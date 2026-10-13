<p align="center"><a href="README.md">English</a> · <strong>Русский</strong></p>

<p align="center">
  <img src="docs/assets/banner.svg" alt="StemFlow — four stems, your next set" width="100%">
</p>

<p align="center">
  <img src="https://img.shields.io/badge/status-alpha-ff5400?style=flat-square" alt="Alpha">
  <img src="https://img.shields.io/badge/platform-Windows-292929?style=flat-square" alt="Windows">
  <img src="https://img.shields.io/badge/processing-CUDA%20%2F%20CPU-292929?style=flat-square" alt="CUDA / CPU">
  <img src="https://img.shields.io/badge/interface-RU%20%2F%20EN-292929?style=flat-square" alt="RU / EN">
  <img src="https://img.shields.io/badge/license-MIT-292929?style=flat-square" alt="MIT">
</p>

<p align="center"><strong>Из одного трека — в четыре партии и готовый Stem Deck.</strong><br>
Открытый настольный генератор стемов для Traktor Pro 4.</p>

---

## Что умеет StemFlow

| | |
|---|---|
| **Четыре стема** | Drums, Bass, Other, Vocals на MelBand 4-stem SYH v2 |
| **CUDA / CPU / Auto** | В Auto при ошибке CUDA или нехватке VRAM весь трек перезапускается на CPU |
| **Плейлисты** | Импорт файлов и папок, обложки в очереди, отмена и повтор; модель загружается один раз на очередь |
| **Traktor Stem** | Оригинальный мастер + 4 стема, пять стереодорожек AAC с целью 320 кбит/с каждая |
| **Метаданные** | Поддерживаемые теги и обложка переносятся из оригинала |
| **Своя папка** | Выбор места сохранения, запоминание пути, опциональное сохранение WAV |
| **Замена оригиналов** | Stem рядом с треком, оригинал в резервной папке после проверки экспорта |
| **Интерфейс** | RU / EN, Roboto, фиксированное окно с собственными кнопками управления |

Нормализация, компрессор и лимитер отключены. Мастер не проходит через модель;
сумма разделённых стемов может отличаться от оригинала.
Для новых пользователей интерфейс запускается на английском. В Settings можно
переключить язык на русский; сохранённый ранее выбор не сбрасывается.

## Запуск из исходников

**Проверенное окружение:** Windows, Python 3.14.8 x64, PyTorch CUDA 12.6,
RTX 3070 8 ГБ, 16 ГБ RAM. На CPU обработка работает, но заметно медленнее.
Нужен [Microsoft Edge WebView2 Runtime](https://developer.microsoft.com/microsoft-edge/webview2/).

### 1. Окружение

Скачай код репозитория и открой PowerShell в его папке:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --no-cache-dir -r requirements/app.lock.txt
```

Все зависимости остаются внутри `.venv`. FFmpeg входит в imageio-ffmpeg;
отдельная установка FFmpeg для приложения не требуется.

### 2. Модель

```powershell
.\.venv\Scripts\python.exe scripts/download_model.py
```

Скачивается **только SYH v2**, около **3,76 ГБ**. Скрипт проверяет размер и SHA-256.
Веса исключены из Git; конфиг, источник и контрольные суммы находятся в `config/`.
Загрузка идёт напрямую с Hugging Face. GUI проверяет модель при запуске и предлагает
скачать её внутри приложения с прогрессом, скоростью и отменой. Команда выше —
альтернативный способ установки. Установленные веса используются
повторно; после установки зависимостей и весов обработка не требует интернета.

Модель: [SYH99999 / MelBandRoformer4StemFTLarge](https://huggingface.co/SYH99999/MelBandRoformer4StemFTLarge).
Версия и ссылка закреплены на конкретной ревизии, а не на изменяемом `main`.

### 3. Приложение

Открой **`Start-Stemgen.cmd`** или выполни:

```powershell
.\.venv\Scripts\python.exe stemflow.py
```

Для проверки видеокарты:

```powershell
.\.venv\Scripts\python.exe scripts/check_cuda.py
```

## Рабочий процесс

1. Выбери папку сохранения на главном экране или в **Settings → Экспорт**.
2. Добавь треки или целую папку.
3. Выбери **Auto**, **CUDA** или **CPU** и запусти очередь.
4. Открой готовый `.stem.mp4` в Stem Deck Traktor.

Фрагменты по 11 секунд используются по умолчанию; 6 секунд уменьшают расход VRAM.
Готовые Stem-файлы не перезаписываются.

### Замена файлов в исходной папке

В Settings выбери **«Заменить в исходной папке»**. Перед переносом оригинала
приложение проверяет пять аудиодорожек и копию контейнера.

```text
Music/
├── Track.stem.mp4
└── .stemflow-originals/
    └── Track.mp3
```

Для восстановления перенеси оригинал из `.stemflow-originals` обратно.
Резервные копии и готовые Stem-файлы исключены из повторного импорта.

## Командная строка

```powershell
.\.venv\Scripts\python.exe separate.py "D:\Music\Track.mp3" --seconds 0 --device auto --output-dir "D:\Music\Stems" --discard-wavs
```

`--seconds 0` — весь трек. В CLI WAV сохраняются, если не передать
`--discard-wavs`. Для замены полного трека используй `--replace-original`
вместо `--output-dir`.

## Где лежат данные

| Данные | Каталог |
|---|---|
| Настройки, очередь, отчёты, кэш окна | `%LOCALAPPDATA%\StemFlow` |
| Временное аудио | `%TEMP%\StemFlow`, очищается после обработки или отмены |
| Готовые файлы | Выбранная пользователем папка |
| Сохранённые WAV | `<название>-stems` рядом с готовым файлом |
| Веса при запуске исходников | `models/melband-4stem-syh-v2` |
| Веса в EXE-сборке | `%LOCALAPPDATA%\StemFlow\models` |

## Разработка и EXE

```powershell
.\.venv\Scripts\python.exe scripts/check_repository.py
```

[Contributing](CONTRIBUTING.md) · [Инструкция сборки EXE](docs/build.md)

В EXE-сборке модель скачивается через интерфейс приложения и хранится в
`%LOCALAPPDATA%\StemFlow\models\melband-4stem-syh-v2`.

Первая **альфа-сборка Windows** создана и проверена на компьютере разработчика:
запуск GUI, разделение на CUDA и CPU, Auto без CUDA, очередь, переиспользование
модели и отмена обработчика. Проверка на чистой Windows и большем наборе треков
ещё нужна. Публичный бинарный релиз пока не опубликован.

Распакуй всю папку с `StemFlow.exe`, `StemFlow-worker.exe` и `_internal`.
Python уже включён. Запусти `StemFlow.exe`: приложение проверит модель и предложит
скачать её с прогрессом, скоростью и отменой. Отдельный скрипт не нужен.

```text
stemflow.py           входная точка GUI / worker
desktop.py           окно, очередь, обложки и настройки
separate.py           обработка трека и протокол очереди
model_runtime.py      модель и кэш на очередь
ni_stem.py            NI Stem контейнер
audio_metadata.py     обложки и теги
file_output.py        проверка и замена оригиналов
app_paths.py          ресурсы, данные и временные файлы
ui/                   HTML, CSS, JS, логотип и шрифт
config/               конфиг и манифест модели
vendor/msst/          закреплённая архитектура и лицензия
scripts/              загрузка модели, проверки и сборка
packaging/            рецепт PyInstaller
```

## Лицензия и благодарности

Разработчик и дизайнер: **[@Chepuxaa](https://github.com/Chepuxaa)**.

Разработано при содействии **OpenAI Codex**.

Оригинальный код — [MIT](LICENSE). Сторонние компоненты и веса сохраняют свои
лицензии: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

Спасибо автору весов **SYH99999**, проекту
[Music Source Separation Training](https://github.com/ZFTurbo/Music-Source-Separation-Training)
и разработчикам PyTorch, pywebview и Roboto.

StemFlow — независимый проект, не связанный с Native Instruments.
