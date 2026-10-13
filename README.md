<p align="center"><strong>English</strong> · <a href="README.ru.md">Русский</a></p>

<p align="center"><img src="docs/assets/banner.svg" alt="StemFlow — four stems, your next set" width="100%"></p>

<p align="center">
<img src="https://img.shields.io/badge/status-alpha-ff5400?style=flat-square" alt="Alpha">
<img src="https://img.shields.io/badge/platform-Windows-292929?style=flat-square" alt="Windows">
<img src="https://img.shields.io/badge/runtime-TensorRT%20%2B%20ONNX-292929?style=flat-square" alt="TensorRT + ONNX">
<img src="https://img.shields.io/badge/interface-EN%20%2F%20RU-292929?style=flat-square" alt="EN / RU">
<img src="https://img.shields.io/badge/license-MIT-292929?style=flat-square" alt="MIT">
</p>

<p align="center"><strong>One track. Four parts. Ready for your next set.</strong><br>
An open-source desktop stem generator for Traktor Pro 4.</p>

<p align="center"><a href="https://github.com/Chepuxaa/StemFlow/releases/tag/v1.0.0-alpha.2"><strong>Download for Windows</strong></a> · <a href="#quick-start">Quick start</a> · <a href="docs/build.md">Build from source</a></p>

## Features

| Feature | Details |
|---|---|
| **Four stems** | Drums, Bass, Other and Vocals with MelBand 4-stem SYH v2 |
| **GPU acceleration** | TensorRT for RTX, with reusable engine caches |
| **CPU support** | ONNX Runtime; optional Fast CPU mode uses INT8 linear layers |
| **Auto mode** | Prefers GPU; handled CUDA failures restart the track on CPU |
| **Batch processing** | Files or folders, cover art, cancellation and retry; model reuse across the queue |
| **Traktor export** | Original master + four stems in `.stem.mp4`, five stereo AAC streams targeting 320 kbps each |
| **Artwork and tags** | Preserve supported metadata; optional StemFlow cover badge |
| **Personal settings** | Stem colors, 50% / 75% overlap, 6 / 11-second chunks, English / Russian |
| **Your files** | Choose the destination, optionally retain WAVs or replace tracks with original backups |

The master bypasses the separation model. No normalization, compression or limiter
is applied; the sum of separated stems can differ from the original.
Processing runs locally. Internet is needed for initial setup downloads.
Serato export is not implemented yet.

## Quick start

1. Download **`StemFlow.exe`** from [the application release](https://github.com/Chepuxaa/StemFlow/releases/tag/v1.0.0-alpha.2).
2. Run it. **One EXE** — no separate worker, `_internal` folder or Python installation.
3. Download the model when prompted, with progress and SHA-256 integrity checks.
4. Choose an output folder, add tracks, select **Auto**, **CUDA** or **CPU**, and start the queue.
5. Load the exported `.stem.mp4` into a Traktor Stem Deck.

The EXE is approximately **142 MB** (136 MiB). Setup separately downloads the
**1.92 GB model** and an audio tool of approximately **31 MB**. First GPU use
prepares a hardware-specific engine and needs additional time and disk space.
First Fast CPU use creates a local cache of approximately **0.94 GB** without
downloading another model. The EXE temporarily extracts its embedded runtime at
launch, so installed disk usage exceeds the EXE file size.

### Requirements and settings

- **Windows x64** with [Microsoft Edge WebView2 Runtime](https://developer.microsoft.com/microsoft-edge/webview2/).
- **GPU:** compatible NVIDIA RTX card and driver; tested on RTX 3070, 8 GB VRAM.
- **RAM:** tested with 16 GB. Model preparation needs substantial free memory.
- **CPU:** supported, but substantially slower. Fast CPU is enabled by default in the GUI; disable it for original CPU precision. INT8 can slightly change the audio.
- **Overlap:** 75% uses more passes; 50% reduces work. Compare results on your music.
- **Chunks:** 11 seconds by default; 6 seconds reduces GPU memory requirements.

PyTorch and the full CUDA Toolkit are **not required**. Auto handles recoverable
GPU errors; a fatal native engine crash requires a retry or manual CPU selection.
This is an alpha release: broader hardware testing is ongoing.

## Output and backups

Existing Stem files are never overwritten. Tags and artwork support depends on
the source format. The cover badge affects exported artwork only. Stem colors are
written to the NI container; their appearance depends on Traktor's color mode.

**Replace in source folder** validates the export before archiving the original:

```text
Music/
├── Track.stem.mp4
└── .stemflow-originals/
    └── Track.mp3
```

Restore a track by moving it out of `.stemflow-originals`. Backups and generated
Stem files are excluded from subsequent imports.

## Data locations

| Data | Location |
|---|---|
| Model and derived CPU caches | `%LOCALAPPDATA%\StemFlow\models\melband-4stem-syh-v2` |
| GPU engine caches | `%LOCALAPPDATA%\StemFlow\engines` |
| Downloaded audio tool | `%LOCALAPPDATA%\StemFlow\runtime` |
| Settings, queue and reports | `%LOCALAPPDATA%\StemFlow` |
| Temporary audio | `%TEMP%\StemFlow`; cleaned after completion or cancellation |
| Finished files | Your selected destination |
| Optional WAVs | `<track>-stems` beside the finished file |

Models and engines do not live beside the EXE. Deleting engine caches while the
app is closed causes them to be rebuilt on next GPU use.

## Run from source

Use **Python 3.14 x64**; the current build uses Python 3.14.8. Open PowerShell in
the repository directory:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --no-cache-dir -r requirements/app.lock.txt
.\.venv\Scripts\python.exe stemflow.py
```

Dependencies stay in `.venv`. The GUI installs the model when needed.
`Start-Stemgen.cmd` is an alternative launcher. Manual model setup:

```powershell
.\.venv\Scripts\python.exe scripts/download_model.py
.\.venv\Scripts\python.exe scripts/download_model.py --verify-only
```

Weights are in [a separate model release](https://github.com/Chepuxaa/StemFlow/releases/tag/models-melband4-v2-onnx),
not Git or the EXE. The ONNX bundle derives from the pinned
[SYH99999 checkpoint](https://huggingface.co/SYH99999/MelBandRoformer4StemFTLarge).
Sources, sizes and checksums are recorded in `config/model.json`.

### Command line

```powershell
.\.venv\Scripts\python.exe separate.py "D:\Music\Track.mp3" --seconds 0 --device auto --output-dir "D:\Music\Stems" --discard-wavs --overlap 75 --cpu-fast
```

`--seconds 0` processes the entire track. WAVs are retained unless `--discard-wavs`
is passed. Use `--replace-original` instead of `--output-dir` for source replacement.
`--cpu-fast` enables INT8 for CPU only; without it the CLI uses original CPU precision.
Add `--watermark-cover` to stamp exported artwork.

### Development

```powershell
.\.venv\Scripts\python.exe scripts/check_repository.py
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

[Windows EXE build](docs/build.md) · [Contributing](CONTRIBUTING.md)

## License and credits

Developer and designer: **[@Chepuxaa](https://github.com/Chepuxaa)**.
Built with assistance from **OpenAI Codex**.

Original code is [MIT-licensed](LICENSE). Model weights and third-party components
retain their own licenses; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

Thanks to **SYH99999** for the weights,
[Music Source Separation Training](https://github.com/ZFTurbo/Music-Source-Separation-Training)
for the architecture, and the ONNX Runtime, NVIDIA, pywebview and Roboto teams.
StemFlow is independent and is not affiliated with Native Instruments.
