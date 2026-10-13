"""Download the pinned checkpoint and verify its size and SHA-256."""

import argparse
import hashlib
import json
from pathlib import Path
import sys
import urllib.request

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app_paths import MODEL_DIR, RESOURCE_DIR


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args()
    manifest = json.loads((RESOURCE_DIR / 'config/model.json').read_text())
    target = MODEL_DIR / 'ver2.ckpt'
    if target.exists():
        if target.stat().st_size != manifest['weights_bytes'] or sha256(target) != manifest['weights_sha256']:
            raise SystemExit(f'Existing checkpoint failed verification; preserved: {target}')
        print(f'Verified: {target}')
        return
    if args.verify_only:
        raise SystemExit(f'Checkpoint missing: {target}')
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    temporary = MODEL_DIR / 'ver2.ckpt.partial'
    if temporary.exists():
        raise SystemExit(f'An incomplete download exists. Remove it to retry: {temporary}')
    digest, received = hashlib.sha256(), 0
    owned = False
    try:
        request = urllib.request.Request(manifest['weights_url'], headers={'User-Agent': 'StemFlow/1.0'})
        with urllib.request.urlopen(request, timeout=60) as response, temporary.open('xb') as stream:
            owned = True
            while block := response.read(4 * 1024 * 1024):
                stream.write(block)
                digest.update(block)
                received += len(block)
                print(f'\rDownloading: {received / manifest["weights_bytes"]:.0%}', end='', flush=True)
        if received != manifest['weights_bytes'] or digest.hexdigest() != manifest['weights_sha256']:
            raise ValueError('Checkpoint verification failed')
        temporary.rename(target)
    except Exception:
        if owned:
            temporary.unlink(missing_ok=True)
        raise
    print(f'\nVerified: {target}')


if __name__ == '__main__':
    main()
