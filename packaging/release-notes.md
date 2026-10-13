# StemFlow v1.0.0-alpha.2

## Download and run

Download **StemFlow.exe** and launch it. This is one Windows x64 executable;
no separate worker, `_internal` folder or Python installation is required.
Microsoft Edge WebView2 Runtime is required for the GUI.

Setup downloads and verifies the **1.92 GB ONNX model** and an audio tool
(approximately **31 MB**). Model files are separate release assets and are
installed automatically by the app. Processing then works offline.

## Changes

- Replaced the PyTorch application runtime with TensorRT for RTX on GPU and ONNX Runtime on CPU.
- Added Fast CPU mode using local INT8 linear-layer conversion, enabled by default in the GUI. Disable it for original CPU precision; audio can slightly differ.
- Added a single 50% / 75% overlap setting for both devices and 6 / 11-second chunks.
- Improved GPU engine loading and limited engine preparation concurrency to reduce memory pressure.
- Fixed certificate verification during setup using native system trust and bundled CA certificates, without disabling TLS verification.
- Added optional StemFlow cover artwork branding and configurable stem colors with a compact color picker.
- Fixed taskbar minimization for the frameless window.
- Replaced raw worker crash output with readable errors and diagnostic reports.
- Rewrote English and Russian documentation and removed unused PyTorch conversion sources.

## Storage and requirements

The EXE temporarily extracts its runtime at launch. Models, settings and caches
live under `%LOCALAPPDATA%\StemFlow`, not beside the EXE.
First GPU use prepares a hardware-specific engine. First Fast CPU use prepares
approximately **0.94 GB** of local cache without another model download.

GPU processing requires a compatible NVIDIA RTX card and driver. CPU is supported
but substantially slower. Tested with RTX 3070 8 GB and 16 GB RAM; broader hardware
testing is ongoing. Auto can fall back after handled CUDA errors; fatal native
engine crashes require retry or manual CPU selection. Serato export is not yet implemented.

## Русский

Скачай и запусти **StemFlow.exe** — нужен один файл, без `_internal`, обработчика
и установки Python. Для интерфейса нужен Microsoft Edge WebView2 Runtime.
Приложение скачает модель **1,92 ГБ** и аудиоинструмент около **31 МБ**.

В этой версии: TensorRT + ONNX вместо PyTorch, быстрый CPU с INT8, выбор
перекрытия, плашка на обложке, цвета стемов, исправления сворачивания, загрузки
модели и подготовки GPU. INT8 может немного менять звук; его можно отключить.
CPU заметно медленнее GPU. Это альфа; экспорт для Serato пока не реализован.

Developer and designer: [@Chepuxaa](https://github.com/Chepuxaa).
Built with assistance from OpenAI Codex.
