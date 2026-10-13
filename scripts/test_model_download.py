"""Exercise model setup against a local HTTP server, without downloading weights."""
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.download_model import DownloadCancelled, download_checkpoint, verify_checkpoint
from desktop import DesktopAPI


PAYLOAD = b'StemFlow download integrity test\n' * 80000


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Length', str(len(PAYLOAD)))
        self.end_headers()
        try:
            self.wfile.write(PAYLOAD)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def log_message(self, *args):
        pass


class ModelSetupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.manifest = {'weights_url': f'http://127.0.0.1:{cls.server.server_port}/model',
                        'weights_bytes': len(PAYLOAD),
                        'weights_sha256': hashlib.sha256(PAYLOAD).hexdigest()}

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(prefix='StemFlow-download-test-')
        self.addCleanup(self.folder.cleanup)
        self.target = Path(self.folder.name) / 'ver2.ckpt'

    def test_verified_download_then_corruption(self):
        events = []
        download_checkpoint(self.target, self.manifest, lambda **event: events.append(event))
        self.assertEqual(self.target.read_bytes(), PAYLOAD)
        self.assertTrue(verify_checkpoint(self.target, self.manifest))
        self.assertEqual({e['stage'] for e in events}, {'downloading', 'verifying'})
        self.assertEqual(events[-1]['received'], len(PAYLOAD))
        self.target.write_bytes(b'X' + PAYLOAD[1:])
        self.assertFalse(verify_checkpoint(self.target, self.manifest))

    def test_bad_hash_keeps_existing_file(self):
        self.target.write_bytes(b'original')
        with self.assertRaises(ValueError):
            download_checkpoint(self.target, {**self.manifest, 'weights_sha256': '0' * 64})
        self.assertEqual(self.target.read_bytes(), b'original')
        self.assertEqual(list(self.target.parent.glob('*.partial')), [])

    def test_cancel_download_and_verification(self):
        for stage in ('downloading', 'verifying'):
            cancel = threading.Event()
            def progress(**event):
                if event['stage'] == stage and event['received'] > 0:
                    cancel.set()
            with self.assertRaises(DownloadCancelled):
                download_checkpoint(self.target, self.manifest, progress, cancel)
            self.assertFalse(self.target.exists())
            self.assertEqual(list(self.target.parent.glob('*.partial')), [])

    def test_repair_preserves_old_checkpoint(self):
        self.target.write_bytes(b'broken')
        download_checkpoint(self.target, self.manifest)
        self.assertTrue(verify_checkpoint(self.target, self.manifest))
        backups = list(self.target.parent.glob('*.invalid'))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), b'broken')

    def test_gui_setup_state_and_queue_gate(self):
        with patch('desktop.MODEL_DIR', self.target.parent), patch('desktop.model_manifest', return_value=self.manifest):
            api = DesktopAPI(state_file=self.target.parent / 'queue.json')
            api._jobs = [{'id': 'test', 'status': 'pending'}]
            api.start()
            self.assertFalse(api.get_state()['busy'])
            api.check_model()
            api._model_thread.join(timeout=5)
            self.assertEqual(api.get_state()['model']['stage'], 'missing')
            api.download_model()
            api._model_thread.join(timeout=5)
            self.assertEqual(api.get_state()['model']['stage'], 'ready')
            api.check_model()
            api._model_thread.join(timeout=5)
            self.assertEqual(api.get_state()['model']['stage'], 'ready')
            self.target.write_bytes(b'broken')
            api.start()
            api._model_thread.join(timeout=5)
            self.assertFalse(api.get_state()['busy'])
            self.assertEqual(api.get_state()['model']['stage'], 'invalid')


if __name__ == '__main__':
    unittest.main()
