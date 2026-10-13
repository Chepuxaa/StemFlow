"""A single-file app must never launch a stale worker from an older install."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from app_paths import worker_command


class WorkerLaunchTests(unittest.TestCase):
    def test_uses_itself_even_when_an_old_worker_is_beside_it(self):
        with tempfile.TemporaryDirectory(prefix='stemflow-worker-test-') as temporary:
            executable = str(Path(temporary) / 'StemFlow.exe')
            (Path(temporary) / 'StemFlow-worker.exe').write_bytes(b'old version')
            with patch.object(sys, 'frozen', True, create=True), patch.object(sys, 'executable', executable):
                self.assertEqual(worker_command(['--worker']), [executable, '--worker'])


if __name__ == '__main__':
    unittest.main()
