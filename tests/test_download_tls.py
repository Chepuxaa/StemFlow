"""A local HTTPS peer must be explicitly trusted and have the right hostname."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import ssl
import threading
import unittest
import urllib.error
import urllib.request

from download_tls import download_context


class Handler(BaseHTTPRequestHandler):
    def handle(self):
        try:
            super().handle()
        except ConnectionResetError:
            # A Windows client aborts after rejecting the peer certificate.
            pass

    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'verified')

    def log_message(self, *args):
        pass


class DownloadTlsTests(unittest.TestCase):
    def test_untrusted_peer_rejected_and_trusted_hostname_checked(self):
        fixture = Path(__file__).parent / 'fixtures'
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        server_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        server_context.load_cert_chain(fixture / 'localhost-cert.pem', fixture / 'localhost-key.pem')
        server.socket = server_context.wrap_socket(server.socket, server_side=True)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = f'https://localhost:{server.server_port}/'
        # Ignore machine proxy configuration for this loopback-only test.
        context = download_context()
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),
                                             urllib.request.HTTPSHandler(context=context))
        try:
            self.assertTrue(context.check_hostname)
            self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
            with self.assertRaises(urllib.error.URLError) as failure:
                opener.open(url, timeout=5)
            self.assertIsInstance(failure.exception.reason, ssl.SSLCertVerificationError)
            context.load_verify_locations(cafile=str(fixture / 'localhost-cert.pem'))
            with opener.open(url, timeout=5) as response:
                self.assertEqual(response.read(), b'verified')
            with self.assertRaises(urllib.error.URLError) as failure:
                opener.open(url.replace('localhost', '127.0.0.1'), timeout=5)
            self.assertIsInstance(failure.exception.reason, ssl.SSLCertVerificationError)
        finally:
            download_context.cache_clear()
            server.shutdown()
            server.server_close()
            thread.join()
