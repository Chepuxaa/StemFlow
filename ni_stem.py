"""Small NI Stem container writer; Traktor playback still needs manual validation."""

import json
import struct
import subprocess
from pathlib import Path

import imageio_ffmpeg

from audio_metadata import copy_metadata

STEMS = ("drums", "bass", "other", "vocals")


def boxes(data):
    offset = 0
    while offset < len(data):
        if len(data) - offset < 8:
            raise ValueError("Truncated MP4 box")
        size, kind = struct.unpack_from(">I4s", data, offset)
        if size < 8 or offset + size > len(data):
            raise ValueError("Unsupported or invalid MP4 box")
        yield kind, data[offset + 8:offset + size]
        offset += size


def box(kind, payload):
    return struct.pack(">I4s", len(payload) + 8, kind) + payload


def patch_movie(movie):
    metadata = {
        "version": 1,
        "stems": [dict(name=name.title(), color=color) for name, color in zip(
            STEMS, ("#009E73", "#D55E00", "#CC79A7", "#56B4E9"))],
        "mastering_dsp": {
            "compressor": {"enabled": False, "ratio": 3, "output_gain": 0.5,
                           "release": 0.3, "attack": 0.003, "input_gain": 0.5,
                           "threshold": 0, "hp_cutoff": 300, "dry_wet": 50},
            "limiter": {"enabled": False, "release": 0.05,
                        "threshold": 0, "ceiling": -0.35},
        },
    }
    stem_box = box(b"stem", json.dumps(metadata).encode("utf-8"))
    children, tracks, has_udta = [], 0, False
    for kind, payload in boxes(movie):
        if kind == b"trak":
            track_parts = []
            for child_kind, child in boxes(payload):
                if child_kind == b"tkhd":
                    child = bytearray(child)
                    # Keep the master enabled; individual stems remain in the movie.
                    child[1:4] = (3 if tracks == 0 else 2).to_bytes(3, "big")
                    group_offset = 46 if child[0] == 1 else 34
                    child[group_offset:group_offset + 2] = b"\x00\x00"
                track_parts.append(box(child_kind, child))
            payload = b"".join(track_parts)
            tracks += 1
        elif kind == b"udta":
            parts = []
            for child_kind, child in boxes(payload):
                if child_kind == b"meta":
                    meta_parts = []
                    for meta_kind, meta in boxes(child[4:]):
                        if meta_kind == b"ilst":
                            meta += box(b"TAUT", box(b"data", struct.pack(">II", 1, 0) + b"STEM"))
                        meta_parts.append(box(meta_kind, meta))
                    child = child[:4] + b"".join(meta_parts)
                parts.append(box(child_kind, child))
            payload = b"".join(parts) + stem_box
            has_udta = True
        children.append(box(kind, payload))
    if tracks != 5:
        raise ValueError(f"Expected 5 audio tracks, found {tracks}")
    if not has_udta:
        children.append(box(b"udta", stem_box))
    return b"".join(children)


def export_stem(directory: Path, title: str, *, codec="aac", destination=None, source_track=None):
    if codec not in ("aac", "alac"):
        raise ValueError("Supported codecs: aac, alac")
    destination = Path(destination) if destination is not None else directory
    destination.mkdir(parents=True, exist_ok=True)
    extension = "mp4" if codec == "aac" else "m4a"
    output = destination / f"{title}.stem.{extension}"
    temporary = destination / "container.partial.mp4"
    if output.exists() or temporary.exists():
        raise FileExistsError("Output container already exists")
    command = [imageio_ffmpeg.get_ffmpeg_exe(), "-nostdin", "-hide_banner",
               "-loglevel", "error", "-n"]
    for name in ("master",) + STEMS:
        command += ["-i", str(directory / f"{name}.wav")]
    for index in range(5):
        command += ["-map", f"{index}:a:0"]
    # AAC is the Windows compatibility default. ALAC remains an optional export.
    command += ["-c:a", codec]
    if codec == "aac":
        command += ["-b:a:0", "320k"]
        for index in range(1, 5):
            command += [f"-b:a:{index}", "320k"]
    else:
        command += ["-sample_fmt", "s32p"]
    for index, name in enumerate(("master",) + STEMS):
        command += [f"-metadata:s:a:{index}", f"handler_name={name.title()}"]
    # Keep moov after media data so adding metadata leaves chunk offsets intact.
    command += ["-metadata", f"title={title}", "-brand", "mp42" if codec == "aac" else "M4A ",
                "-f", "mp4", str(temporary)]
    try:
        subprocess.run(command, check=True)
        with temporary.open("r+b") as stream:
            length = stream.seek(0, 2)
            stream.seek(0)
            while stream.tell() < length:
                offset = stream.tell()
                size, kind = struct.unpack(">I4s", stream.read(8))
                header_size = 8
                if size == 1:
                    size = struct.unpack(">Q", stream.read(8))[0]
                    header_size = 16
                if size < header_size or offset + size > length:
                    raise ValueError("Invalid top-level MP4 box")
                if kind == b"moov":
                    if offset + size != length or header_size != 8:
                        raise ValueError("Expected final, regular moov box")
                    movie = patch_movie(stream.read(size - 8))
                    stream.seek(offset)
                    stream.write(box(b"moov", movie))
                    stream.truncate()
                    break
                stream.seek(offset + size)
            else:
                raise ValueError("Missing moov box")
        if source_track is not None:
            copied = copy_metadata(Path(source_track), temporary)
            print(f"Metadata: {', '.join(copied['copied_tags']) or 'no source tags'}; "
                  f"cover: {copied['cover_copied']}", flush=True)
        temporary.rename(output)
        return output
    finally:
        temporary.unlink(missing_ok=True)
