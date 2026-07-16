"""
Icon Generator
==============

One-off generator for ``usage_monitor_for_codex.ico``. Run from the repo
root with ``python tools/generate_icon.py``.
"""
from __future__ import annotations

import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

SIZE = 256
OUTPUT = Path(__file__).parent.parent / 'usage_monitor_for_codex.ico'


def build_master() -> Image.Image:
    """Render the Codex prompt motif and two usage bars on a dark tile."""
    image = Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle([8, 8, SIZE - 8, SIZE - 8], radius=48, fill=(30, 30, 30, 255))

    fonts_directory = Path(os.environ.get('WINDIR', r'C:\Windows')) / 'Fonts'
    font = None
    for path in (fonts_directory / 'consolab.ttf', fonts_directory / 'arialbd.ttf'):
        try:
            font = ImageFont.truetype(str(path), 120)
            break
        except OSError:
            continue
    assert font is not None, 'no usable font found'

    bbox = draw.textbbox((0, 0), '>_', font=font)
    draw.text(((SIZE - bbox[2] + bbox[0]) / 2 - bbox[0], 40 - bbox[1]), '>_', fill=(255, 255, 255, 255), font=font)
    draw.rectangle([32, 176, 152, 198], fill=(74, 158, 255, 255))
    draw.rectangle([32, 176, SIZE - 32, 198], outline=(255, 255, 255, 90), width=3)
    draw.rectangle([32, 208, 100, 230], fill=(74, 158, 255, 255))
    draw.rectangle([32, 208, SIZE - 32, 230], outline=(255, 255, 255, 90), width=3)
    return image


if __name__ == '__main__':
    build_master().save(OUTPUT, format='ICO', sizes=[(256, 256), (64, 64), (48, 48), (32, 32), (16, 16)])
    print(f'wrote {OUTPUT}')
