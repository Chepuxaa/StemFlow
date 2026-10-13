<p align="center"><a href="README.md">English</a> · <strong>Русский</strong></p>

<p align="center"><img src="docs/assets/banner.svg" alt="StemFlow — четыре стема для следующего сета" width="100%"></p>

<p align="center">
<img src="https://img.shields.io/badge/status-alpha-ff5400?style=flat-square" alt="Alpha">
<img src="https://img.shields.io/badge/platform-Windows-292929?style=flat-square" alt="Windows">
<img src="https://img.shields.io/badge/runtime-TensorRT%20%2B%20ONNX-292929?style=flat-square" alt="TensorRT + ONNX">
<img src="https://img.shields.io/badge/interface-EN%20%2F%20RU-292929?style=flat-square" alt="EN / RU">
<img src="https://img.shields.io/badge/license-MIT-292929?style=flat-square" alt="MIT">
</p>

<p align="center"><strong>Один трек. Четыре партии. Готово для следующего сета.</strong><br>
Открытый настольный генератор стемов для Traktor Pro 4.</p>

<p align="center"><a href="https://github.com/Chepuxaa/StemFlow/releases/tag/v1.0.0-alpha.2"><strong>Скачать для Windows</strong></a> · <a href="#быстрый-старт">Быстрый старт</a> · <a href="docs/build.md">Сборка из исходников</a></p>

## Возможности

| Возможность | Подробности |
|---|---|
| **Четыре стема** | Барабаны, бас, остальное и вокал на MelBand 4-stem SYH v2 |
| **Ускорение на GPU** | TensorRT for RTX, повторное использование подготовленных движков |
| **Обработка на CPU** | ONNX Runtime; «Быстрый CPU» использует INT8 для линейных слоёв |
| **Auto** | Предпочитает GPU; при обрабатываемой ошибке CUDA перезапускает трек на CPU |
| **Очередь** | Файлы и папки, обложки, отмена и повтор; модель остаётся загруженной на очередь |
| **Экспорт в Traktor** | Оригинальный мастер + четыре стема в `.stem.mp4`, пять стереодорожек AAC с целевым битрейтом 320 кбит/с каждая |
| **Обложки и теги** | Перенос поддерживаемых метаданных; необязательная плашка StemFlow |
| **Настройки** | Цвета стемов, перекрытие 50% / 75%, фрагменты 6 / 11 секунд, английский / русский |
| **Свои файлы** | Выбор папки, WAV по желанию, замена треков с резервными копиями оригиналов |

Мастер не проходит через модель. Нормализация, компрессор и лимитер отключены;
сумма стемов может отличаться от оригинала. Обработка локальная, интернет нужен
для первоначальной загрузки компонентов. Экспорт для Serato пока не реализован.

## Быстрый старт

1. Скачай **`StemFlow.exe`** из [релиза приложения](https://github.com/Chepuxaa/StemFlow/releases/tag/v1.0.0-alpha.2).
2. Запусти. Нужен **один EXE** — без отдельного обработчика, `_internal` и установки Python.
3. Скачай модель через приложение: есть прогресс и проверка SHA-256.
4. Выбери папку, добавь треки, укажи **Auto**, **CUDA** или **CPU** и запусти очередь.
5. Открой `.stem.mp4` в Stem Deck Traktor.

EXE занимает примерно **142 МБ** (136 МиБ). Отдельно скачиваются **модель 1,92 ГБ**
и аудиоинструмент около **31 МБ**. При первом использовании GPU готовится движок
под видеокарту — нужны время и дополнительное место. «Быстрый CPU» создаёт
локальный кэш примерно **0,94 ГБ**, без новой загрузки модели. EXE временно
распаковывает библиотеки при запуске; использование диска превышает размер EXE.

### Требования и настройки

- **Windows x64**, [Microsoft Edge WebView2 Runtime](https://developer.microsoft.com/microsoft-edge/webview2/).
- **GPU:** совместимая NVIDIA RTX и драйвер; проверено на RTX 3070 с 8 ГБ VRAM.
- **RAM:** проверено с 16 ГБ; подготовке модели нужна свободная память.
- **CPU:** поддерживается, но существенно медленнее GPU. «Быстрый CPU» включён в GUI по умолчанию; отключение возвращает исходную точность. INT8 может немного менять звук.
- **Перекрытие:** 75% — больше проходов, 50% — меньше вычислений. Сравни на своих треках.
- **Фрагменты:** по умолчанию 11 секунд; 6 секунд уменьшают требования к видеопамяти.

PyTorch и полный CUDA Toolkit **не нужны**. Auto восстанавливается после
обрабатываемых ошибок GPU; аварийное завершение нативного движка требует повтора
или ручного выбора CPU. Это альфа: проверка на большем числе компьютеров продолжается.
Первоначальный язык — английский; переключение на русский сохраняется.

## Экспорт и резервные копии

Готовые Stem-файлы не перезаписываются. Поддержка тегов и обложки зависит от
формата источника. Плашка меняет только экспортированную обложку. Цвета стемов
записываются в NI-контейнер; отображение зависит от режима цвета в Traktor.

**«Заменить в исходной папке»** проверяет экспорт перед переносом оригинала:

```text
Music/
├── Track.stem.mp4
└── .stemflow-originals/
    └── Track.mp3
```

Для восстановления перенеси оригинал из `.stemflow-originals` обратно.
Резервные копии и готовые Stem-файлы исключены из повторного импорта.

## Где лежат данные

| Данные | Каталог |
|---|---|
| Модель и кэш CPU | `%LOCALAPPDATA%\StemFlow\models\melband-4stem-syh-v2` |
| Движки GPU | `%LOCALAPPDATA%\StemFlow\engines` |
| Аудиоинструмент | `%LOCALAPPDATA%\StemFlow\runtime` |
| Настройки, очередь, отчёты | `%LOCALAPPDATA%\StemFlow` |
| Временное аудио | `%TEMP%\StemFlow`, очищается после обработки или отмены |
| Готовые файлы | Выбранная папка |
| Необязательные WAV | `<название>-stems` рядом с готовым файлом |

Модели и движки не лежат рядом с EXE. Удаление кэша движков при закрытом приложении
приведёт к его повторной подготовке при следующей обработке на GPU.

## Запуск из исходников

Нужен **Python 3.14 x64**; текущая сборка использует Python 3.14.8.
Открой PowerShell в папке репозитория:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --no-cache-dir -r requirements/app.lock.txt
.\.venv\Scripts\python.exe stemflow.py
```

Зависимости остаются внутри `.venv`. Модель устанавливается через GUI.
Альтернативный запуск — `Start-Stemgen.cmd`. Ручная установка модели:

```powershell
.\.venv\Scripts\python.exe scripts/download_model.py
.\.venv\Scripts\python.exe scripts/download_model.py --verify-only
```

Веса находятся в [отдельном релизе модели](https://github.com/Chepuxaa/StemFlow/releases/tag/models-melband4-v2-onnx),
а не в Git или EXE. Используется конвертированный
[checkpoint SYH99999](https://huggingface.co/SYH99999/MelBandRoformer4StemFTLarge).
Источники, размеры и контрольные суммы закреплены в `config/model.json`.

### Командная строка

```powershell
.\.venv\Scripts\python.exe separate.py "D:\Music\Track.mp3" --seconds 0 --device auto --output-dir "D:\Music\Stems" --discard-wavs --overlap 75 --cpu-fast
```

`--seconds 0` — весь трек. WAV сохраняются, если не передать `--discard-wavs`.
Для замены оригинала используй `--replace-original` вместо `--output-dir`.
`--cpu-fast` включает INT8 только на CPU; без него CLI использует исходную точность.
`--watermark-cover` добавляет плашку на экспортированную обложку.

### Разработка

```powershell
.\.venv\Scripts\python.exe scripts/check_repository.py
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

[Сборка Windows EXE](docs/build.md) · [Contributing](CONTRIBUTING.md)

## Лицензия и благодарности

Разработчик и дизайнер: **[@Chepuxaa](https://github.com/Chepuxaa)**.
Разработано при содействии **OpenAI Codex**.

Оригинальный код — [MIT](LICENSE). Веса и сторонние компоненты сохраняют свои
лицензии: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

Спасибо **SYH99999** за веса,
[Music Source Separation Training](https://github.com/ZFTurbo/Music-Source-Separation-Training)
за архитектуру, командам ONNX Runtime, NVIDIA, pywebview и Roboto.
StemFlow — независимый проект, не связанный с Native Instruments.
