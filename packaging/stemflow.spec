"""Experimental Windows onedir build: GUI and console worker share one runtime."""
from pathlib import Path
import os
from importlib.metadata import version
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
# MelBand inference does not use legacy cuDNN RNN/MHA, multi-GPU solvers,
# host profiling, cuRAND, FFTW compatibility or the alternate NVRTC library.
# Keep cuDNN graph/engines/ops: they provide our fast attention backend.
# A full runtime remains available for debugging and future model changes.
slim_torch_dlls = {
    'cudnn_adv64_9.dll', 'cusolvermg64_11.dll', 'curand64_10.dll',
    'nvperf_host.dll', 'nvrtc64_120_0.alt.dll', 'cufftw64_11.dll',
}
if os.environ.get('STEMFLOW_FULL_RUNTIME') != '1':
    if version('torch') != '2.14.1+cu126':
        raise RuntimeError('Revalidate the slim runtime for this PyTorch version, or set STEMFLOW_FULL_RUNTIME=1.')
    removed = [item for item in a.binaries + a.datas if Path(item[0]).name.lower() in slim_torch_dlls]
    print('Slim runtime: excluding', len(removed), 'optional DLLs,',
          round(sum(Path(item[1]).stat().st_size for item in removed) / 1024**2, 1), 'MiB')
    a.binaries = [item for item in a.binaries if Path(item[0]).name.lower() not in slim_torch_dlls]
    a.datas = [item for item in a.datas if Path(item[0]).name.lower() not in slim_torch_dlls]
pyz = PYZ(a.pure)
gui = EXE(pyz, a.scripts, [], exclude_binaries=True, name='StemFlow', console=False, upx=False)
worker = EXE(pyz, a.scripts, [], exclude_binaries=True, name='StemFlow-worker', console=True, upx=False)
app = COLLECT(gui, worker, a.binaries, a.datas, strip=False, upx=False, name='StemFlow')
