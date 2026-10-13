"""Bundle integrity, cancellation/resume and preservation of existing files."""
import functools
import hashlib
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import tempfile
import threading
import unittest

from scripts.download_model import DownloadCancelled, download_checkpoint, verify_checkpoint


class QuietHandler(SimpleHTTPRequestHandler):
    counts = {}

    def do_GET(self):
        self.counts[self.path] = self.counts.get(self.path, 0) + 1
        super().do_GET()

    def log_message(self, *args):
        pass


class BundleDownloadTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='stemflow-download-test-')
        self.root = Path(self.temporary.name)
        self.upstream = self.root / 'upstream'
        self.upstream.mkdir()
        QuietHandler.counts = {}
        handler = functools.partial(QuietHandler, directory=str(self.upstream))
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        files = []
        for name, data in [('weights.data', b'weights'), ('graph.onnx', b'graph contents' * 100)]:
            (self.upstream / name).write_bytes(data)
            files.append({'name': name, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(),
                          'url': f'http://127.0.0.1:{self.server.server_port}/{name}'})
        self.manifest = {'files': files, 'weights_bytes': sum(f['bytes'] for f in files)}
        self.target = self.root / 'installed/weights.data'

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temporary.cleanup()

    def test_cancel_keeps_completed_files_and_resume_skips_them(self):
        cancel = threading.Event()
        events = []
        def progress(**event):
            events.append(event)
            if event['stage'] == 'downloading' and event['received'] > len(b'weights'):
                cancel.set()
        with self.assertRaises(DownloadCancelled):
            download_checkpoint(self.target, self.manifest, progress, cancel)
        self.assertEqual(self.target.read_bytes(), b'weights')
        self.assertFalse((self.target.parent / 'graph.onnx').exists())
        self.assertFalse(list(self.target.parent.glob('*.partial')))
        cancel.clear()
        download_checkpoint(self.target, self.manifest, cancel=cancel)
        self.assertTrue(verify_checkpoint(self.target, self.manifest))
        self.assertEqual(QuietHandler.counts['/weights.data'], 1)
        self.assertEqual(QuietHandler.counts['/graph.onnx'], 2)
        self.assertTrue(all(event['total'] == self.manifest['weights_bytes'] for event in events))

    def test_bad_hash_does_not_replace_an_existing_file(self):
        self.target.parent.mkdir()
        self.target.write_bytes(b'original content')
        file = self.manifest['files'][0]
        invalid = {'weights_bytes': file['bytes'], 'weights_sha256': '0' * 64, 'weights_url': file['url']}
        with self.assertRaises(ValueError):
            download_checkpoint(self.target, invalid)
        self.assertEqual(self.target.read_bytes(), b'original content')
        self.assertFalse(list(self.target.parent.glob('*.partial')))


if __name__ == '__main__':
    unittest.main()
