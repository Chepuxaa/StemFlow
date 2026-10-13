# Windows EXE build — experimental

The first EXE bundle was built and checked on the development Windows machine:
native window startup, device probing, CUDA/CPU exports, Auto with CUDA hidden,
queued tracks, model reuse, error continuation and worker cancellation.
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
The build script adds `Download-model.cmd`, first-run instructions and available
dependency license texts. Keep these files in the distributed folder too.

Model weights are not embedded. The intended packaged setup is:

```powershell
.\StemFlow-worker.exe --download-model
.\StemFlow.exe
```

The model is stored in `%LOCALAPPDATA%\StemFlow\models`. Resource assets are
read from the bundle; settings, reports and scratch audio remain outside it.

## Before publishing a binary

- Test startup on a Windows machine without Python installed, with WebView2 Runtime.
- Test CUDA and CPU export, device probing, two queued tracks, cancellation and restart.
- Test folder selection, source replacement with recovery, covers and metadata.
- Inspect PyInstaller warnings for dynamic imports and missing DLLs.
- Include licenses for every bundled dependency and the FFmpeg binary.
- Verify behavior with non-ASCII paths and a read-only installation directory.

Official references: [PyInstaller](https://pyinstaller.org/en/stable/),
[pywebview freezing guide](https://pywebview.flowrl.com/guide/freezing).
