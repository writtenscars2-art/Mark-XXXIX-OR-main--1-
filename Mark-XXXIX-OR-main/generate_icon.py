"""
Creates a more distinctive JARVIS icon with a glowing, angular core and a futuristic sigil.
Saves multiple sizes into a single .ico file.
"""
import math
from pathlib import Path
from PIL import Image, ImageDraw


def draw_icon(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    cx, cy = size / 2, size / 2
    glow = (0, 220, 255)
    accent = (255, 90, 180)
    amber = (255, 190, 90)
    dark = (12, 16, 30)

    # outer glow halo
    for i in range(10, 0, -1):
        alpha = 18 + i * 8
        r = size * (0.44 + i * 0.008)
        draw.ellipse(
            [cx - r, cy - r, cx + r, cy + r],
            outline=(*glow, alpha),
            width=max(1, size // 110),
        )

    # broken orbit ring
    for angle in range(0, 360, 60):
        rad = math.radians(angle)
        x1 = cx + math.cos(rad) * size * 0.24
        y1 = cy + math.sin(rad) * size * 0.24
        x2 = cx + math.cos(rad) * size * 0.40
        y2 = cy + math.sin(rad) * size * 0.40
        draw.line([x1, y1, x2, y2], fill=(*accent, 180), width=max(1, size // 95))

    # deep background prism
    prism = [
        (cx - size * 0.28, cy + size * 0.02),
        (cx - size * 0.08, cy - size * 0.26),
        (cx + size * 0.22, cy - size * 0.10),
        (cx + size * 0.06, cy + size * 0.24),
    ]
    draw.polygon(prism, fill=(*dark, 230), outline=(*glow, 180))

    # central diamond core
    draw.polygon(
        [
            (cx - size * 0.09, cy),
            (cx, cy - size * 0.18),
            (cx + size * 0.09, cy),
            (cx, cy + size * 0.18),
        ],
        fill=(*accent, 255),
        outline=(*glow, 255),
    )

    # stylized J sigil
    draw.line(
        [cx - size * 0.055, cy - size * 0.15, cx - size * 0.055, cy + size * 0.085],
        fill=(*dark, 255),
        width=max(2, size // 28),
    )
    draw.arc(
        [cx - size * 0.115, cy - size * 0.14, cx + size * 0.03, cy + size * 0.12],
        0,
        270,
        fill=(*glow, 255),
        width=max(3, size // 24),
    )
    draw.line(
        [cx - size * 0.075, cy + size * 0.085, cx + size * 0.045, cy + size * 0.085],
        fill=(*glow, 255),
        width=max(3, size // 24),
    )
    draw.ellipse(
        [cx + size * 0.03, cy + size * 0.055, cx + size * 0.08, cy + size * 0.105],
        fill=(*amber, 255),
    )

    # angular side blades
    draw.polygon(
        [
            (cx - size * 0.30, cy - size * 0.02),
            (cx - size * 0.21, cy - size * 0.16),
            (cx - size * 0.13, cy - size * 0.08),
            (cx - size * 0.20, cy + size * 0.05),
        ],
        fill=(*dark, 200),
        outline=(*amber, 170),
    )
    draw.polygon(
        [
            (cx + size * 0.30, cy - size * 0.02),
            (cx + size * 0.21, cy - size * 0.16),
            (cx + size * 0.13, cy - size * 0.08),
            (cx + size * 0.20, cy + size * 0.05),
        ],
        fill=(*dark, 200),
        outline=(*amber, 170),
    )

    # subtle pulse arcs
    pulse_r = size * 0.35
    draw.arc(
        [cx - pulse_r, cy - pulse_r, cx + pulse_r, cy + pulse_r],
        20,
        95,
        fill=(*amber, 180),
        width=max(2, size // 50),
    )
    draw.arc(
        [cx - pulse_r, cy - pulse_r, cx + pulse_r, cy + pulse_r],
        205,
        280,
        fill=(*glow, 170),
        width=max(2, size // 50),
    )

    # circular mask
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, size - 1, size - 1], fill=255)
    img.putalpha(mask)

    return img


def main():
    out = Path(__file__).parent / "icon.ico"
    sizes = [256, 128, 64, 48, 32, 16]
    frames = [draw_icon(s) for s in sizes]
    frames[0].save(
        out,
        format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=frames[1:],
    )
    print(f"✅ Icon saved: {out}")


if __name__ == "__main__":
    main()
