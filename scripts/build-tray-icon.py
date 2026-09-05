"""Package the approved PNG as a multi-resolution Windows icon. Requires Pillow."""
from pathlib import Path

from PIL import Image, ImageOps


ROOT = Path(__file__).resolve().parents[1]
SIZES = (16, 20, 24, 32, 48, 256)


def main():
    with Image.open(ROOT / 'bridge/assets/tray-icon-source.png') as source:
        if source.mode != 'RGBA' or source.getchannel('A').getextrema()[0] != 0:
            raise ValueError('The approved source must contain real transparency.')
        artwork = ImageOps.contain(source, (240, 240), Image.Resampling.LANCZOS)
        square = Image.new('RGBA', (256, 256))
        square.alpha_composite(artwork, ((256 - artwork.width) // 2, (256 - artwork.height) // 2))
        # Windows PowerShell's System.Drawing needs DIB frames for reliable decoding.
        square.save(ROOT / 'bridge/tray-icon.ico', sizes=[(size, size) for size in SIZES],
                    bitmap_format='bmp')


if __name__ == '__main__':
    main()
