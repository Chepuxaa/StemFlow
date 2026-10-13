"""Updating external model weights must invalidate an otherwise identical graph."""
from pathlib import Path
import tempfile
import unittest

from cuda_runtime import engine_cache_key


class EngineCacheTests(unittest.TestCase):
    def test_weight_update_and_gpu_change_do_not_reuse_an_old_engine(self):
        with tempfile.TemporaryDirectory(prefix='stemflow-cache-test-') as temporary:
            graph = Path(temporary) / 'core.onnx'
            graph.write_bytes(b'identical neural graph, external weights')
            baseline = engine_cache_key(graph, '1.6', 'RTX 3070', (8, 6), 'old-weights')
            self.assertEqual(baseline, engine_cache_key(graph, '1.6', 'RTX 3070', (8, 6), 'old-weights'))
            self.assertNotEqual(baseline, engine_cache_key(graph, '1.6', 'RTX 3070', (8, 6), 'new-weights'))
            self.assertNotEqual(baseline, engine_cache_key(graph, '1.6', 'RTX 4070', (8, 9), 'old-weights'))


if __name__ == '__main__':
    unittest.main()
