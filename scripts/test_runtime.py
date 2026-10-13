"""Hardware integration checks for model parity, queue reuse and CPU fallback."""
import argparse
import json
from pathlib import Path
import sys
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import numpy as np
import inference_runtime
from model_runtime import ModelCache
from cuda_runtime import CudaError
import separate


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--gpu', action='store_true')
    parser.add_argument('--reference-dir', type=Path, help='Optional input-audio.npy and expected-audio.npy parity fixture')
    args = parser.parse_args()
    results = {}
    class LostDriver:
        def close(self):
            raise CudaError('CUDA context was reset')
    lost = object.__new__(inference_runtime.RtxModel)
    lost.execution = lost.engine = lost.runtime = None
    lost.driver, lost.allocations, lost.stream = LostDriver(), [], None
    lost.close()
    assert lost.driver is None
    results['lost_cuda_context_cleanup'] = 'PASS'
    short = np.zeros((6615, 2), dtype=np.float32)
    short[:, 0] = np.sin(np.arange(len(short)) * (2 * np.pi * 440 / 44100)) * .1
    short[:, 1] = short[:, 0]
    cache = ModelCache()
    original_loader = inference_runtime.load_model
    cuda_attempts = []
    def fail_cuda(device, seconds, cpu_fast=False):
        if device.startswith('cuda'):
            cuda_attempts.append(device)
            raise CudaError('Injected CUDA failure to verify automatic fallback')
        return original_loader(device, seconds, cpu_fast=cpu_fast)
    with patch('separate.resolve_device', return_value='cuda:0'), patch('inference_runtime.load_model', side_effect=fail_cuda):
        first, report = separate.separate_audio(short, 6, 'auto', lambda *_: None, cache)
        session = cache.model
        second, reused = separate.separate_audio(short, 6, 'auto', lambda *_: None, cache)
        assert report['device'] == 'cpu' and report['fallback_reason']
        assert reused['device'] == 'cpu' and reused['model_reused'] and cache.model is session
        assert len(cuda_attempts) == 1
        assert all(np.array_equal(first[k], second[k]) for k in first)
    cache.clear()
    results['auto_fallback_and_sticky_cpu_queue'] = 'PASS'
    for device, seconds in [('cpu', 11)] + ([('cuda', 6), ('cuda', 11)] if args.gpu else []):
        cache = ModelCache()
        started = time.perf_counter()
        actual, report = separate.separate_audio(short, seconds, device, lambda *_: None, cache)
        assert set(actual) == {'drums', 'bass', 'other', 'vocals'}
        assert all(v.shape == (2, len(short)) and np.isfinite(v).all() for v in actual.values())
        if device == 'cuda' and seconds == 11 and args.reference_dir is not None:
            work = args.reference_dir
            audio = np.load(work / 'input-audio.npy')[0].T
            expected = np.load(work / 'expected-audio.npy')[0]
            stems, reused = separate.separate_audio(audio, seconds, device, lambda *_: None, cache)
            predicted = np.stack([stems[k] for k in inference_runtime.INSTRUMENTS])
            error = expected.astype(np.float64) - predicted
            agreement = float(10 * np.log10(np.sum(expected.astype(np.float64)**2) / np.sum(error**2)))
            assert agreement > 50, agreement
            assert reused['model_reused']
            results['gpu_11_parity_db'] = agreement
        results[f'{device}_{seconds}_seconds'] = {'status': 'PASS', 'elapsed': time.perf_counter() - started}
        cache.clear()
    assert 'torch' not in sys.modules
    results['torch_imported'] = False
    (ROOT / 'build').mkdir(exist_ok=True)
    (ROOT / 'build/runtime-validation.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
    print(json.dumps(results, indent=2), flush=True)


if __name__ == '__main__':
    main()
