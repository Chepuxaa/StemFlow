"""Acquire the pinned audio tool from its upstream wheel; never bundle that binary."""
import json
from pathlib import Path
import sys
import uuid
import zipfile

from app_paths import DATA_DIR, RESOURCE_DIR
from scripts.download_model import DownloadCancelled, download_checkpoint, verify_checkpoint

FFMPEG_PATH = DATA_DIR / 'runtime/ffmpeg.exe'


def manifest():
    return json.loads((RESOURCE_DIR / 'config/ffmpeg.json').read_text())


def available():
    if not getattr(sys, 'frozen', False):
        import imageio_ffmpeg
        return Path(imageio_ffmpeg.get_ffmpeg_exe()).is_file()
    return FFMPEG_PATH.is_file() and FFMPEG_PATH.stat().st_size == manifest()['binary_bytes']


def get_ffmpeg_exe():
    if not getattr(sys, 'frozen', False):
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    if not available():
        raise FileNotFoundError('Open StemFlow to download its audio tools first.')
    return str(FFMPEG_PATH)


def install(progress=lambda **event: None, cancel=None):
    if available():
        return
    info = manifest()
    FFMPEG_PATH.parent.mkdir(parents=True, exist_ok=True)
    wheel = FFMPEG_PATH.with_name('audio-tool-' + uuid.uuid4().hex + '.whl')
    extracted = FFMPEG_PATH.with_name('ffmpeg-' + uuid.uuid4().hex + '.partial')
    def report(**event):
        progress(**{**event, 'stage': 'tools_downloading' if event['stage'] == 'downloading' else 'tools_verifying'})
    try:
        download_checkpoint(wheel, info, report, cancel)
        if cancel is not None and cancel.is_set():
            raise DownloadCancelled()
        with zipfile.ZipFile(wheel) as archive, extracted.open('xb') as stream:
            with archive.open(info['member']) as source:
                while block := source.read(1024 * 1024):
                    if cancel is not None and cancel.is_set():
                        raise DownloadCancelled()
                    stream.write(block)
        if not verify_checkpoint(extracted, {'weights_bytes': info['binary_bytes'],
                                             'weights_sha256': info['binary_sha256']}, cancel=cancel):
            raise ValueError('Audio tool integrity check failed.')
        extracted.replace(FFMPEG_PATH)
    finally:
        wheel.unlink(missing_ok=True)
        extracted.unlink(missing_ok=True)
