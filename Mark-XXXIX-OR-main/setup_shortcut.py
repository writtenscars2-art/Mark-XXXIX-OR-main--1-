"""
setup_shortcut.py
1. Generates a sharp JARVIS icon (icon.ico) — MARK XXXIX blue HUD style
2. Creates the desktop shortcut using win32com (handles spaces/parens in paths)
Run once: python setup_shortcut.py
"""
import os
import sys
from pathlib import Path

BASE_DIR    = Path(__file__).resolve().parent
ICON_PATH   = BASE_DIR / "icon.ico"
MAIN_PY     = BASE_DIR / "main.py"
PYTHONW     = Path(sys.executable).parent / "pythonw.exe"
DESKTOP     = Path(os.path.expanduser("~")) / "OneDrive" / "Desktop"

# Fallback desktop paths
if not DESKTOP.exists():
    import winreg
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders")
        DESKTOP = Path(winreg.QueryValueEx(key, "Desktop")[0])
    except Exception:
        DESKTOP = Path.home() / "Desktop"

SHORTCUT_PATH = DESKTOP / "JARVIS.lnk"


# ── 1. Generate JARVIS icon ───────────────────────────────────────────────────

def make_icon():
    from PIL import Image, ImageDraw, ImageFont
    import math

    sizes = [256, 128, 64, 48, 32, 16]
    frames = []

    for size in sizes:
        img  = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        cx, cy = size // 2, size // 2
        r = size // 2 - 2

        # Outer ring — electric blue
        draw.ellipse([cx-r, cy-r, cx+r, cy+r],
                     outline=(0, 212, 255, 255), width=max(2, size//32))

        # Inner ring
        r2 = int(r * 0.78)
        draw.ellipse([cx-r2, cy-r2, cx+r2, cy+r2],
                     outline=(0, 150, 200, 180), width=max(1, size//48))

        # Crosshair lines
        gap = int(r * 0.28)
        lw  = max(1, size // 64)
        draw.line([(cx - r, cy), (cx - gap, cy)], fill=(0, 212, 255, 200), width=lw)
        draw.line([(cx + gap, cy), (cx + r, cy)], fill=(0, 212, 255, 200), width=lw)
        draw.line([(cx, cy - r), (cx, cy - gap)], fill=(0, 212, 255, 200), width=lw)
        draw.line([(cx, cy + gap), (cx, cy + r)], fill=(0, 212, 255, 200), width=lw)

        # Arc segments (HUD brackets)
        arc_r = int(r * 0.90)
        arc_rect = [cx - arc_r, cy - arc_r, cx + arc_r, cy + arc_r]
        for start in [20, 110, 200, 290]:
            draw.arc(arc_rect, start=start, end=start + 60,
                     fill=(0, 212, 255, 255), width=max(2, size // 24))

        # Centre fill — deep navy
        cf = int(r * 0.55)
        draw.ellipse([cx-cf, cy-cf, cx+cf, cy+cf],
                     fill=(0, 8, 20, 240))

        # "J" letter in centre
        font_size = max(10, int(size * 0.38))
        try:
            font = ImageFont.truetype("C:/Windows/Fonts/courbd.ttf", font_size)
        except Exception:
            try:
                font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", font_size)
            except Exception:
                font = ImageFont.load_default()

        text  = "J"
        bbox  = draw.textbbox((0, 0), text, font=font)
        tw    = bbox[2] - bbox[0]
        th    = bbox[3] - bbox[1]
        draw.text((cx - tw // 2, cy - th // 2 - bbox[1]),
                  text, font=font, fill=(0, 212, 255, 255))

        frames.append(img)

    frames[0].save(
        str(ICON_PATH),
        format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=frames[1:]
    )
    print(f"Icon saved: {ICON_PATH}")


# ── 2. Create desktop shortcut via win32com ───────────────────────────────────

def make_shortcut():
    from win32com.client import Dispatch

    shell = Dispatch("WScript.Shell")
    sc    = shell.CreateShortcut(str(SHORTCUT_PATH))
    sc.TargetPath       = str(PYTHONW)
    sc.Arguments        = f'"{MAIN_PY}"'
    sc.WorkingDirectory = str(BASE_DIR)
    sc.IconLocation     = f"{ICON_PATH},0"
    sc.Description      = "J.A.R.V.I.S - NVIDIA NIM + ElevenLabs"
    sc.WindowStyle      = 1   # normal window — pythonw.exe is silent, no console ever appears
    sc.Save()
    print(f"Shortcut created: {SHORTCUT_PATH}")
    print(f"  Target  : {PYTHONW}")
    print(f"  Args    : \"{MAIN_PY}\"")
    print(f"  WorkDir : {BASE_DIR}")
    print(f"  Icon    : {ICON_PATH}")


if __name__ == "__main__":
    print("=== JARVIS Setup ===")
    print()

    print("[1/2] Generating icon...")
    make_icon()

    print("[2/2] Creating desktop shortcut...")
    make_shortcut()

    print()
    print("Done. Double-click JARVIS on your Desktop to launch.")
