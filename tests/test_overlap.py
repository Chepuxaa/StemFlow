"""Both overlaps preserve sample coverage; Auto retains overlap after fallback."""
from contextlib import redirect_stdout
from io import StringIO
import unittest
from unittest.mock import patch

import numpy as np
import inference_runtime as runtime


class IdentityModel:
    def __init__(self, device='cpu'):
        self.device = device
        self.indices = None
        self.calls = 0

    def predict(self, batch):
        self.calls += 1
        return batch

    def close(self):
        pass


class OverlapTests(unittest.TestCase):
    def test_partial_last_chunk_and_boundaries_preserve_audio(self):
        rng = np.random.default_rng(3)
        calls = {}
        for seconds in (6, 11):
            for length in (1, int(seconds * runtime.RATE) - 1, int(25.37 * runtime.RATE)):
                audio = rng.uniform(-1, 1, (length, 2)).astype(np.float32)
                for overlap in (2, 4):
                    model = IdentityModel()
                    with patch.object(runtime, 'spectrum_of', side_effect=lambda batch: batch), \
                         patch.object(runtime, 'reconstruct', side_effect=lambda spectrum, masks, indices, size: np.repeat(masks[:, None], 4, axis=1)):
                        result = runtime.infer(model, {'inference': {'num_overlap': overlap}}, audio, seconds)
                    for stem in result.values():
                        np.testing.assert_allclose(stem.T, audio, atol=2e-7, rtol=2e-7)
                    calls[seconds, length, overlap] = model.calls
            self.assertLess(calls[seconds, length, 2], calls[seconds, length, 4])

    def test_auto_fallback_keeps_overlap_and_preserves_cached_config(self):
        import separate
        config = {'inference': {'num_overlap': 4}}
        seen = []
        def load(device, seconds):
            return IdentityModel(device), config
        def infer(model, selected, *args):
            seen.append((model.device, selected['inference']['num_overlap']))
            if model.device.startswith('cuda'):
                raise separate.CudaError('CUDA unavailable during execution')
            return {'vocals': np.zeros((2, 1))}
        cache = runtime.ModelCache()
        with patch.object(runtime, 'load_model', side_effect=load), \
             patch.object(separate, 'resolve_device', return_value='cuda:0'), \
             patch.object(separate, 'infer', side_effect=infer), \
             patch.object(separate, 'event'), redirect_stdout(StringIO()):
            for _ in range(2):
                _, report = separate.separate_audio(np.zeros((1, 2)), 6, 'auto', None,
                                                   cache, overlap_percent=50)
                self.assertEqual(report['device'], 'cpu')
                self.assertEqual(report['overlap_percent'], 50)
                self.assertEqual(report['overlap'], 2)
        self.assertEqual(seen, [('cuda:0', 2), ('cpu', 2), ('cpu', 2)])
        self.assertEqual(config['inference']['num_overlap'], 4)
        cache.clear()
