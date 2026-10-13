"""Native desktop window with a local HTML UI and sequential CUDA workers."""

import copy
import base64
import ctypes
from collections import deque
import json
import os
import platform
from pathlib import Path
import subprocess
import sys
import threading
import uuid

import webview
import mutagen
from mutagen.id3 import ID3
from mutagen.mp4 import MP4
from webview.dom import DOMEventHandler
from file_output import BACKUP_FOLDER
from app_paths import DATA_DIR, MODEL_DIR, RESOURCE_DIR, cleanup_run_directory, worker_command
from scripts.download_model import (DownloadCancelled, checkpoint_fingerprint,
                                    download_checkpoint, model_manifest, verify_checkpoint)
import audio_runtime

ROOT = RESOURCE_DIR
EXTENSIONS = {".mp3", ".wav", ".flac", ".m4a", ".mp4", ".aif", ".aiff", ".ogg", ".opus"}
NO_WINDOW = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


class DesktopAPI:
    def __init__(self, state_file=None, worker_script=None):
        self._window = None
        self._lock = threading.RLock()
        self._process = None
        self._busy = False
        self._stop = threading.Event()
        self._state_file = Path(state_file) if state_file else DATA_DIR / 'queue.json'
        self._worker_script = Path(worker_script) if worker_script else ROOT / "separate.py"
        self._jobs = []
        self._covers = {}
        self._settings = {"keep_wavs": False, "chunk_seconds": 11, "device": "auto", "language": "en", "output_mode": "output", "output_directory": ""}
        self._notice = ""
        self._model_cancel = threading.Event()
        self._model_thread = None
        self._model_fingerprint = None
        self._model = {'stage': 'checking', 'received': 0, 'total': model_manifest()['weights_bytes'],
                       'speed': 0, 'error': '', 'active': False, 'cancelling': False}
        saved_file = self._state_file
        if state_file is None and not saved_file.exists() and (ROOT / '.cache/queue.json').exists():
            saved_file = ROOT / '.cache/queue.json'
        if saved_file.exists():
            try:
                saved = json.loads(saved_file.read_text(encoding="utf-8"))
                self._settings.update(saved.get("settings", {}))
                if self._settings.get('device') not in ('auto', 'cuda', 'cpu'):
                    self._settings['device'] = 'auto'
                if self._settings.get('language') not in ('ru', 'en'):
                    self._settings['language'] = 'en'
                if self._settings.get('output_mode') not in ('output', 'replace'):
                    self._settings['output_mode'] = 'output'
                if not isinstance(self._settings.get('output_directory'), str):
                    self._settings['output_directory'] = ''
                self._jobs = saved.get("jobs", [])
                for job in self._jobs:
                    if job["status"] == "running":
                        job.update(status="pending", stage="waiting", progress=0)
            except (ValueError, KeyError, TypeError):
                self._notice = "Не удалось восстановить предыдущую очередь."

    def _save(self):
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._state_file.with_suffix(".tmp")
        temporary.write_text(json.dumps({"jobs": self._jobs, "settings": self._settings},
                                        ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self._state_file)

    def get_state(self):
        with self._lock:
            return copy.deepcopy({"jobs": self._jobs, "settings": self._settings,
                                  "busy": self._busy, "stopping": self._stop.is_set() and self._busy,
                                  "notice": self._translated_notice(), "model": self._model})

    def _model_progress(self, **event):
        with self._lock:
            self._model.update(event)

    def _start_model_task(self, download=False):
        with self._lock:
            if self._busy or self._model['active']:
                return self.get_state()
            self._model_cancel.clear()
            self._model_fingerprint = None
            self._model.update(stage='downloading' if download else 'checking', received=0,
                               total=model_manifest()['weights_bytes'],
                               speed=0, error='', active=True, cancelling=False)
            # Let cancellation finish cleaning its partial file when the window closes.
            self._model_thread = threading.Thread(target=self._run_model_task, args=(download,), daemon=False)
            self._model_thread.start()
        return self.get_state()

    def _run_model_task(self, download):
        target = MODEL_DIR / 'ver2.ckpt'
        manifest = model_manifest()
        try:
            if download and not verify_checkpoint(target, manifest, self._model_progress, self._model_cancel):
                download_checkpoint(target, manifest, self._model_progress, self._model_cancel)
            elif not download:
                before = checkpoint_fingerprint(target) if target.is_file() else None
                valid = verify_checkpoint(target, manifest, self._model_progress, self._model_cancel)
                if not valid or before != checkpoint_fingerprint(target):
                    self._model_progress(stage='invalid' if target.exists() else 'missing')
                    return
            if not audio_runtime.available():
                if not download:
                    self._model_progress(stage='tools_missing', received=0,
                                         total=audio_runtime.manifest()['weights_bytes'])
                    return
                audio_runtime.install(self._model_progress, self._model_cancel)
            with self._lock:
                self._model_fingerprint = checkpoint_fingerprint(target)
                self._model.update(stage='ready', received=manifest['weights_bytes'], speed=0)
        except DownloadCancelled:
            self._model_progress(stage='cancelled', speed=0)
        except Exception as exc:
            self._model_progress(stage='cancelled' if self._model_cancel.is_set() else 'failed',
                                 error='' if self._model_cancel.is_set() else str(exc), speed=0)
        finally:
            self._model_progress(active=False, cancelling=False)

    def check_model(self):
        return self._start_model_task()

    def download_model(self):
        with self._lock:
            if self._model['stage'] == 'ready':
                return self.get_state()
        return self._start_model_task(download=True)

    def cancel_model(self):
        with self._lock:
            if self._model['active']:
                self._model_cancel.set()
                self._model['cancelling'] = True
        return self.get_state()

    def shutdown(self):
        self.cancel_model()
        if self.get_state()['busy']:
            self.cancel()

    def _translated_notice(self):
        if self._settings['language'] == 'ru':
            return self._notice
        messages = {
            'Не удалось восстановить предыдущую очередь.': 'Could not restore the previous queue.',
            'Новых поддерживаемых треков не найдено.': 'No new supported tracks found.',
            'Очередь запущена.': 'Queue started.',
            'Останавливаю текущий трек. Остальные останутся в очереди.': 'Stopping this track. Remaining tracks stay queued.',
            'Очередь остановлена.': 'Queue stopped.',
            'Очередь обработана.': 'Queue finished.',
            'CUDA недоступна: обработка продолжается на CPU.': 'CUDA unavailable: continuing on CPU.',
            'Выбери папку сохранения в настройках.': 'Choose a destination folder in Settings.',
        }
        if self._notice.startswith('Добавлено треков: '):
            return 'Tracks added: ' + self._notice.split(': ', 1)[1]
        return messages.get(self._notice, self._notice)

    def set_language(self, language):
        with self._lock:
            if language not in ('ru', 'en'):
                raise ValueError('Language must be ru or en.')
            self._settings['language'] = language
            self._save()
        return self.get_state()

    def add_files(self, paths):
        added = 0
        with self._lock:
            existing = {j["path"].casefold() for j in self._jobs if j["status"] in ("pending", "running")}
            for value in paths:
                path = Path(value).resolve()
                if BACKUP_FOLDER in path.parts:
                    continue
                if not path.is_file() or path.suffix.lower() not in EXTENSIONS or path.name.lower().endswith((".stem.mp4", ".stem.m4a")):
                    continue
                if str(path).casefold() in existing:
                    continue
                existing.add(str(path).casefold())
                self._jobs.append({"id": uuid.uuid4().hex, "path": str(path), "name": path.name,
                                   "status": "pending", "stage": "waiting", "progress": 0,
                                   "output": None, "error": "", "report": None})
                added += 1
            self._notice = f"Добавлено треков: {added}" if added else "Новых поддерживаемых треков не найдено."
            self._save()
        return self.get_state()

    def choose_files(self):
        paths = self._window.create_file_dialog(webview.FileDialog.OPEN, allow_multiple=True,
                   directory=str(Path.home()), file_types=(("Audio" if self._settings['language'] == 'en' else "Аудио") + " (*.mp3;*.wav;*.flac;*.m4a;*.mp4;*.aif;*.aiff;*.ogg;*.opus)",))
        return self.add_files(paths or [])

    def choose_folder(self):
        folders = self._window.create_file_dialog(webview.FileDialog.FOLDER)
        if folders:
            # Folder imports include subfolders, sorted consistently.
            return self.add_files(str(path) for path in sorted(Path(folders[0]).rglob("*")) if path.is_file())
        return self.get_state()

    def choose_output_directory(self):
        with self._lock:
            if self._busy:
                raise ValueError('Stop the queue before changing the destination.')
        folders = self._window.create_file_dialog(webview.FileDialog.FOLDER,
                                                directory=self._settings['output_directory'] or str(Path.home()))
        if folders:
            folder = Path(folders[0]).resolve()
            if not folder.is_dir():
                raise ValueError('Destination is not a folder.')
            probe = folder / f'.stemflow-{uuid.uuid4().hex}.tmp'
            with probe.open('xb') as stream:
                stream.write(b'')
            probe.unlink()
            with self._lock:
                if self._busy:
                    raise ValueError('Stop the queue before changing the destination.')
                self._settings['output_directory'] = str(folder)
                self._save()
        return self.get_state()

    def set_settings(self, keep_wavs, chunk_seconds, device='auto', output_mode='output'):
        with self._lock:
            if self._busy:
                raise ValueError("Settings can be changed after stopping the queue." if self._settings['language'] == 'en' else "Настройки можно менять после остановки очереди.")
            chunk_seconds = int(chunk_seconds)
            if chunk_seconds not in (6, 11):
                raise ValueError("Supported chunk sizes: 6 or 11 seconds." if self._settings['language'] == 'en' else "Поддерживаемый размер фрагмента: 6 или 11 секунд.")
            if device not in ('auto', 'cuda', 'cpu'):
                raise ValueError('Select Auto, CUDA or CPU.' if self._settings['language'] == 'en' else 'Выбери Auto, CUDA или CPU.')
            if output_mode not in ('output', 'replace'):
                raise ValueError('Unknown output mode.')
            self._settings.update(keep_wavs=bool(keep_wavs), chunk_seconds=chunk_seconds,
                                  device=device, output_mode=output_mode)
            self._save()
        return self.get_state()

    def remove_job(self, job_id):
        with self._lock:
            self._jobs = [job for job in self._jobs if job["id"] != job_id or job["status"] == "running"]
            self._save()
        return self.get_state()

    def clear_finished(self):
        with self._lock:
            self._jobs = [job for job in self._jobs if job["status"] in ("pending", "running")]
            self._save()
        return self.get_state()

    def retry_job(self, job_id):
        with self._lock:
            for job in self._jobs:
                if job["id"] == job_id and job["status"] in ("failed", "cancelled"):
                    job.update(status="pending", stage="waiting", progress=0, error="")
            self._save()
        return self.get_state()

    def start(self):
        with self._lock:
            try:
                model_ready = self._model['stage'] == 'ready' and self._model_fingerprint == checkpoint_fingerprint(MODEL_DIR / 'ver2.ckpt')
            except OSError:
                model_ready = False
            if not model_ready:
                if not self._model['active'] and self._model['stage'] == 'ready':
                    self.check_model()
                return self.get_state()
            if self._busy or not any(job["status"] == "pending" for job in self._jobs):
                return self.get_state()
            if self._settings['output_mode'] != 'replace' and not self._settings['output_directory']:
                self._notice = 'Выбери папку сохранения в настройках.'
                return self.get_state()
            self._stop.clear()
            self._busy = True
            self._notice = "Очередь запущена."
            threading.Thread(target=self._run_queue, daemon=True).start()
        return self.get_state()

    def cancel(self):
        with self._lock:
            self._stop.set()
            process = self._process
            self._notice = "Останавливаю текущий трек. Остальные останутся в очереди."
        self._terminate(process)
        return self.get_state()

    def _terminate(self, process):
        if process is not None and process.poll() is None:
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                               capture_output=True, creationflags=NO_WINDOW)
            else:
                process.terminate()

    def _run_queue(self):
        process = None
        # Keep Windows awake only while this worker thread processes the queue.
        if os.name == "nt":
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)
        try:
            while not self._stop.is_set():
                with self._lock:
                    job = next((j for j in self._jobs if j["status"] == "pending"), None)
                    if job is None:
                        break
                    settings = self._settings.copy()
                    job.update(status="running", stage="starting", progress=0, error="", device=None)
                    self._save()
                if process is None or process.poll() is not None:
                    command = worker_command(['--worker', '--device', settings['device'],
                                              '--chunk-seconds', str(settings['chunk_seconds'])])
                    if not settings['keep_wavs']:
                        command.append('--discard-wavs')
                    if settings['output_mode'] == 'replace':
                        command.append('--replace-original')
                    else:
                        command.extend(['--output-dir', settings['output_directory']])
                    env = os.environ.copy()
                    env['PYTHONIOENCODING'] = 'utf-8'
                    with self._lock:
                        if self._stop.is_set():
                            job.update(status='cancelled', stage='cancelled')
                            break
                        try:
                            process = subprocess.Popen(command, cwd=ROOT, env=env, stdin=subprocess.PIPE,
                                                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                                       text=True, encoding='utf-8', errors='replace',
                                                       creationflags=NO_WINDOW)
                            self._process = process
                        except OSError as exc:
                            job.update(status='failed', stage='failed', error=str(exc))
                            self._save()
                            continue
                self._run_worker_job(job, settings, process)
        finally:
            if process is not None:
                try:
                    process.stdin.close()
                    process.wait(timeout=10)
                except (OSError, subprocess.TimeoutExpired):
                    self._terminate(process)
                    process.wait(timeout=10)
            if os.name == "nt":
                ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
            with self._lock:
                self._busy = False
                self._process = None
                self._notice = "Очередь остановлена." if self._stop.is_set() else "Очередь обработана."
                self._save()

    def _run_worker_job(self, job, settings, process):
        tail = deque(maxlen=18)
        run_directory = None
        done = False
        try:
            if self._stop.is_set():
                job.update(status='cancelled', stage='cancelled')
                return
            process.stdin.write(json.dumps({'id': job['id'], 'path': job['path']}) + '\n')
            process.stdin.flush()
            for line in process.stdout:
                tail.append(line.rstrip())
                if not line.startswith('STEM_EVENT '):
                    continue
                payload = json.loads(line[len('STEM_EVENT '):])
                if payload.get('job_id') != job['id']:
                    continue
                with self._lock:
                    job.update(stage=payload['stage'], progress=payload['progress'])
                    if payload.get('device'):
                        job['device'] = payload['device']
                    if payload.get('fallback_reason'):
                        self._notice = 'CUDA недоступна: обработка продолжается на CPU.'
                    if payload.get('run_directory'):
                        run_directory = Path(payload['run_directory'])
                    if payload['stage'] == 'done':
                        job.update(status='done', progress=100, output=payload['output'], report=payload['report'])
                        done = True
                        break
                    if payload['stage'] == 'failed':
                        job.update(status='failed', error=payload.get('error') or '\n'.join(tail)[-5000:])
                        break
            if job['status'] == 'running':
                job.update(status='cancelled' if self._stop.is_set() else 'failed',
                           stage='cancelled' if self._stop.is_set() else 'failed',
                           error='' if self._stop.is_set() else '\n'.join(tail)[-5000:])
        except (OSError, ValueError) as exc:
            self._terminate(process)
            with self._lock:
                job.update(status='cancelled' if self._stop.is_set() else 'failed',
                           stage='cancelled' if self._stop.is_set() else 'failed', error=str(exc))
        finally:
            if run_directory is not None and (self._stop.is_set() or process.poll() is not None):
                cleanup_run_directory(run_directory)
            with self._lock:
                self._save()

    def get_cover(self, job_id):
        with self._lock:
            job = next((item for item in self._jobs if item['id'] == job_id), None)
            if job is None:
                return None
            path = Path(job['path'])
            if not path.exists() and (job.get('report') or {}).get('original_backup'):
                path = Path(job['report']['original_backup'])
        try:
            key = (str(path), path.stat().st_mtime_ns)
            if key in self._covers:
                return self._covers[key]
            raw = mutagen.File(path)
            pictures = []
            if raw is not None and isinstance(raw.tags, ID3):
                pictures = [picture.data for picture in sorted(raw.tags.getall('APIC'), key=lambda p: p.type != 3)]
            elif isinstance(raw, MP4):
                pictures = list((raw.tags or {}).get('covr', []))
            elif raw is not None:
                pictures = [p.data for p in sorted(getattr(raw, 'pictures', []), key=lambda p: p.type != 3)]
            result = None
            for picture in pictures:
                data = bytes(picture)
                if len(data) > 4 * 1024 * 1024:
                    continue
                mime = 'image/png' if data.startswith(b'\x89PNG') else 'image/jpeg' if data.startswith(b'\xff\xd8') else None
                if mime:
                    result = f'data:{mime};base64,' + base64.b64encode(data).decode('ascii')
                    break
            self._covers[key] = result
            return result
        except (OSError, mutagen.MutagenError):
            return None

    def open_output(self, job_id=None):
        with self._lock:
            job = next((j for j in self._jobs if j["id"] == job_id), None)
            if job_id is None and self._settings['output_mode'] == 'replace':
                job = next((j for j in reversed(self._jobs) if j.get('output')), None)
                if job is None and self._jobs:
                    folder = Path(self._jobs[0]['path']).parent
                    if folder.is_dir():
                        os.startfile(str(folder))
                        return True
            folder = Path(job["output"]).parent if job and job["output"] else (
                Path(self._settings['output_directory']) if self._settings['output_directory'] else None)
        if folder is None:
            return self.choose_output_directory()
        if not folder.is_dir():
            raise FileNotFoundError(folder)
        os.startfile(str(folder))
        return True

    def minimize_window(self):
        self._window.minimize()
        return True

    def open_author(self):
        import webbrowser
        webbrowser.open('https://github.com/Chepuxaa')
        return True

    def get_device_info(self):
        cpu_name = platform.processor() or 'CPU'
        ram_gib = None
        try:
            cpu = subprocess.run(['powershell.exe', '-NoProfile', '-Command',
                                  '(Get-CimInstance Win32_Processor | Select-Object -First 1).Name'],
                                 capture_output=True, text=True, timeout=5, creationflags=NO_WINDOW, check=True)
            cpu_name = cpu.stdout.strip() or cpu_name
            class MemoryStatus(ctypes.Structure):
                _fields_ = [('length', ctypes.c_ulong), ('load', ctypes.c_ulong),
                            ('total_physical', ctypes.c_ulonglong), ('available_physical', ctypes.c_ulonglong),
                            ('total_page', ctypes.c_ulonglong), ('available_page', ctypes.c_ulonglong),
                            ('total_virtual', ctypes.c_ulonglong), ('available_virtual', ctypes.c_ulonglong),
                            ('extended_virtual', ctypes.c_ulonglong)]
            status = MemoryStatus()
            status.length = ctypes.sizeof(status)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                ram_gib = round(status.total_physical / 1024**3, 1)
        except (OSError, AttributeError, subprocess.SubprocessError):
            pass
        cpu_info = {'cpu_name': cpu_name, 'ram_gib': ram_gib}
        try:
            # Probe the same PyTorch environment as the worker, including a CUDA operation.
            result = subprocess.run(worker_command(['--probe-device']),
                                    capture_output=True, text=True, timeout=20,
                                    creationflags=NO_WINDOW, check=True)
            return {**json.loads(result.stdout), **cpu_info}
        except (OSError, ValueError, subprocess.SubprocessError):
            return {'cuda_available': False, 'name': 'CPU', 'memory_gib': None, **cpu_info}

    def close_window(self):
        # The window's closing event stops any running queue before exit.
        self._window.destroy()
        return True


def create_app_window(api):
    window = webview.create_window("StemFlow", str(ROOT / "ui/index.html"), js_api=api,
                                  width=1000, height=600, resizable=False,
                                  frameless=True, easy_drag=False, shadow=True,
                                  background_color="#101010")
    api._window = window
    window.events.closing += api.shutdown
    return window


def main():
    if not getattr(sys, 'frozen', False) and Path(sys.prefix).resolve() != (ROOT / ".venv").resolve():
        raise SystemExit("Launch with .venv\\Scripts\\python.exe desktop.py")
    api = DesktopAPI()
    window = create_app_window(api)

    def loaded():
        api.check_model()
        zone = window.dom.get_element("#dropzone")
        def dropped(event):
            paths = [item["pywebviewFullPath"] for item in event.get("dataTransfer", {}).get("files", [])
                     if item.get("pywebviewFullPath")]
            api.add_files(paths)
        zone.on("drop", DOMEventHandler(dropped, prevent_default=True, stop_propagation=True))

    window.events.loaded += loaded
    webview.start(gui="edgechromium", storage_path=str(DATA_DIR / 'webview'), private_mode=True)


if __name__ == "__main__":
    main()
