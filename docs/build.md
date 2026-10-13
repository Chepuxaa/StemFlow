# Windows EXE build — experimental

The first EXE bundle was built and checked on the development Windows machine:
native window startup, device probing, CUDA/CPU exports, Auto with CUDA hidden,
queued tracks, model reuse, error continuation and worker cancellation.
Model setup was also exercised in the native GUI using a local test download:
RU/EN, download progress, cancellation, retry and verified completion.
It is an alpha build; clean-machine validation is still required before a broad release.

## Build

On Windows, finish the source setup from the README, then run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/build.ps1
```

The default build produces a single `dist/StemFlow.exe`, with libraries and
license texts embedded. It temporarily extracts its runtime when launched.
The GUI starts the same EXE in worker mode, reusing the parent extraction.
Models and compiled GPU engines remain in AppData. Set `STEMFLOW_ONEDIR=1`
to build the previous folder layout for development.
The bundle uses TensorRT for RTX and CPU ONNX
Runtime; PyTorch and its CUDA DLLs are excluded. The previous PyTorch runtime
audit is no longer part of the repository. Model or engine updates require revalidation.
Dependency license texts are embedded during the build.

Model weights are not embedded. Open `StemFlow.exe`: its first-run screen checks
all files in the converted ONNX model bundle and offers a download with progress, speed and cancellation.
SHA-256 verification completes before processing can start.
The release excludes the FFmpeg executable; setup fetches its pinned upstream
wheel (31 MB) and verifies both the wheel and extracted tool. The installed tool
is stored in `%LOCALAPPDATA%\StemFlow\runtime`. The optional CLI setup is:

```powershell
.\StemFlow.exe --download-model
.\StemFlow.exe
```

The model is stored in `%LOCALAPPDATA%\StemFlow\models`. Resource assets are
read from the bundle; settings, reports and scratch audio remain outside it.

For source and regression checks:

```powershell
.\.venv\Scripts\python.exe scripts/check_repository.py
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

## Before publishing a binary

- Test startup on a Windows machine without Python installed, with WebView2 Runtime.
- Test CUDA and CPU export, device probing, two queued tracks, cancellation and restart.
- Test folder selection, source replacement with recovery, covers and metadata.
- Inspect PyInstaller warnings for dynamic imports and missing DLLs.
- Include licenses for every bundled dependency; do not add the acquired FFmpeg executable to the release.
- Verify behavior with non-ASCII paths and a read-only installation directory.

Official references: [PyInstaller](https://pyinstaller.org/en/stable/),
[pywebview freezing guide](https://pywebview.flowrl.com/guide/freezing).
