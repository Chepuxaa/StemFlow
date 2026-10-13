"""Render the supplied rectangular SVG glyph into a transparent Windows ICO."""
from pathlib import Path
import xml.etree.ElementTree as ET


def build_icon(svg, destination):
    from PIL import Image, ImageDraw
    root = ET.parse(svg).getroot()
    left, top, width, height = map(float, root.attrib['viewBox'].split())
    canvas = 1024
    scale = canvas / max(width, height)
    offset_x, offset_y = (canvas - width * scale) / 2, (canvas - height * scale) / 2
    image = Image.new('RGBA', (canvas, canvas), (0, 0, 0, 0))
    drawing = ImageDraw.Draw(image)
    for element in root:
        if element.tag.rsplit('}', 1)[-1] != 'rect':
            raise ValueError('The icon renderer expects the supplied SVG rectangle glyph.')
        x, y = float(element.get('x', 0)), float(element.get('y', 0))
        w, h = float(element.get('width')), float(element.get('height'))
        box = ((x - left) * scale + offset_x, (y - top) * scale + offset_y,
               (x + w - left) * scale + offset_x, (y + h - top) * scale + offset_y)
        drawing.rounded_rectangle(box, radius=float(element.get('rx', 0)) * scale, fill=element.get('fill'))
    image = image.resize((256, 256), Image.Resampling.LANCZOS)
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    image.save(destination, format='ICO', sizes=[(n, n) for n in (16, 20, 24, 32, 40, 48, 64, 128, 256)])
    return destination


if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1]
    print(build_icon(root / 'ui/assets/icon.svg', root / 'ui/assets/icon.ico'))
