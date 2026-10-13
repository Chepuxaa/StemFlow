## StemFlow for Windows x64

An open-source stem generator for Traktor Pro 4, by developer and designer **@Chepuxaa**.

- MelBand 4-stem SYH v2: Drums, Bass, Other and Vocals.
- CUDA, CPU and Auto with CPU fallback.
- Playlist queue, artwork, metadata, cancellation and retry.
- Original master and four AAC stems, targeting 320 kbps per stream.
- In-app model download with progress, speed and integrity verification.
- English by default, with Russian available in Settings.

### Install

1. Download the Windows archive. If it has `.001` and `.002` parts, download both to the same folder and extract `.001` with [7-Zip](https://www.7-zip.org/).
2. Keep the entire extracted `StemFlow` folder together.
3. Launch **StemFlow.exe**. Python is included. Keep the worker EXE and `_internal` beside it.
4. First-run setup downloads the model (3.76 GB) and audio tool (about 31 MB) from their pinned upstream sources. Processing then works offline.
5. Choose a destination folder, add tracks and start the queue.

Requires Windows x64 and Microsoft Edge WebView2 Runtime. CUDA needs a compatible NVIDIA driver. Tested on RTX 3070 8 GB, 16 GB RAM; CPU mode is available.

This is a **prerelease**, checked on the development Windows PC. Clean-machine testing is still needed. The included `SHA256SUMS.txt` lists release file checksums.

### Русский

Скачай архив приложения. Если он разделён на части `.001` и `.002`, положи обе в одну папку и распакуй `.001` через 7-Zip. Запускай **StemFlow.exe**, сохрани рядом обработчик и `_internal`. Устанавливать Python отдельно не нужно.

Приложение само предложит загрузку модели и аудиоинструмента. После установки интернет для обработки не нужен. Русский язык выбирается в Settings. Модель и настройки лежат в `%LOCALAPPDATA%\StemFlow` и сохраняются при обновлении приложения.
