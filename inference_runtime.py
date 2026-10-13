"""Persistent MelBand neural-core runtimes: TensorRT RTX GPU and ONNX CPU."""
import ctypes as C
import gc
import math
import mmap
import os
from pathlib import Path
import uuid

import numpy as np
from app_paths import DATA_DIR, MODEL_DIR
from cuda_runtime import Driver, CudaError, engine_cache_key, probe_device
from scripts.download_model import model_manifest
from spectral_runtime import spectrum_of, reconstruct, RATE

INSTRUMENTS = ['drums', 'bass', 'other', 'vocals']


def deserialize_engine_file(runtime, path):
    # Map the cache rather than allocating another ~1.9 GB Python bytes object.
    with Path(path).open('rb') as stream:
        with mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as data:
            return runtime.deserialize_cuda_engine(data)


def resolve_device(requested):
    if requested not in ('auto', 'cuda', 'cpu'):
        raise ValueError(f'Unknown device: {requested}')
    if requested == 'cpu':
        return 'cpu'
    if probe_device()['cuda_available']:
        return 'cuda:0'
    if requested == 'cuda':
        raise CudaError('TensorRT RTX unavailable. Select Auto or CPU in Settings.')
    return 'cpu'


class CpuModel:
    def __init__(self, graph, fast=False):
        import onnxruntime as ort
        from cpu_graph import optimized_cpu_graph
        options = ort.SessionOptions()
        options.intra_op_num_threads = min(8, os.cpu_count() or 1)
        options.inter_op_num_threads = 1
        options.enable_cpu_mem_arena = False
        options.log_severity_level = 3
        graph = optimized_cpu_graph(graph)
        if fast:
            from cpu_int8 import fast_cpu_graph
            graph = fast_cpu_graph(graph)
        self.session = ort.InferenceSession(str(graph), sess_options=options,
                                            providers=['CPUExecutionProvider'])

    def predict(self, spectrum):
        return self.session.run(['masks'], {'spectrum': spectrum})[0]

    def close(self):
        self.session = None


class RtxModel:
    def __init__(self, graph):
        self.driver = None
        self.allocations = []
        self.stream = None
        self.execution = self.engine = self.runtime = None
        try:
            import tensorrt_rtx as trt
            self.driver = Driver()
            name, _, capability = self.driver.information()
            key = engine_cache_key(graph, trt.__version__, name, capability, model_manifest()['weights_sha256'])
            directory = DATA_DIR / 'engines'
            directory.mkdir(parents=True, exist_ok=True)
            cache = directory / f'{graph.stem}-{key}.engine'
            logger = trt.Logger(trt.Logger.ERROR)
            self.runtime = trt.Runtime(logger)
            # Limit concurrent compiler work on 16 GB systems; GPU inference is unaffected.
            self.runtime.max_threads = 1
            self.engine_reused = False
            if cache.is_file():
                try:
                    self.engine = deserialize_engine_file(self.runtime, cache)
                    self.engine_reused = self.engine is not None
                except RuntimeError:
                    self.engine = None
            if self.engine is None:
                builder = trt.Builder(logger)
                network = builder.create_network(0)
                parser = trt.OnnxParser(network, logger)
                if not parser.parse_from_file(str(graph)):
                    raise CudaError('TensorRT CUDA model parsing failed: ' + '; '.join(str(parser.get_error(i)) for i in range(parser.num_errors)))
                config = builder.create_builder_config()
                config.set_memory_pool_limit(trt.MemoryPoolType.WORKSPACE, 256 * 1024**2)
                blob = builder.build_serialized_network(network, config)
                if blob is None:
                    raise CudaError('TensorRT CUDA engine compilation failed; try a six-second chunk.')
                temporary = cache.with_name(cache.name + '.' + uuid.uuid4().hex + '.partial')
                try:
                    with temporary.open('xb') as stream:
                        stream.write(blob)
                    temporary.replace(cache)
                finally:
                    temporary.unlink(missing_ok=True)
                del parser, network, config, builder, blob
                gc.collect()
                self.engine = deserialize_engine_file(self.runtime, cache)
            if self.engine is None:
                raise CudaError('TensorRT CUDA engine initialization failed.')
            self.execution = self.engine.create_execution_context()
            if self.execution is None:
                raise CudaError('TensorRT CUDA execution context could not be created.')
            self.output = np.empty(tuple(self.engine.get_tensor_shape('masks')),
                                   dtype=trt.nptype(self.engine.get_tensor_dtype('masks')))
            self.input_dtype = trt.nptype(self.engine.get_tensor_dtype('spectrum'))
            shape = self.engine.get_tensor_shape('spectrum')
            self.stream = C.c_void_p()
            self.driver.call('cuStreamCreate', [C.POINTER(C.c_void_p), C.c_uint], C.byref(self.stream), 0)
            for tensor, size in [('spectrum', int(np.prod(shape)) * np.dtype(self.input_dtype).itemsize),
                                 ('masks', self.output.nbytes)]:
                pointer = self.driver.allocate(size)
                self.allocations.append(pointer)
                if not self.execution.set_tensor_address(tensor, pointer.value):
                    raise CudaError(f'TensorRT CUDA cannot bind {tensor}.')
        except Exception as exc:
            self.close()
            if isinstance(exc, CudaError):
                raise
            raise CudaError(f'TensorRT CUDA initialization failed: {exc}') from exc

    def predict(self, spectrum):
        try:
            source = np.ascontiguousarray(spectrum, dtype=self.input_dtype)
            self.driver.call('cuMemcpyHtoD_v2', [C.c_uint64, C.c_void_p, C.c_size_t],
                             self.allocations[0], source.ctypes.data, source.nbytes)
            if not self.execution.execute_async_v3(self.stream.value):
                raise CudaError('TensorRT CUDA inference failed.')
            self.driver.call('cuStreamSynchronize', [C.c_void_p], self.stream)
            self.driver.call('cuMemcpyDtoH_v2', [C.c_void_p, C.c_uint64, C.c_size_t],
                             self.output.ctypes.data, self.allocations[1], self.output.nbytes)
            return self.output
        except Exception as exc:
            raise CudaError(f'TensorRT CUDA inference failed: {exc}') from exc

    def close(self):
        self.execution = self.engine = self.runtime = None
        if self.driver:
            for pointer in self.allocations:
                try:
                    self.driver.free(pointer)
                except CudaError:
                    pass
            self.allocations.clear()
            if self.stream:
                try:
                    self.driver.call('cuStreamDestroy_v2', [C.c_void_p], self.stream)
                except CudaError:
                    pass
                self.stream = None
            try:
                self.driver.close()
            except CudaError:
                # A lost/reset CUDA context must not prevent the CPU fallback.
                pass
            self.driver = None


class ModelCache:
    """Retain one session and its GPU buffers throughout a queue."""
    def __init__(self):
        self.model = self.config = self.device = self.chunk_seconds = None
        self.force_cpu = False
        self.cpu_fast = False

    def get(self, device, chunk_seconds=11, cpu_fast=False):
        actual_fast = bool(cpu_fast and not device.startswith('cuda'))
        reused = self.model is not None and self.device == device and self.chunk_seconds == chunk_seconds and self.cpu_fast == actual_fast
        if not reused:
            self.clear()
            self.model, self.config = load_model(device, chunk_seconds, cpu_fast=actual_fast) if actual_fast else load_model(device, chunk_seconds)
            self.device, self.chunk_seconds = device, chunk_seconds
            self.cpu_fast = actual_fast
        return self.model, self.config, reused

    def clear(self):
        if self.model is not None:
            self.model.close()
        self.model = self.config = self.device = self.chunk_seconds = None
        self.cpu_fast = False


def load_model(device='cuda:0', chunk_seconds=11, cpu_fast=False):
    if chunk_seconds not in (6, 11):
        raise ValueError('Converted MelBand supports six- or eleven-second chunks.')
    graph = MODEL_DIR / f'core-{int(chunk_seconds)}.onnx'
    if not graph.is_file():
        raise FileNotFoundError(f'ONNX model missing: {graph}. Download the model in Settings.')
    indices = np.load(MODEL_DIR / 'freq-indices.npy', allow_pickle=False)
    if indices.ndim != 1 or indices.dtype != np.int64 or np.any(indices < 0) or np.any(indices >= 4098):
        raise ValueError('Invalid MelBand frequency indices.')
    model = RtxModel(graph) if device.startswith('cuda') else CpuModel(graph, fast=cpu_fast)
    model.indices = indices
    model.device = device
    return model, {'audio': {'sample_rate': RATE}, 'inference': {'num_overlap': 4},
                   'training': {'instruments': INSTRUMENTS}}


def infer(model, config, audio, chunk_seconds=11, progress=None):
    size = int(chunk_seconds * RATE)
    if config['inference']['num_overlap'] not in (2, 4):
        raise ValueError('Supported overlap factors: 2 (50%) or 4 (75%).')
    step = size // config['inference']['num_overlap']
    length = len(audio)
    count = math.ceil(max(length - size, 0) / step) + 1
    output = np.zeros((4, 2, length), dtype=np.float32)
    weights = np.zeros(length, dtype=np.float32)
    taper = np.bartlett(size).astype(np.float32)
    for index in range(count):
        start, stop = index * step, min(index * step + size, length)
        batch = np.zeros((1, 2, size), dtype=np.float32)
        batch[0, :, :stop - start] = audio[start:stop].T
        spectrum = spectrum_of(batch)
        prediction = reconstruct(spectrum, model.predict(spectrum), model.indices, size)[0]
        if prediction.shape != (4, 2, size) or not np.isfinite(prediction).all():
            raise RuntimeError('Model returned invalid stem audio.')
        window = taper.copy()
        if index == 0:
            window[:size // 2] = 1
        if index == count - 1:
            window[size // 2:] = 1
        valid = stop - start
        output[:, :, start:stop] += prediction[:, :, :valid] * window[None, None, :valid]
        weights[start:stop] += window[:valid]
        if progress:
            progress(index + 1, count)
    if not np.all(weights > 0):
        raise RuntimeError('Incomplete overlap-add coverage.')
    output /= weights[None, None, :]
    return dict(zip(INSTRUMENTS, output))
