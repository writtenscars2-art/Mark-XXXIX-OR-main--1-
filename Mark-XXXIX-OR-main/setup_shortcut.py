"""
setup_shortcut.py — Creates a desktop shortcut for JARVIS.

Approach:
  - Shortcut target: python.exe jarvis_launcher.py
  - jarvis_launcher.py hides the console via Win32 API, then calls main()
  - This is the most reliable method — no VBS, no pythonw dependency
  - Single-instance guard in main.py prevents duplicate JARVIS instances

Run once: python setup_shortcut.py
"""

import os
import sys
from pathlib import Path


def get_desktop() -> Path:
    """Return the user's desktop path (handles OneDrive Desktop)."""
    onedrive = Path.home() / "OneDrive" / "Desktop"
    if onedrive.exists():
        return onedrive
    desk = Path.home() / "Desktop"
    if desk.exists():
        return desk
    try:
        import ctypes
        buf = ctypes.create_unicode_buffer(512)
        ctypes.windll.shell32.SHGetFolderPathW(0, 0x0000, 0, 0, buf)
        p = Path(buf.value)
        if p.exists():
            return p
    except Exception:
        pass
    return Path.home() / "Desktop"


def main():
    base_dir     = Path(__file__).resolve().parent
    launcher_py  = base_dir / "jarvis_launcher.py"
    icon_path    = base_dir / "icon.ico"
    desktop      = get_desktop()
    lnk_path     = desktop / "JARVIS.lnk"

    python_exe = Path(sys.executable)
    if not python_exe.exists():
        print(f"ERROR: Python not found: {python_exe}")
        sys.exit(1)

    if not launcher_py.exists():
        print(f"ERROR: jarvis_launcher.py not found: {launcher_py}")
        sys.exit(1)

    print(f"Python  : {python_exe}")
    print(f"Launcher: {launcher_py}")
    print(f"Icon    : {icon_path}")
    print(f"Desktop : {desktop}")

    try:
        from win32com.client import Dispatch
    except ImportError:
        print("Installing pywin32...")
        import subprocess
        subprocess.run([str(python_exe), "-m", "pip", "install", "pywin32"], check=True)
        from win32com.client import Dispatch

    shell    = Dispatch("WScript.Shell")
    shortcut = shell.CreateShortcut(str(lnk_path))

    # Target: python.exe
    shortcut.TargetPath       = str(python_exe)
    # Arguments: path to launcher (quoted to handle spaces)
    shortcut.Arguments        = f'"{launcher_py}"'
    shortcut.WorkingDirectory = str(base_dir)
    shortcut.WindowStyle      = 1      # normal (Qt manages its own window visibility)
    shortcut.Description      = "Launch JARVIS AI Assistant"

    if icon_path.exists():
        shortcut.IconLocation = f"{icon_path},0"

    shortcut.save()

    if lnk_path.exists():
        print(f"\nSUCCESS!")
        print(f"  Shortcut : {lnk_path}")
        print(f"  Target   : {python_exe}")
        print(f"  Args     : \"{launcher_py}\"")
        print(f"\nDouble-click JARVIS on your Desktop to launch.")
        print("Only one instance will run at a time (single-instance guard active).")
    else:
        print("ERROR: Shortcut not created.")
        sys.exit(1)


if __name__ == "__main__":
    main()
