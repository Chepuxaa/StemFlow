"""Mel-Band four-stem separation on CUDA or CPU and NI Stem export."""

import argparse
import json
import gc
import math
from pathlib import Path
import subprocess
import sys
import time
import traceback
import tempfile
import shutil

from audio_runtime import get_ffmpeg_exe
import numpy as np
import soundfile as sf
from cuda_runtime import CudaError, probe_device
from model_runtime import load_model, infer, resolve_device, ModelCache
from file_output import replace_original, fingerprint
from app_paths import DATA_DIR, TEMP_ROOT, RESOURCE_DIR, MODEL_DIR

from ni_stem import STEMS, export_stem
from stem_palette import DEFAULT_COLORS, validate_colors

ROOT = RESOURCE_DIR
RATE = 44100
CURRENT_JOB = None


def event(stage, progress, **details):
    if CURRENT_JOB is not None:
        details['job_id'] = CURRENT_JOB
    print("STEM_EVENT " + json.dumps({"stage": stage, "progress": progress, **details}), flush=True)


def positive(value):
    value = float(value)
    if not math.isfinite(value) or value < 0:
        raise argparse.ArgumentTypeError("Expected a finite nonnegative number")
    return value


def separate_audio(audio, chunk_seconds, requested, progress, cache=None, overlap_percent=75, cpu_fast=False):
    if overlap_percent not in (50, 75):
        raise ValueError('Supported overlap: 50% or 75%.')
    device = 'cpu' if cache and cache.force_cpu and requested == 'auto' else resolve_device(requested)
    fallback_reason = None
    if requested == 'auto' and device == 'cpu':
        fallback_reason = 'CUDA unavailable'
        event('load', 8, device=device, fallback_reason=fallback_reason)

    def attempt(target):
        model = None
        started = time.perf_counter()
        try:
            reuse = cache is not None and cache.model is not None and cache.device == target
            event('separate' if reuse else 'load', 10 if reuse else 8,
                  device=target, model_reused=reuse)
            if cache is None:
                model, config = load_model(target, chunk_seconds, cpu_fast=cpu_fast) if cpu_fast else load_model(target, chunk_seconds)
                reused = False
            else:
                model, config, reused = cache.get(target, chunk_seconds, cpu_fast=cpu_fast)
            loaded = time.perf_counter()
            # Queue cache keeps the original config, including after GPU -> CPU fallback.
            config = {**config, 'inference': {**config['inference'], 'num_overlap': 4 if overlap_percent == 75 else 2}}
            stems = infer(model, config, audio, chunk_seconds, progress)
            return stems, 0.0 if reused else loaded - started, time.perf_counter() - loaded, (
                0.0)
        finally:
            if model is not None and cache is None:
                model.close()
            del model

    started = time.perf_counter()
    failed_cuda_seconds = 0.0
    result = None
    try:
        result = attempt(device)
    except RuntimeError as exc:
        message = str(exc).lower()
        cuda_error = isinstance(exc, CudaError) or any(
            name in message for name in ('cuda', 'cudnn', 'cublas', 'nvidia'))
        if requested != 'auto' or not device.startswith('cuda') or not cuda_error:
            raise
        fallback_reason = str(exc)
        failed_cuda_seconds = time.perf_counter() - started
    # Leave the exception scope before reloading: its traceback can retain GPU tensors.
    if result is None:
        if cache:
            cache.clear()
            cache.force_cpu = True
        gc.collect()
        device = 'cpu'
        print(f'CUDA failed; restarting the entire track on CPU: {fallback_reason}', flush=True)
        event('load', 8, device=device, fallback_reason=fallback_reason)
        result = attempt(device)
    stems, load_seconds, separation_seconds, peak = result
    return stems, {'device': device, 'requested_device': requested,
                   'fallback_reason': fallback_reason, 'failed_cuda_seconds': failed_cuda_seconds,
                   'model_load_seconds': load_seconds, 'separation_seconds': separation_seconds,
                   'model_reused': load_seconds == 0,
                   'peak_allocated_vram_gib': peak,
                   'backend': 'TensorRT RTX' if device.startswith('cuda') else 'ONNX Runtime',
                   'gpu': probe_device()['name'] if device.startswith('cuda') else None,
                   'overlap_percent': overlap_percent,
                   'cpu_fast': bool(cpu_fast and device == 'cpu'),
                   'overlap': 4 if overlap_percent == 75 else 2}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("track", nargs="?", type=Path)
    parser.add_argument("--start", type=positive, default=0)
    parser.add_argument("--seconds", type=positive, default=60, help="0 = full track")
    parser.add_argument("--chunk-seconds", type=positive, default=11)
    parser.add_argument('--device', choices=('auto', 'cuda', 'cpu'), default='auto')
    parser.add_argument('--overlap', type=int, choices=(50, 75), default=75)
    parser.add_argument('--cpu-fast', action='store_true', help='Use locally converted INT8 linear layers on CPU')
    parser.add_argument('--worker', action='store_true', help='Read queue jobs as JSON lines on stdin')
    parser.add_argument('--replace-original', action='store_true')
    parser.add_argument('--watermark-cover', action='store_true')
    parser.add_argument('--stem-colors', nargs=4, metavar='COLOR', help='Drums, Bass, Other, Vocals as #RRGGBB')
    parser.add_argument('--output-dir', type=Path, help='User-selected destination for finished stems')
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--codec", choices=("aac", "alac"), default="aac",
                        help="AAC for Windows Traktor; ALAC is an optional compatibility trial")
    parser.add_argument("--discard-wavs", action="store_true", help="Remove intermediate WAVs after a successful export")
    args = parser.parse_args()
    try:
        args.stem_colors = validate_colors(DEFAULT_COLORS if args.stem_colors is None else args.stem_colors)
    except ValueError as exc:
        parser.error(str(exc))
    if not getattr(sys, 'frozen', False) and Path(sys.prefix).resolve() != (ROOT / ".venv").resolve():
        parser.error("Run with .\\.venv\\Scripts\\python.exe separate.py")
    try:
        resolve_device(args.device)
    except RuntimeError as exc:
        parser.error(str(exc))
    if args.chunk_seconds not in (6, 11):
        parser.error("--chunk-seconds must be 6 or 11")
    if not args.replace_original and args.output_dir is None:
        parser.error('Choose a destination with --output-dir, or use --replace-original')
    if args.worker:
        worker_loop(args)
        return
    if bool(args.track) == args.self_test:
        parser.error("Provide either a track path or --self-test")
    if args.track and not args.track.is_file():
        parser.error(f"File not found: {args.track}")
    if args.replace_original and (args.self_test or args.start or args.seconds):
        parser.error('--replace-original requires a full input track: --seconds 0 --start 0')
    process_track(args)


def worker_loop(args):
    global CURRENT_JOB
    cache = ModelCache()
    try:
        for line in sys.stdin:
            try:
                task = json.loads(line)
                CURRENT_JOB = task['id']
                args.track = Path(task['path'])
                args.self_test = False
                args.start = args.seconds = 0
                process_track(args, cache)
            except Exception as exc:
                traceback.print_exc()
                event('failed', 0, error=str(exc))
            finally:
                CURRENT_JOB = None
    finally:
        cache.clear()


def process_track(args, cache=None):
    TEMP_ROOT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='track-', dir=TEMP_ROOT) as directory:
        _process_track(args, cache, Path(directory))


def _process_track(args, cache, directory):
    if args.track and not args.track.is_file():
        raise FileNotFoundError(args.track)
    source_fingerprint = fingerprint(args.track) if args.replace_original else None
    if args.replace_original:
        extension = 'mp4' if args.codec == 'aac' else 'm4a'
        target = args.track.parent / f'{args.track.stem}.stem.{extension}'
        if target.exists():
            raise FileExistsError(target)

    title = "self-test" if args.self_test else args.track.stem
    extension = 'mp4' if args.codec == 'aac' else 'm4a'
    final_folder = args.track.parent if args.replace_original else args.output_dir.expanduser().resolve()
    if not args.replace_original:
        final_folder.mkdir(parents=True, exist_ok=True)
        if (final_folder / f'{title}.stem.{extension}').exists():
            raise FileExistsError(final_folder / f'{title}.stem.{extension}')
    if not args.discard_wavs and (final_folder / f'{title}-stems').exists():
        raise FileExistsError(final_folder / f'{title}-stems')
    event("decode", 2, run_directory=str(directory))
    master_path = directory / "master.wav"
    if args.self_test:
        duration = min(args.seconds, 6) if args.seconds else 6
        t = np.arange(int(duration * RATE), dtype=np.float32) / RATE
        mono = 0.12 * np.sin(2 * np.pi * 220 * t) + 0.08 * np.sin(2 * np.pi * 880 * t)
        sf.write(master_path, np.stack((mono, mono), axis=1), RATE, subtype="FLOAT")
    else:
        command = [get_ffmpeg_exe(), "-nostdin", "-hide_banner",
                   "-loglevel", "error", "-n", "-ss", str(args.start), "-i", str(args.track)]
        if args.seconds:
            command += ["-t", str(args.seconds)]
        command += ["-map", "0:a:0", "-vn", "-ar", str(RATE), "-ac", "2",
                    "-c:a", "pcm_f32le", str(master_path)]
        subprocess.run(command, check=True)
    audio, rate = sf.read(master_path, dtype="float32", always_2d=True)
    if not len(audio) or not np.isfinite(audio).all():
        raise ValueError("Input contains no usable finite audio")
    from scripts.download_model import model_target
    checkpoint = model_target()
    if not checkpoint.is_file():
        raise FileNotFoundError(f'Weights missing: {checkpoint}. Run scripts/download_model.py or StemFlow.exe --download-model.')
    print(f"Audio: {len(audio) / rate:.2f}s; loading MelBand 4-stem SYH v2", flush=True)
    started = time.perf_counter()
    event("load", 8, audio_seconds=len(audio) / rate)

    def chunk_finished(completed, total):
        event("separate", 10 + 75 * completed / total,
              completed_chunks=completed, total_chunks=total)

    stems, device_report = separate_audio(audio, args.chunk_seconds, args.device, chunk_finished, cache,
                                          overlap_percent=args.overlap, cpu_fast=args.cpu_fast)
    elapsed = time.perf_counter() - started
    levels = {}
    event("write", 86)
    for name in STEMS:
        stem = stems[name]
        if stem.shape != audio.T.shape or not np.isfinite(stem).all():
            raise ValueError(f"Invalid model output: {name}")
        levels[name] = float(np.max(np.abs(stem)))
        sf.write(directory / f"{name}.wav", stem.T, rate, subtype="FLOAT")
    # Keep float WAVs and the model's original level, including peaks above 1.0.
    # No normalization, attenuation, or limiter is applied before encoding.
    gain = 1.0
    print(f"Writing {args.codec.upper()} NI Stem container...", flush=True)
    event("encode", 90)
    destination = directory if args.replace_original else args.output_dir.expanduser().resolve()
    output = export_stem(directory, title, codec=args.codec, source_track=args.track,
                         destination=destination, watermark=args.watermark_cover, stem_colors=args.stem_colors)
    backup = None
    if args.replace_original:
        event('publish', 96)
        generated = output
        output, backup = replace_original(args.track, generated, source_fingerprint)
        generated.unlink()
    report = {"model": "melband-4stem-syh-v2", **device_report,
              "input": str(args.track.resolve()) if args.track else "synthetic technical test",
              "audio_seconds": len(audio) / rate, "start_seconds": args.start,
              "separation_and_load_seconds": elapsed,
              "chunk_seconds": args.chunk_seconds, "batch_size": 1,
              "export_codec": args.codec,
              "stem_colors": args.stem_colors,
              "aac_target_bitrates_kbps": [320, 320, 320, 320, 320] if args.codec == "aac" else None,
              "common_output_gain": gain, "normalization": False, "limiter": False,
              "stem_peaks_before_gain": levels,
              "output": str(output), "traktor_playback_verified": False}
    report['original_backup'] = str(backup) if backup else None
    reports = DATA_DIR / 'reports'
    reports.mkdir(parents=True, exist_ok=True)
    if not args.discard_wavs:
        wav_folder = output.parent / f'{title}-stems'
        wav_folder.mkdir(exist_ok=False)
        for name in ("master",) + STEMS:
            shutil.copyfile(directory / f'{name}.wav', wav_folder / f'{name}.wav')
        report['wav_directory'] = str(wav_folder)
    (reports / f'{directory.name}.json').write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    event("done", 100, output=str(output), report=report)
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    try:
        main()
    except CudaError as exc:
        raise SystemExit(f"TensorRT GPU processing failed: {exc}")
