"""Generate PWA app icons for SocialPoster using Pillow."""

import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw
except ImportError:
    print("Pillow not installed. Installing...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "Pillow"])
    from PIL import Image, ImageDraw

ICONS_DIR = Path(__file__).parent.parent / "src" / "socialposter" / "web" / "static" / "icons"
ICONS_DIR.mkdir(parents=True, exist_ok=True)

INDIGO = (99, 102, 241)  # #6366f1
WHITE = (255, 255, 255)


def draw_icon(size, padding_ratio=0.15, maskable=False):
    """Create an icon with indigo rounded rect background and white checkmark."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    if maskable:
        # Maskable icons need full-bleed background with safe zone at 80%
        draw.rectangle([0, 0, size, size], fill=INDIGO)
        # Draw checkmark within safe zone (inner 80%)
        safe_margin = int(size * 0.1)
        inner = size - 2 * safe_margin
    else:
        # Regular icon with rounded rect
        radius = int(size * 0.18)
        draw.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=INDIGO)
        safe_margin = 0
        inner = size

    # Draw checkmark
    padding = int(inner * padding_ratio)
    x0 = safe_margin + padding
    y_center = size // 2
    x_mid = x0 + int(inner * 0.3)
    y_bottom = y_center + int(inner * 0.18)
    x_end = safe_margin + inner - padding
    y_top = y_center - int(inner * 0.18)

    stroke_width = max(2, int(size * 0.06))
    draw.line([(x0, y_center), (x_mid, y_bottom)], fill=WHITE, width=stroke_width)
    draw.line([(x_mid, y_bottom), (x_end, y_top)], fill=WHITE, width=stroke_width)

    return img


def main():
    sizes = {
        "icon-192.png": (192, False),
        "icon-512.png": (512, False),
        "icon-maskable-192.png": (192, True),
        "icon-maskable-512.png": (512, True),
        "apple-touch-icon-180.png": (180, False),
    }

    for name, (size, maskable) in sizes.items():
        img = draw_icon(size, maskable=maskable)
        path = ICONS_DIR / name
        img.save(str(path), "PNG")
        print(f"Created {path}")

    # Generate favicon.ico (multi-size ICO)
    img16 = draw_icon(16)
    img32 = draw_icon(32)
    img48 = draw_icon(48)
    ico_path = ICONS_DIR / "favicon.ico"
    img16.save(str(ico_path), format="ICO", sizes=[(16, 16), (32, 32), (48, 48)],
               append_images=[img32, img48])
    print(f"Created {ico_path}")

    print("All icons generated successfully!")


if __name__ == "__main__":
    main()
