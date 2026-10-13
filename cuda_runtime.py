"""Small native CUDA Driver API wrapper; no CUDA Toolkit or PyTorch dependency."""
import ctypes as C
import hashlib
from functools import lru_cache
import sys


class CudaError(RuntimeError):
    pass


def engine_cache_key(graph, runtime_version, device_name, capability, weights_digest):
    """Invalidate the compiled engine when weights change, even with the same graph."""
    identity = (runtime_version + device_name + str(capability) + weights_digest).encode()
    return hashlib.sha256(graph.read_bytes() + identity).hexdigest()[:24]


class Driver:
    def __init__(self):
        if sys.platform != 'win32':
            raise CudaError('TensorRT RTX currently requires Windows in StemFlow.')
        try:
            self.lib = C.WinDLL('nvcuda.dll')
            self.call('cuInit', [C.c_uint], 0)
            count = C.c_int()
            self.call('cuDeviceGetCount', [C.POINTER(C.c_int)], C.byref(count))
            if count.value < 1:
                raise CudaError('No NVIDIA CUDA device available.')
            self.context = C.c_void_p()
            self.call('cuDevicePrimaryCtxRetain', [C.POINTER(C.c_void_p), C.c_int], C.byref(self.context), 0)
            self.call('cuCtxSetCurrent', [C.c_void_p], self.context)
        except OSError as exc:
            raise CudaError(f'NVIDIA CUDA driver unavailable: {exc}') from exc

    def call(self, name, types, *args):
        function = getattr(self.lib, name)
        function.argtypes, function.restype = types, C.c_int
        code = function(*args)
        if code:
            raise CudaError(f'{name}: CUDA driver error {code}')

    def allocate(self, size):
        pointer = C.c_uint64()
        self.call('cuMemAlloc_v2', [C.POINTER(C.c_uint64), C.c_size_t], C.byref(pointer), size)
        return pointer

    def free(self, pointer):
        self.call('cuMemFree_v2', [C.c_uint64], pointer)

    def information(self):
        name = C.create_string_buffer(256)
        self.call('cuDeviceGetName', [C.c_void_p, C.c_int, C.c_int], name, len(name), 0)
        memory = C.c_size_t()
        self.call('cuDeviceTotalMem_v2', [C.POINTER(C.c_size_t), C.c_int], C.byref(memory), 0)
        major, minor = C.c_int(), C.c_int()
        for attribute, target in [(75, major), (76, minor)]:
            self.call('cuDeviceGetAttribute', [C.POINTER(C.c_int), C.c_int, C.c_int], C.byref(target), attribute, 0)
        return name.value.decode(), memory.value, (major.value, minor.value)

    def close(self):
        if getattr(self, 'context', None):
            self.call('cuDevicePrimaryCtxRelease_v2', [C.c_int], 0)
            self.context = None


@lru_cache(maxsize=1)
def probe_device():
    driver = None
    try:
        driver = Driver()
        name, memory, capability = driver.information()
        if capability not in ((7, 5), (8, 6), (8, 9), (12, 0), (12, 1)):
            raise CudaError(f'GPU compute capability {capability} is not supported by TensorRT RTX.')
        import tensorrt_rtx as trt
        pointer = driver.allocate(16)
        driver.free(pointer)
        logger = trt.Logger(trt.Logger.ERROR)
        if trt.Builder(logger) is None:
            raise CudaError('TensorRT RTX initialization failed.')
        return {'cuda_available': True, 'name': name.removeprefix('NVIDIA GeForce '),
                'memory_gib': round(memory / 1024**3, 1), 'backend': 'TensorRT RTX'}
    except (OSError, ImportError, RuntimeError) as exc:
        return {'cuda_available': False, 'name': 'CPU', 'memory_gib': None,
                'backend': 'ONNX Runtime', 'reason': str(exc)}
    finally:
        if driver:
            driver.close()
