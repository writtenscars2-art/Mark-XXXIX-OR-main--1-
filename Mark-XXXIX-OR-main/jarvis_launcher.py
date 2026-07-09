"""
jarvis_launcher.py — Single-file launcher for JARVIS.

This script is what the desktop shortcut runs.
It:
  1. Hides the console window immediately (Windows only)
  2. Changes working directory to the script's location
  3. Imports and calls main() from main.py
  
No VBS, no cmd.exe, no pythonw needed.
The shortcut target is:  python.exe jarvis_launcher.py
"""

import ctypes
import os
import sys
from pathlib import Path

# ── 1. Hide the console window immediately ────────────────────────────────
# This must happen BEFORE any Qt import so no console flashes
if sys.platform == "win32":
    try:
        # SW_HIDE = 0
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 0)
    except Exception:
        pass

# ── 2. Set working directory to JARVIS project root ──────────────────────
BASE_DIR = Path(__file__).resolve().parent
os.chdir(BASE_DIR)
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# ── 3. Run JARVIS main ────────────────────────────────────────────────────
from main import main
main()
