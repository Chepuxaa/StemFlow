"""Download the pinned ONNX bundle and verify every file's size and SHA-256."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time
import urllib.request
import uuid

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app_paths import MODEL_DIR, RESOURCE_DIR
from download_tls import download_context


class DownloadCancelled(Exception):
    pass


def model_manifest():
    return json.loads((RESOURCE_DIR / 'config/model.json').read_text())


def model_target():
    return MODEL_DIR / model_manifest().get('weights_file', 'ver2.ckpt')


def checkpoint_fingerprint(target):
    manifest = model_manifest()
    if manifest.get('files') and Path(target).parent == MODEL_DIR:
        return tuple((file['name'], checkpoint_fingerprint_file(MODEL_DIR / file['name'])) for file in manifest['files'])
    return checkpoint_fingerprint_file(target)


def checkpoint_fingerprint_file(target):
    if not Path(target).is_file():
        return None
    stat = Path(target).stat()
    return stat.st_size, stat.st_mtime_ns


def _check_cancel(cancel):
    if cancel is not None and cancel.is_set():
        raise DownloadCancelled()


def verify_checkpoint(target, manifest, progress=lambda **event: None, cancel=None):
    if manifest.get('files'):
        offset = 0
        for file in manifest['files']:
            def report(**event):
                progress(**{**event, 'received': offset + event['received'], 'total': manifest['weights_bytes']})
            single = {'weights_bytes': file['bytes'], 'weights_sha256': file['sha256']}
            if not verify_checkpoint(Path(target).parent / file['name'], single, report, cancel):
                return False
            offset += file['bytes']
        return True
    target = Path(target)
    _check_cancel(cancel)
    if not target.is_file():
        return False
    total = manifest['weights_bytes']
    if target.stat().st_size != total:
        return False
    digest, received = hashlib.sha256(), 0
    with target.open('rb') as stream:
        while block := stream.read(4 * 1024 * 1024):
            _check_cancel(cancel)
            digest.update(block)
            received += len(block)
            progress(stage='checking', received=received, total=total, speed=0)
    _check_cancel(cancel)
    return received == total and digest.hexdigest() == manifest['weights_sha256']


def download_checkpoint(target, manifest, progress=lambda **event: None, cancel=None):
    """Publish only verified bytes; cancellation removes only this task's partial file."""
    if manifest.get('files'):
        offset = 0
        for file in manifest['files']:
            single = {'weights_bytes': file['bytes'], 'weights_sha256': file['sha256'], 'weights_url': file['url']}
            destination = Path(target).parent / file['name']
            def report(**event):
                progress(**{**event, 'received': offset + event['received'], 'total': manifest['weights_bytes']})
            if not verify_checkpoint(destination, single, report, cancel):
                download_checkpoint(destination, single, report, cancel)
            offset += file['bytes']
        return Path(target)
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    total = manifest['weights_bytes']
    if shutil.disk_usage(target.parent).free < total + 64 * 1024**2:
        raise OSError('Not enough free space to download the model.')
    temporary = target.with_name(target.name + '.' + uuid.uuid4().hex + '.partial')
    owned = False
    try:
        _check_cancel(cancel)
        request = urllib.request.Request(manifest['weights_url'], headers={'User-Agent': 'StemFlow/1.0'})
        progress(stage='downloading', received=0, total=total, speed=0)
        with urllib.request.urlopen(request, timeout=15, context=download_context()) as response, temporary.open('xb') as stream:
            owned = True
            received = 0
            started = time.monotonic()
            while True:
                _check_cancel(cancel)
                block = response.read1(1024 * 1024)
                if not block:
                    break
                received += len(block)
                if received > total:
                    raise ValueError('Downloaded checkpoint exceeds the expected size.')
                stream.write(block)
                progress(stage='downloading', received=received, total=total,
                         speed=received / max(time.monotonic() - started, 0.001))
            stream.flush()
            os.fsync(stream.fileno())
        progress(stage='verifying', received=0, total=total, speed=0)
        def verified_progress(**event):
            progress(**{**event, 'stage': 'verifying'})
        if not verify_checkpoint(temporary, manifest, verified_progress, cancel):
            raise ValueError('Checkpoint size or SHA-256 verification failed. Please retry.')
        _check_cancel(cancel)
        # Preserve an existing invalid checkpoint rather than silently deleting it.
        if target.exists():
            target.rename(target.with_name(target.name + '.' + uuid.uuid4().hex + '.invalid'))
        temporary.replace(target)
    finally:
        if owned:
            temporary.unlink(missing_ok=True)
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args()
    manifest = model_manifest()
    target = model_target()
    def progress(**event):
        print(f'\r{event["stage"].capitalize()}: {event["received"] / event["total"]:.0%}', end='', flush=True)
    if verify_checkpoint(target, manifest, progress):
        print(f'\nVerified: {target}')
        if not args.verify_only:
            from audio_runtime import install
            install(progress)
        return
    if args.verify_only:
        raise SystemExit(f'Checkpoint missing or invalid: {target}')
    download_checkpoint(target, manifest, progress)
    from audio_runtime import install
    install(progress)
    print(f'\nVerified: {target}')


if __name__ == '__main__':
    main()
