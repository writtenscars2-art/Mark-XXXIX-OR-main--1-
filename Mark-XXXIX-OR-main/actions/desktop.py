"""
desktop.py — Windows desktop control for JARVIS.

Actions: wallpaper, organize, clean, list, stats,
         create_shortcut, pin_to_taskbar, show_desktop,
         open_desktop_folder, task (AI-powered via NVIDIA/Groq).
"""

import os
import sys
import json
import shutil
import subprocess
import tempfile
import platform
from pathlib import Path
from datetime import datetime

try:
    import pyautogui
    _PYAUTOGUI = True
except ImportError:
    _PYAUTOGUI = False

_OS = platform.system()   # "Windows" | "Darwin" | "Linux"


def _get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


_CONFIG_PATH = _get_base_dir() / "config" / "api_keys.json"


def _load_config() -> dict:
    try:
        return json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _get_desktop() -> Path:
    if _OS == "Linux":
        xdg = os.environ.get("XDG_DESKTOP_DIR", "")
        if xdg and Path(xdg).exists():
            return Path(xdg)
    return Path.home() / "Desktop"


# ── AI code generation (NVIDIA NIM / Groq) ────────────────────────────────────

def _ask_ai_for_desktop_action(task: str) -> str:
    """Generate safe desktop automation code via NVIDIA NIM (no claude_client)."""
    try:
        from openai import OpenAI

        cfg        = _load_config()
        groq_key   = cfg.get("groq_api_key",   "").strip()
        nvidia_key = cfg.get("nvidia_api_key",  "").strip()

        desktop = str(_get_desktop())
        prompt  = (
            f"OS: {_OS}\nDesktop path: {desktop}\n\n"
            "Generate SAFE Python code for this desktop task using ONLY:\n"
            "- pathlib.Path (read-only operations, no deletion)\n"
            "- shutil.copy2, shutil.copytree, shutil.disk_usage\n"
            "- os.path (read-only)\n"
            "- time.sleep\n"
            "- pyautogui (if available)\n"
            "NO file deletion, NO subprocess, NO exec/eval, NO imports.\n"
            "If unsafe, output exactly: UNSAFE\n"
            f"Output ONLY raw Python code.\nTask: {task}"
        )
        system = "You are a code generator. Output only raw Python code, nothing else."

        if groq_key and groq_key not in ("", "YOUR_GROQ_KEY_HERE"):
            client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=groq_key)
            model  = cfg.get("groq_model", "llama-3.3-70b-versatile")
        elif nvidia_key:
            client = OpenAI(base_url="https://integrate.api.nvidia.com/v1", api_key=nvidia_key)
            model  = cfg.get("nvidia_model", "meta/llama-3.3-70b-instruct")
        else:
            return "ERROR: No AI key configured."

        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user",   "content": prompt},
            ],
            max_tokens=600,
            temperature=0.1,
        )
        return (resp.choices[0].message.content or "").strip()

    except Exception as e:
        return f"ERROR: {e}"


def _execute_generated_code(code: str, player=None) -> str:
    if not code or code.strip() in ("UNSAFE", "") or code.startswith("ERROR:"):
        return code if code.startswith("ERROR:") else "That action cannot be performed safely."

    # Strip markdown fences if present
    import re
    code = re.sub(r"^```[a-zA-Z]*\r?\n?", "", code.strip())
    code = re.sub(r"\r?\n?```\s*$", "", code)
    code = code.strip()

    output_lines: list[str] = []

    sandbox: dict = {
        "__builtins__": {
            "print": lambda *a: output_lines.append(" ".join(str(x) for x in a)),
            "len": len, "str": str, "int": int, "float": float,
            "bool": bool, "list": list, "dict": dict, "tuple": tuple,
            "range": range, "enumerate": enumerate, "sorted": sorted,
            "isinstance": isinstance, "hasattr": hasattr, "getattr": getattr,
            "max": max, "min": min, "sum": sum, "abs": abs,
            "zip": zip, "map": map, "filter": filter,
        },
        "Path":    Path,
        "shutil":  type("shutil", (), {
            "copy2":      shutil.copy2,
            "copytree":   shutil.copytree,
            "disk_usage": shutil.disk_usage,
        })(),
        "os_path": os.path,
    }
    if _PYAUTOGUI:
        sandbox["pyautogui"] = pyautogui
    if _OS == "Windows":
        try:
            import ctypes, winreg
            sandbox["ctypes"] = ctypes
            sandbox["winreg"] = type("winreg", (), {
                "OpenKey":           winreg.OpenKey,
                "QueryValueEx":      winreg.QueryValueEx,
                "HKEY_CURRENT_USER": winreg.HKEY_CURRENT_USER,
            })()
        except ImportError:
            pass

    try:
        exec(compile(code, "<jarvis_desktop>", "exec"), sandbox)
        return "\n".join(output_lines) if output_lines else "Done."
    except Exception as e:
        print(f"[Desktop] Exec error: {e}\n{code[:200]}")
        return f"Execution error: {e}"


# ── Wallpaper ─────────────────────────────────────────────────────────────────

def set_wallpaper(image_path: str) -> str:
    path = Path(image_path).expanduser().resolve()
    if not path.exists():
        return f"Image not found: {image_path}"
    if path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".bmp", ".webp"}:
        return f"Unsupported format: {path.suffix}. Use jpg, png, bmp or webp."

    try:
        if _OS == "Windows":
            import ctypes
            if path.suffix.lower() in {".webp", ".png"}:
                try:
                    from PIL import Image
                    bmp_path = Path(tempfile.mktemp(suffix=".bmp"))
                    Image.open(path).convert("RGB").save(bmp_path, "BMP")
                    path = bmp_path
                except ImportError:
                    pass
            ctypes.windll.user32.SystemParametersInfoW(20, 0, str(path), 3)
            return f"Wallpaper set: {path.name}"

        elif _OS == "Darwin":
            script = (
                f'tell application "System Events" to tell every desktop to '
                f'set picture to POSIX file "{path}"'
            )
            subprocess.run(["osascript", "-e", script], capture_output=True)
            return f"Wallpaper set: {path.name}"

        else:
            desktop_env = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()
            uri = f"file://{path}"
            if "gnome" in desktop_env or "unity" in desktop_env:
                subprocess.run(["gsettings", "set", "org.gnome.desktop.background",
                                "picture-uri", uri], capture_output=True)
            elif "kde" in desktop_env:
                script = (
                    f'var d=desktops()[0];d.wallpaperPlugin="org.kde.image";'
                    f'd.currentConfigGroup=["Wallpaper","org.kde.image","General"];'
                    f'd.writeConfig("Image","file://{path}");'
                )
                subprocess.run(["qdbus", "org.kde.plasmashell", "/PlasmaShell",
                                "org.kde.PlasmaShell.evaluateScript", script],
                               capture_output=True)
            elif "xfce" in desktop_env:
                subprocess.run(["xfconf-query", "-c", "xfce4-desktop",
                                "-p", "/backdrop/screen0/monitor0/workspace0/last-image",
                                "-s", str(path)], capture_output=True)
            else:
                subprocess.run(["feh", "--bg-scale", str(path)], capture_output=True)
            return f"Wallpaper set: {path.name}"

    except Exception as e:
        return f"Could not set wallpaper: {e}"


def set_wallpaper_from_url(url: str) -> str:
    try:
        import urllib.request
        suffix = Path(url.split("?")[0]).suffix or ".jpg"
        tmp    = Path(tempfile.mktemp(suffix=suffix))
        urllib.request.urlretrieve(url, str(tmp))
        result = set_wallpaper(str(tmp))
        try:
            tmp.unlink()
        except Exception:
            pass
        return result
    except Exception as e:
        return f"Could not download wallpaper: {e}"


def get_current_wallpaper() -> str:
    try:
        if _OS == "Windows":
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\Desktop")
            val, _ = winreg.QueryValueEx(key, "Wallpaper")
            winreg.CloseKey(key)
            return f"Current wallpaper: {val}"
        elif _OS == "Darwin":
            result = subprocess.run(
                ["osascript", "-e", 'tell app "System Events" to get picture of desktop 1'],
                capture_output=True, text=True
            )
            return f"Current wallpaper: {result.stdout.strip()}"
        else:
            result = subprocess.run(
                ["gsettings", "get", "org.gnome.desktop.background", "picture-uri"],
                capture_output=True, text=True
            )
            return f"Current wallpaper: {result.stdout.strip()}"
    except Exception as e:
        return f"Could not get wallpaper: {e}"


# ── Desktop organization ──────────────────────────────────────────────────────

FILE_TYPE_MAP = {
    "Images":      {".jpg",".jpeg",".png",".gif",".bmp",".webp",".svg",".ico",".heic"},
    "Documents":   {".pdf",".doc",".docx",".txt",".xls",".xlsx",
                    ".ppt",".pptx",".csv",".odt",".ods",".odp"},
    "Videos":      {".mp4",".avi",".mkv",".mov",".wmv",".flv",".webm",".m4v"},
    "Music":       {".mp3",".wav",".flac",".aac",".ogg",".wma",".m4a"},
    "Archives":    {".zip",".rar",".7z",".tar",".gz",".bz2",".xz"},
    "Code":        {".py",".js",".ts",".html",".css",".json",".xml",
                    ".cpp",".java",".cs",".go",".rs",".sh",".php"},
    "Executables": {".exe",".msi",".bat",".cmd",".sh",".appimage",".deb",".rpm"},
}

_SKIP_EXTENSIONS = {
    "Windows": {".lnk", ".url"},
    "Darwin":  {".webloc"},
    "Linux":   {".desktop"},
}


def organize_desktop(mode: str = "by_type") -> str:
    desktop    = _get_desktop()
    skip_exts  = _SKIP_EXTENSIONS.get(_OS, set())
    moved, skipped = [], []

    for item in desktop.iterdir():
        if item.is_dir() or item.name.startswith("."):
            continue
        if item.suffix.lower() in skip_exts:
            continue

        if mode == "by_date":
            mtime       = datetime.fromtimestamp(item.stat().st_mtime)
            folder_name = mtime.strftime("%Y-%m")
        else:
            ext         = item.suffix.lower()
            folder_name = "Others"
            for folder, exts in FILE_TYPE_MAP.items():
                if ext in exts:
                    folder_name = folder
                    break

        target_dir = desktop / folder_name
        target_dir.mkdir(exist_ok=True)
        new_path = target_dir / item.name

        if new_path.exists():
            skipped.append(item.name)
            continue

        shutil.move(str(item), str(new_path))
        moved.append(f"{item.name} → {folder_name}/")

    result = f"Desktop organised ({mode}): {len(moved)} files moved."
    if moved:
        result += "\n" + "\n".join(moved[:8])
        if len(moved) > 8:
            result += f"\n... and {len(moved) - 8} more."
    if skipped:
        result += f"\n{len(skipped)} skipped (name conflict)."
    return result


def list_desktop() -> str:
    desktop = _get_desktop()
    items   = []
    for item in sorted(desktop.iterdir()):
        if item.name.startswith("."):
            continue
        if item.is_dir():
            try:
                count = len(list(item.iterdir()))
            except PermissionError:
                count = "?"
            items.append(f"📁 {item.name}/ ({count} items)")
        else:
            size     = item.stat().st_size
            size_str = (f"{size/1024:.1f} KB" if size < 1024*1024
                        else f"{size/1024/1024:.1f} MB")
            items.append(f"📄 {item.name} ({size_str})")

    if not items:
        return "Desktop is empty."
    return f"Desktop ({len(items)} items):\n" + "\n".join(items)


def clean_desktop() -> str:
    desktop     = _get_desktop()
    skip_exts   = _SKIP_EXTENSIONS.get(_OS, set())
    today       = datetime.now().strftime("%Y-%m-%d")
    archive_dir = desktop / f"Desktop Archive {today}"
    archive_dir.mkdir(exist_ok=True)
    moved = 0
    for item in desktop.iterdir():
        if item.is_dir() or item.name.startswith("."):
            continue
        if item.suffix.lower() in skip_exts:
            continue
        new_path = archive_dir / item.name
        if not new_path.exists():
            shutil.move(str(item), str(new_path))
            moved += 1
    return f"Desktop cleaned: {moved} files archived to '{archive_dir.name}'."


def get_desktop_stats() -> str:
    desktop    = _get_desktop()
    files      = [i for i in desktop.iterdir() if i.is_file()]
    folders    = [i for i in desktop.iterdir() if i.is_dir()]
    total_size = sum(f.stat().st_size for f in files if f.exists())
    size_str   = (f"{total_size/1024:.1f} KB" if total_size < 1024*1024
                  else f"{total_size/1024/1024:.1f} MB")
    return (
        f"Desktop stats ({_OS}):\n"
        f"  Files   : {len(files)}\n"
        f"  Folders : {len(folders)}\n"
        f"  Size    : {size_str}\n"
        f"  Path    : {desktop}"
    )


# ── Windows-specific extras ───────────────────────────────────────────────────

def create_shortcut(target: str, shortcut_name: str = "") -> str:
    """Create a desktop shortcut for an app or file (Windows only)."""
    if _OS != "Windows":
        return "Shortcuts are only supported on Windows."
    try:
        import win32com.client
        target_path = Path(target).resolve()
        name        = shortcut_name or target_path.stem
        lnk_path    = _get_desktop() / f"{name}.lnk"
        shell       = win32com.client.Dispatch("WScript.Shell")
        sc          = shell.CreateShortCut(str(lnk_path))
        sc.TargetPath       = str(target_path)
        sc.WorkingDirectory = str(target_path.parent)
        sc.save()
        return f"Shortcut created: {lnk_path.name}"
    except ImportError:
        # Fallback via PowerShell
        try:
            ps = (
                f'$ws = New-Object -ComObject WScript.Shell; '
                f'$s = $ws.CreateShortcut("{_get_desktop()}\\{shortcut_name or Path(target).stem}.lnk"); '
                f'$s.TargetPath = "{target}"; $s.Save()'
            )
            subprocess.run(["powershell", "-Command", ps],
                           capture_output=True, timeout=8)
            return f"Shortcut created on desktop."
        except Exception as e:
            return f"Could not create shortcut: {e}"
    except Exception as e:
        return f"Could not create shortcut: {e}"


def pin_to_taskbar(app_name: str) -> str:
    """Pin an app to the Windows taskbar via PowerShell verb."""
    if _OS != "Windows":
        return "Taskbar pinning is Windows-only."
    try:
        ps = (
            f'$app = ((New-Object -Com Shell.Application).NameSpace("shell:AppsFolder")'
            f'.Items() | Where-Object {{$_.Name -like "*{app_name}*"}}) | Select-Object -First 1; '
            f'if ($app) {{ $app.Verbs() | Where-Object {{$_.Name -match "pin"}} | '
            f'Select-Object -First 1 | ForEach-Object {{$_.DoIt()}} }}'
        )
        subprocess.run(["powershell", "-Command", ps],
                       capture_output=True, timeout=10)
        return f"Attempted to pin {app_name} to taskbar."
    except Exception as e:
        return f"Could not pin to taskbar: {e}"


def show_desktop() -> str:
    """Show/hide desktop (Win+D)."""
    if _OS == "Windows":
        if _PYAUTOGUI:
            pyautogui.hotkey("win", "d")
            return "Desktop shown, boss."
        try:
            subprocess.run(
                ["powershell", "-Command",
                 '(New-Object -ComObject Shell.Application).ToggleDesktop()'],
                capture_output=True, timeout=5
            )
            return "Desktop toggled, boss."
        except Exception as e:
            return f"Could not show desktop: {e}"
    elif _PYAUTOGUI:
        pyautogui.hotkey("super", "d")
        return "Desktop shown, boss."
    return "Show desktop not supported on this OS."


def open_desktop_folder() -> str:
    """Open the Desktop folder in File Explorer."""
    desktop = _get_desktop()
    try:
        if _OS == "Windows":
            subprocess.Popen(["explorer.exe", str(desktop)])
        elif _OS == "Darwin":
            subprocess.Popen(["open", str(desktop)])
        else:
            subprocess.Popen(["xdg-open", str(desktop)])
        return f"Opened desktop folder: {desktop}"
    except Exception as e:
        return f"Could not open desktop folder: {e}"


# ── Public entry point ────────────────────────────────────────────────────────

def desktop_control(
    parameters: dict = None,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    """
    parameters:
        action : wallpaper | wallpaper_url | current_wallpaper |
                 organize | clean | list | stats |
                 create_shortcut | pin_to_taskbar | show_desktop |
                 open_desktop_folder | task
        path   : image path for 'wallpaper', target for 'create_shortcut'
        url    : image URL for 'wallpaper_url'
        mode   : 'by_type' or 'by_date' for 'organize'
        name   : shortcut/app name
        task   : natural-language description for AI-powered actions
    """
    params = parameters or {}
    action = params.get("action", "").lower().strip()
    task   = params.get("task", "").strip()

    if player:
        player.write_log(f"[desktop] {action or task[:40]}")

    try:
        if action == "wallpaper":
            path = params.get("path", "")
            return set_wallpaper(path) if path else "No image path provided."

        elif action == "wallpaper_url":
            url = params.get("url", "")
            return set_wallpaper_from_url(url) if url else "No URL provided."

        elif action == "current_wallpaper":
            return get_current_wallpaper()

        elif action == "organize":
            return organize_desktop(params.get("mode", "by_type"))

        elif action == "clean":
            return clean_desktop()

        elif action == "list":
            return list_desktop()

        elif action == "stats":
            return get_desktop_stats()

        elif action == "create_shortcut":
            target = params.get("path", "") or params.get("target", "")
            name   = params.get("name", "")
            return create_shortcut(target, name) if target else "No target path provided."

        elif action == "pin_to_taskbar":
            name = params.get("name", "") or params.get("app", "")
            return pin_to_taskbar(name) if name else "No app name provided."

        elif action == "show_desktop":
            return show_desktop()

        elif action == "open_desktop_folder":
            return open_desktop_folder()

        elif action == "task" or task:
            actual_task = task or params.get("description", "")
            if not actual_task:
                return "Please describe what you want to do on the desktop."
            print(f"[Desktop] AI generating action: {actual_task}")
            if player:
                player.write_log("[Desktop] Generating action...")
            code = _ask_ai_for_desktop_action(actual_task)
            return _execute_generated_code(code, player=player)

        else:
            if action:
                code = _ask_ai_for_desktop_action(action)
                return _execute_generated_code(code, player=player)
            return "No action or task specified."

    except Exception as e:
        print(f"[Desktop] Error: {e}")
        return f"Desktop control error: {e}"
