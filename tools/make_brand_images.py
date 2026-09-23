"""Generate the brand images (icon / logo, each normal and @2x).

The integration is a tariff comparison for the Austrian E-Control
Tarifkalkulator, so the mark is a lightning bolt (energy) over a rising
gradient (blue = electricity, the traditional accent of price comparison).
Run with:  python tools/make_brand_images.py
"""

from __future__ import annotations

import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

BLUE = (21, 101, 192)  # #1565C0
BLUE_LIGHT = (66, 165, 245)  # #42A5F5
BLUE_DARK = (13, 71, 161)  # #0D47A1
WHITE = (255, 255, 255, 255)
INK = (13, 71, 161, 255)
LIGHT_INK = (240, 246, 255, 255)

BOLD_FONTS = (
    r"C:\Windows\Fonts\segoeuib.ttf",
    r"C:\Windows\Fonts\arialbd.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
)

ROOT = Path(__file__).resolve().parents[1]
BRAND = ROOT / "custom_components" / "econtrol" / "brand"


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Return a bold font of ``size`` pixels, if one can be found."""
    for candidate in BOLD_FONTS:
        if os.path.exists(candidate):
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


def _bolt(size: int, colour: tuple[int, int, int, int]) -> Image.Image:
    """Return a lightning bolt glyph on a transparent square canvas."""
    scale = 8
    side = size * scale
    layer = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    # A classic bolt, defined on a 0..100 grid.
    points = [
        (58, 6),
        (26, 54),
        (46, 54),
        (38, 94),
        (76, 42),
        (54, 42),
    ]
    draw.polygon(
        [(x * side / 100, y * side / 100) for x, y in points], fill=colour
    )
    return layer.resize((size, size), Image.LANCZOS)


def _gradient(size: tuple[int, int], start, end) -> Image.Image:
    """Return a vertical gradient image."""
    width, height = size
    image = Image.new("RGBA", size)
    pixels = image.load()
    for y in range(height):
        mix = y / max(height - 1, 1)
        row = tuple(
            round(start[channel] + (end[channel] - start[channel]) * mix)
            for channel in range(3)
        )
        for x in range(width):
            pixels[x, y] = (*row, 255)
    return image


def icon(size: int) -> Image.Image:
    """Return the square app icon."""
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    radius = round(size * 0.22)
    mask = Image.new("L", (size * 4, size * 4), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, size * 4 - 1, size * 4 - 1), radius=radius * 4, fill=255
    )
    canvas.paste(_gradient((size, size), BLUE_LIGHT, BLUE_DARK), (0, 0), mask.resize((size, size), Image.LANCZOS))
    bolt = _bolt(round(size * 0.62), WHITE)
    canvas.alpha_composite(bolt, ((size - bolt.width) // 2, (size - bolt.height) // 2))
    return canvas


def logo(size: tuple[int, int], *, dark_background: bool) -> Image.Image:
    """Return the horizontal logo."""
    width, height = size
    canvas = Image.new("RGBA", size, (0, 0, 0, 0))
    bolt = _bolt(round(height * 0.86), BLUE_LIGHT if dark_background else BLUE)
    canvas.alpha_composite(bolt, (round(height * 0.05), round(height * 0.07)))

    text_box = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(text_box)
    x = round(height * 0.05) + bolt.width + round(height * 0.18)
    top = _font(round(height * 0.40))
    bottom = _font(round(height * 0.22))
    draw.text((x, round(height * 0.20)), "E-Control", font=top, fill=LIGHT_INK if dark_background else INK)
    draw.text(
        (x, round(height * 0.66)),
        "Tarifkalkulator",
        font=bottom,
        fill=(200, 220, 245, 255) if dark_background else (70, 110, 160, 255),
    )
    canvas.alpha_composite(text_box)
    return canvas


def main() -> None:
    """Write all brand images."""
    BRAND.mkdir(parents=True, exist_ok=True)
    outputs: dict[str, Image.Image] = {
        "icon.png": icon(256),
        "icon@2x.png": icon(512),
        "logo.png": logo((512, 160), dark_background=False),
        "logo@2x.png": logo((1024, 320), dark_background=False),
        "dark_logo.png": logo((512, 160), dark_background=True),
        "dark_logo@2x.png": logo((1024, 320), dark_background=True),
    }
    for name, image in outputs.items():
        image.save(BRAND / name, "PNG", optimize=True)
        print(f"{name}: {image.width}x{image.height}")


if __name__ == "__main__":
    main()
