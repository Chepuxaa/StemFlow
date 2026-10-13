"""Stamp exported artwork with the supplied StemFlow badge."""
from io import BytesIO

from PIL import Image, ImageOps
from app_paths import RESOURCE_DIR


def watermark_cover(data):
    with Image.open(BytesIO(data)) as source:
        cover = ImageOps.exif_transpose(source).convert('RGB')
    with Image.open(RESOURCE_DIR / 'ui/assets/watermark.png') as source:
        badge = source.convert('RGBA')
    width = max(1, round(cover.width * .30))
    height = max(1, round(width * badge.height / badge.width))
    if height > cover.height:
        height = cover.height
        width = max(1, round(height * badge.width / badge.height))
    badge = badge.resize((width, height), Image.Resampling.LANCZOS)
    top = min(round(cover.height * .125), cover.height - height)
    cover.paste(badge, (0, top), badge)
    output = BytesIO()
    cover.save(output, format='JPEG', quality=95, subsampling=0)
    return output.getvalue()
