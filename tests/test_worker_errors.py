import unittest
from worker_errors import worker_error


class WorkerErrorTests(unittest.TestCase):
    def test_native_oom_is_readable_without_protocol_noise(self):
        lines = ['STEM_EVENT {"stage":"load"}', 'Audio: loading model', 'LLVM ERROR: out of memory']
        self.assertIn('system memory', worker_error(lines))
        self.assertIn('оперативной памяти', worker_error(lines, 'ru'))
        self.assertNotIn('STEM_EVENT', worker_error(lines))

    def test_other_failures_keep_diagnostic_and_empty_crashes_get_a_message(self):
        self.assertEqual(worker_error(['STEM_EVENT {}', 'Missing DLL']), 'Missing DLL')
        self.assertTrue(worker_error(['STEM_EVENT {}']))
