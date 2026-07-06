import os
import subprocess
import sys
from pathlib import Path


def create_shortcut():
    project_dir = Path(__file__).resolve().parent
    exe_path = project_dir / "Jarvis.exe"
    icon_path = project_dir / "icon.ico"
    desktop = Path(os.path.expanduser("~")) / "Desktop"
    shortcut_path = desktop / "JARVIS.lnk"

    for stale in [desktop / "Jarvis.lnk", shortcut_path]:
        try:
            if stale.exists():
                stale.unlink()
        except Exception:
            pass

    if not exe_path.exists():
        raise FileNotFoundError(f"Executable not found: {exe_path}")

    if not icon_path.exists():
        icon_path = exe_path

    powershell = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
    script = (
        "$ws = New-Object -ComObject WScript.Shell;"
        "$sc = $ws.CreateShortcut('{0}');"
        "$sc.TargetPath = '{1}';"
        "$sc.WorkingDirectory = '{2}';"
        "$sc.IconLocation = '{3},0';"
        "$sc.Description = 'J.A.R.V.I.S — Local AI Assistant';"
        "$sc.Save()"
    ).format(shortcut_path, exe_path, project_dir, icon_path)

    subprocess.run([powershell, "-NoProfile", "-Command", script], check=True)
    print(f"✅ Shortcut created: {shortcut_path}")


if __name__ == "__main__":
    create_shortcut()
