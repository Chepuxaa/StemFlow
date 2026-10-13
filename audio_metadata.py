"""Copy common music tags and embedded artwork into an existing MP4 container."""

import base64
import math
from pathlib import Path

import mutagen
from mutagen.flac import Picture
from mutagen.id3 import ID3
from mutagen.mp4 import MP4, MP4Cover, MP4FreeForm

TEXT_TAGS = {
    "title": "\xa9nam", "artist": "\xa9ART", "album": "\xa9alb",
    "albumartist": "aART", "date": "\xa9day", "genre": "\xa9gen",
    "composer": "\xa9wrt", "copyright": "cprt", "grouping": "\xa9grp",
    "comment": "\xa9cmt", "lyrics": "\xa9lyr",
}


def track_number(value):
    parts = value.split("/", 1)
    try:
        number = int(parts[0])
        total = int(parts[1]) if len(parts) == 2 else 0
    except ValueError:
        return None
    return (number, total) if 0 <= number <= 65535 and 0 <= total <= 65535 else None


def copy_metadata(source: Path, target: Path):
    raw = mutagen.File(source)
    easy = mutagen.File(source, easy=True)
    if raw is None or easy is None:
        return {"copied_tags": [], "cover_copied": False}
    source_tags = easy.tags or {}
    output = MP4(target)
    if output.tags is None:
        output.add_tags()
    copied = []
    for source_key, target_key in TEXT_TAGS.items():
        values = source_tags.get(source_key)
        if values:
            output[target_key] = [str(value) for value in values]
            copied.append(source_key)
    for source_key, target_key in (("tracknumber", "trkn"), ("discnumber", "disk")):
        values = source_tags.get(source_key)
        parsed = track_number(str(values[0])) if values else None
        if parsed is not None:
            output[target_key] = [parsed]
            copied.append(source_key)
    bpm = source_tags.get("bpm")
    if bpm:
        try:
            tempo = float(bpm[0])
            if math.isfinite(tempo) and 0 <= tempo <= 65535:
                output["tmpo"] = [round(tempo)]
                copied.append("bpm")
        except (ValueError, TypeError):
            pass
    for source_key, target_key in (("initialkey", "initialkey"), ("isrc", "ISRC")):
        values = source_tags.get(source_key)
        if values:
            output[f"----:com.apple.iTunes:{target_key}"] = [
                MP4FreeForm(str(value).encode("utf-8")) for value in values]
            copied.append(source_key)

    pictures = []
    if isinstance(raw.tags, ID3):
        # EasyID3 does not expose comments, lyrics, or embedded cover images.
        for frame_type, target_key in (("COMM", "\xa9cmt"), ("USLT", "\xa9lyr")):
            frames = raw.tags.getall(frame_type)
            if frames:
                output[target_key] = [str(value) for frame in frames
                                      for value in (frame.text if isinstance(frame.text, list) else [frame.text])]
                copied.append("comment" if frame_type == "COMM" else "lyrics")
        pictures = sorted(raw.tags.getall("APIC"), key=lambda pic: pic.type != 3)
    elif isinstance(raw, MP4):
        for key in ("covr", "\xa9cmt", "\xa9lyr", "tmpo",
                    "----:com.apple.iTunes:initialkey", "----:com.apple.iTunes:ISRC"):
            if raw.tags and key in raw.tags:
                output[key] = raw.tags[key]
                copied.append(key)
    else:
        pictures = list(getattr(raw, "pictures", []))
        if not pictures:
            for encoded in source_tags.get("metadata_block_picture", []):
                pictures.append(Picture(base64.b64decode(encoded)))
        pictures.sort(key=lambda pic: pic.type != 3)
    for picture in pictures:
        data = picture.data
        if data.startswith(b"\xff\xd8\xff"):
            image_format = MP4Cover.FORMAT_JPEG
        elif data.startswith(b"\x89PNG\r\n\x1a\n"):
            image_format = MP4Cover.FORMAT_PNG
        else:
            continue
        output["covr"] = [MP4Cover(data, imageformat=image_format)]
        break
    output.save()
    return {"copied_tags": copied, "cover_copied": bool(output.tags.get("covr"))}
