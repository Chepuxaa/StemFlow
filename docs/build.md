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

The script installs PyInstaller in `.venv` and produces `dist/StemFlow/`.
Keep the entire folder together: `StemFlow.exe`, `StemFlow-worker.exe`, and
their shared `_internal` runtime. A single-file bundle would unpack a large
PyTorch runtime each time its worker starts, so the initial recipe uses onedir.
The default build uses the [validated slim CUDA profile](runtime-size.md),
excluding about 469 MiB of optional DLLs. Set `STEMFLOW_FULL_RUNTIME=1` for a
full-runtime diagnostic build. Model or PyTorch changes require revalidation.
The build script adds `Download-model.cmd`, first-run instructions and available
dependency license texts. Keep these files in the distributed folder too.

Model weights are not embedded. Open `StemFlow.exe`: its first-run screen checks
the checkpoint and offers a download with progress, speed and cancellation.
SHA-256 verification completes before processing can start.
The release excludes the FFmpeg executable; setup fetches its pinned upstream
wheel (31 MB) and verifies both the wheel and extracted tool. The installed tool
is stored in `%LOCALAPPDATA%\StemFlow\runtime`. The optional CLI setup is:

```powershell
.\StemFlow-worker.exe --download-model
.\StemFlow.exe
```

The model is stored in `%LOCALAPPDATA%\StemFlow\models`. Resource assets are
read from the bundle; settings, reports and scratch audio remain outside it.

For local model-download regression tests (no real weights or internet required):

```powershell
.\.venv\Scripts\python.exe scripts/test_model_download.py
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
