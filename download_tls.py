"""Verified HTTPS using native trust and bundled public certificate authorities."""

from functools import lru_cache
import ssl


@lru_cache(maxsize=1)
def download_context():
    import certifi
    import truststore

    # Native verification can retrieve missing intermediate certificates on Windows.
    # Bundled roots also support machines whose public root store is incomplete.
    context = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.load_verify_locations(cafile=certifi.where())
    return context
