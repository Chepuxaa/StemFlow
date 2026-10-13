"""Rasterize the supplied vector badge once during packaging."""
from pathlib import Path


def build_watermark(source, target):
    import resvg_py
    Path(target).write_bytes(resvg_py.svg_to_bytes(svg_path=str(source), width=1264,
                                                skip_system_fonts=True))


if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1]
    build_watermark(root / 'ui/assets/watermark.svg', root / 'ui/assets/watermark.png')
