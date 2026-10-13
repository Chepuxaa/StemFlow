"""Windows single-file build with TensorRT RTX + ONNX CPU, no PyTorch."""
from pathlib import Path
import os
import sys
from PyInstaller.utils.hooks import collect_all, collect_dynamic_libs, copy_metadata

root = Path(SPECPATH).parent
sys.path.insert(0, str(root))
from scripts.prepare_release import collect_licenses
from scripts.build_icon import build_icon
from scripts.build_watermark import build_watermark
build_watermark(root / 'ui/assets/watermark.svg', root / 'ui/assets/watermark.png')
icon = build_icon(root / 'ui/assets/icon.svg', root / 'ui/assets/icon.ico')
embedded_licenses = root / 'build/embedded-licenses'
collect_licenses(embedded_licenses)
datas = [(str(root / 'ui'), 'ui'), (str(root / 'config'), 'config'),
         (str(root / 'LICENSE'), '.'), (str(root / 'THIRD_PARTY_NOTICES.md'), '.'),
         (str(embedded_licenses), 'THIRD_PARTY_LICENSES')]
binaries, hiddenimports = [], []
for package in ('imageio_ffmpeg', 'webview', 'tensorrt_rtx',
                'tensorrt_rtx_bindings', 'tensorrt_rtx_libs'):
    package_datas, package_binaries, package_imports = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_imports
from PyInstaller.utils.hooks import collect_data_files
datas += collect_data_files('certifi')
binaries += collect_dynamic_libs('onnxruntime')
hiddenimports += ['onnxruntime.capi.onnxruntime_pybind11_state']
for package in ('onnxruntime', 'tensorrt-rtx-cu13', 'tensorrt-rtx-cu13-bindings', 'tensorrt-rtx-cu13-libs'):
    datas += copy_metadata(package)
datas = [item for item in datas if not ('imageio_ffmpeg' in item[0] and item[0].endswith('.exe'))]
binaries = [item for item in binaries if not ('imageio_ffmpeg' in item[0] and item[0].endswith('.exe'))]
a = Analysis([str(root / 'stemflow.py')], pathex=[str(root)], binaries=binaries,
             datas=datas, hiddenimports=hiddenimports, hookspath=[], runtime_hooks=[],
             excludes=['tkinter', 'PyQt5', 'PyQt6', 'PySide2', 'PySide6', 'torch', 'torchvision',
                       'torchaudio', 'librosa', 'numba', 'scipy', 'sympy', 'onnxscript', 'onnx_ir'],
             noarchive=False)
a.datas = [item for item in a.datas if not ('imageio_ffmpeg' in item[0] and item[0].endswith('.exe'))]
a.binaries = [item for item in a.binaries if not ('imageio_ffmpeg' in item[0] and item[0].endswith('.exe'))]
pyz = PYZ(a.pure)
if os.environ.get('STEMFLOW_ONEDIR') == '1':
    gui = EXE(pyz, a.scripts, [], exclude_binaries=True, name='StemFlow', console=False, upx=False, icon=str(icon))
    worker = EXE(pyz, a.scripts, [], exclude_binaries=True, name='StemFlow-worker', console=True, upx=False)
    app = COLLECT(gui, worker, a.binaries, a.datas, strip=False, upx=False, name='StemFlow')
else:
    app = EXE(pyz, a.scripts, a.binaries, a.datas, [], name='StemFlow', console=False, upx=False, icon=str(icon))
