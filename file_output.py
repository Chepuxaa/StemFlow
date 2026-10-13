"""Publish a verified Stem beside its source and retain a recoverable original."""

import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import uuid

import imageio_ffmpeg
from ni_stem import boxes

BACKUP_FOLDER = '.stemflow-originals'


def fingerprint(path):
    stat = Path(path).stat()
    return stat.st_size, stat.st_mtime_ns


def checksum(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.digest()


def replace_original(source, stem, expected_source):
    source, stem = Path(source).resolve(), Path(stem).resolve()
    target = source.parent / stem.name
    if target == source or target.exists():
        raise FileExistsError(f'Replacement target already exists: {target}')
    movie = dict(boxes(stem.read_bytes()))[b'moov']
    if sum(kind == b'trak' for kind, _ in boxes(movie)) != 5:
        raise ValueError('Replacement must contain five audio tracks')
    if b'stem' not in dict(boxes(dict(boxes(movie))[b'udta'])):
        raise ValueError('NI Stem metadata is missing')
    # Validate every encoded stream before moving the original.
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), '-nostdin', '-v', 'error',
                    '-i', str(stem), '-map', '0:a', '-f', 'null', '-'], check=True)
    if fingerprint(source) != expected_source:
        raise RuntimeError('Source changed during processing; original preserved')
    backup_folder = source.parent / BACKUP_FOLDER
    if backup_folder.is_symlink() or backup_folder.resolve().parent != source.parent:
        raise ValueError('Backup folder must not be a symbolic link')
    backup_folder.mkdir(exist_ok=True)
    backup = backup_folder / source.name
    if backup.exists():
        backup = backup_folder / f'{source.stem}-{uuid.uuid4().hex}{source.suffix}'
    if backup.parent.resolve() != backup_folder.resolve():
        raise ValueError('Invalid backup destination')
    temporary = source.parent / f'.{target.name}.{uuid.uuid4().hex}.partial'
    try:
        with stem.open('rb') as original, temporary.open('xb') as copied:
            shutil.copyfileobj(original, copied)
            copied.flush()
            os.fsync(copied.fileno())
        if checksum(temporary) != checksum(stem):
            raise IOError('Replacement copy verification failed')
        if fingerprint(source) != expected_source:
            raise RuntimeError('Source changed while publishing; original preserved')
        # Windows rename refuses an existing target. Keep both files if archiving fails.
        temporary.rename(target)
        source.rename(backup)
    finally:
        temporary.unlink(missing_ok=True)
    return target, backup
