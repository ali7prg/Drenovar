#!/usr/bin/env python3
"""Arrange actual fixed-camera Godot captures for visual acceptance (no retouching)."""
from pathlib import Path
import json
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
CAPTURES = Path('/tmp/v6-architecture-captures')
REVIEW = HERE / 'review'
ASSETS = HERE.parents[2] / 'godot/project/assets/city/architecture-v6'


def main() -> None:
    manifest = json.loads((ASSETS / 'manifest.json').read_text())
    types = sorted(manifest['levels'], key=lambda t: manifest['levels'][t]['6']['id'])
    REVIEW.mkdir(exist_ok=True)
    font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 18)
    small = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 14)
    width, cell_h, label_h, title_h = 320, 280, 25, 38
    for page in range(3):
        sheet = Image.new('RGB', (width * 6, title_h + 9 * (cell_h + label_h)), '#24312c')
        draw = ImageDraw.Draw(sheet)
        for column, level in enumerate(['VI', 'VII', 'VIII', 'IX', 'X', 'XI']):
            draw.text((column * width + 12, 8), level, font=font, fill='#ffffff')
        for row, type_id in enumerate(types[page * 9:(page + 1) * 9]):
            y = title_h + row * (cell_h + label_h)
            concept_id = manifest['levels'][type_id]['6']['id']
            for column, level in enumerate(range(6, 12)):
                source = CAPTURES / f'{type_id}-{level}.png'
                with Image.open(source) as image:
                    image = image.convert('RGB').resize((width, cell_h), Image.Resampling.LANCZOS)
                    sheet.paste(image, (column * width, y + label_h))
                draw.text((column * width + 12, y + 2), f'{concept_id} / {type_id} / {level}', font=small, fill='#eeeecc')
        sheet.save(REVIEW / f'VI-XI-{page + 1:02d}.png')
    settings = {'source':'actual Godot mesh renderer, no retouching', 'states':162,
                'engine':'Godot 4.6.3', 'renderer':'OpenGL compatibility on software LLVMpipe',
                'camera':'fixed orthographic 18.5m, position(15,17,20), target(0,2.7,0)',
                'lighting':'same directional/ambient settings for all captures, 4xMSAA, shadows on',
                'source_capture_px':[480,420], 'contact_cell_px':[320,280],
                'not_a_device_benchmark':True}
    (REVIEW / 'capture-settings.json').write_text(json.dumps(settings, indent=2) + '\n')


if __name__ == '__main__':
    main()
