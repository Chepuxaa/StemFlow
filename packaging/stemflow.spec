"""Experimental Windows onedir build: GUI and console worker share one runtime."""
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_submodules, copy_metadata

root = Path(SPECPATH).parent
datas = [(str(root / 'ui'), 'ui'), (str(root / 'config'), 'config'),
         (str(root / 'vendor/msst'), 'vendor/msst'),
         (str(root / 'LICENSE'), '.'), (str(root / 'THIRD_PARTY_NOTICES.md'), '.')]
binaries, hiddenimports = [], ['rotary_embedding_torch', 'einops', 'beartype', 'librosa']
for package in ('imageio_ffmpeg', 'webview'):
    package_datas, package_binaries, package_imports = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_imports
# The GPL FFmpeg executable is acquired directly from its upstream wheel at first run.
# StemFlow's release carries the wrapper and notices, but does not redistribute it.
datas = [item for item in datas if not ('imageio_ffmpeg' in item[0] and item[0].endswith('.exe'))]
binaries = [item for item in binaries if not ('imageio_ffmpeg' in item[0] and item[0].endswith('.exe'))]
hiddenimports += collect_submodules('beartype')
for package in ('rotary-embedding-torch', 'librosa', 'beartype'):
    datas += copy_metadata(package)
a = Analysis([str(root / 'stemflow.py')], pathex=[str(root)], binaries=binaries,
             datas=datas, hiddenimports=hiddenimports, hookspath=[], runtime_hooks=[],
             excludes=['tkinter', 'PyQt5', 'PyQt6', 'PySide2', 'PySide6'], noarchive=False)
# Third-party hooks can add the upstream executable during Analysis as well.
a.datas = [item for item in a.datas if not ('imageio_ffmpeg' in item[0] and item[0].endswith('.exe'))]
a.binaries = [item for item in a.binaries if not ('imageio_ffmpeg' in item[0] and item[0].endswith('.exe'))]
pyz = PYZ(a.pure)
gui = EXE(pyz, a.scripts, [], exclude_binaries=True, name='StemFlow', console=False, upx=False)
worker = EXE(pyz, a.scripts, [], exclude_binaries=True, name='StemFlow-worker', console=True, upx=False)
app = COLLECT(gui, worker, a.binaries, a.datas, strip=False, upx=False, name='StemFlow')
