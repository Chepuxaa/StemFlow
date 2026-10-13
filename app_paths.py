"""Writable application data and scratch audio live outside the installation."""

import os
from pathlib import Path
import shutil
import tempfile
import sys

RESOURCE_DIR = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))

DATA_DIR = Path(os.environ.get('LOCALAPPDATA', str(Path.home() / '.local/share'))) / 'StemFlow'
TEMP_ROOT = Path(tempfile.gettempdir()) / 'StemFlow'
MODEL_DIR = DATA_DIR / 'models/melband-4stem-syh-v2'


def worker_command(arguments):
    if getattr(sys, 'frozen', False):
        return [sys.executable, *arguments]
    return [str(RESOURCE_DIR / '.venv/Scripts/python.exe'), '-u',
            str(RESOURCE_DIR / 'stemflow.py'), *arguments]


def cleanup_run_directory(directory):
    path = Path(directory).resolve()
    if path.parent != TEMP_ROOT.resolve() or not path.name.startswith('track-'):
        raise ValueError('Refusing to clean an unrecognized scratch directory')
    if path.exists():
        shutil.rmtree(path)
