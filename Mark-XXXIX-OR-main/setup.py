"""
setup.py — JARVIS first-time setup script.

Run this once before launching main.py:
    python setup.py

What it does:
  1. Checks Python version (3.10+ required)
  2. Upgrades pip silently
  3. Installs all requirements from requirements.txt
  4. Creates config/api_keys.json if it doesn't exist
  5. Verifies critical imports (PyQt6, sounddevice, elevenlabs, openai)
  6. Prints a clear status summary
"""

import subprocess
import sys
import os
import json
from pathlib import Path

# ── Helpers ───────────────────────────────────────────────────────────────────

BASE_DIR    = Path(__file__).resolve().parent
CONFIG_DIR  = BASE_DIR / "config"
API_FILE    = CONFIG_DIR / "api_keys.json"
REQ_FILE    = BASE_DIR  / "requirements.txt"

GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
CYAN   = "\033[96m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

def ok(msg):   print(f"{GREEN}  ✅  {msg}{RESET}")
def warn(msg): print(f"{YELLOW}  ⚠️   {msg}{RESET}")
def err(msg):  print(f"{RED}  ❌  {msg}{RESET}")
def info(msg): print(f"{CYAN}  ℹ️   {msg}{RESET}")
def hdr(msg):  print(f"\n{BOLD}{CYAN}{msg}{RESET}")


# ── Step 1: Python version check ──────────────────────────────────────────────

hdr("═══ JARVIS Setup ═══")
print(f"  Python: {sys.version}")

major, minor = sys.version_info[:2]
if major < 3 or (major == 3 and minor < 10):
    err(f"Python 3.10+ is required. You have {major}.{minor}. Please upgrade.")
    sys.exit(1)
ok(f"Python {major}.{minor} — OK")


# ── Step 2: Upgrade pip ───────────────────────────────────────────────────────

hdr("Upgrading pip...")
try:
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "--upgrade", "pip", "--quiet"],
        check=True
    )
    ok("pip upgraded")
except Exception as e:
    warn(f"pip upgrade failed (non-critical): {e}")


# ── Step 3: Install requirements ─────────────────────────────────────────────

hdr("Installing requirements...")
if not REQ_FILE.exists():
    err(f"requirements.txt not found at {REQ_FILE}")
    sys.exit(1)

try:
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", str(REQ_FILE)],
        capture_output=False,   # show output so user sees progress
        check=True,
    )
    ok("All requirements installed")
except subprocess.CalledProcessError as e:
    err(f"pip install failed (exit code {e.returncode}). Check errors above.")
    sys.exit(1)


# ── Step 4: Create api_keys.json if missing ───────────────────────────────────

hdr("Checking config...")
CONFIG_DIR.mkdir(exist_ok=True)

_DEFAULT_CONFIG = {
    "claude_api_key":          "",
    "nvidia_api_key":          "",
    "nvidia_model":            "meta/llama-3.3-70b-instruct",
    "nvidia_model_deep":       "nvidia/llama-3.3-nemotron-super-49b-v1",
    "groq_api_key":            "",
    "groq_model":              "meta-llama/llama-4-scout-17b-16e-instruct",
    "elevenlabs_api_key":      "",
    "elevenlabs_voice_id":     "",
    "mic_index":               None,
    "default_browser":         "msedge",
    "os_system":               "windows",
    "camera_index":            0,
    "tts_stability":           0.45,
    "tts_similarity_boost":    0.85,
    "tts_style":               0.0,
    "tts_speed":               1.0,
}

if not API_FILE.exists():
    API_FILE.write_text(json.dumps(_DEFAULT_CONFIG, indent=4), encoding="utf-8")
    warn(f"Created {API_FILE} — please fill in your API keys before running JARVIS.")
else:
    # Merge any missing keys into the existing config
    try:
        existing = json.loads(API_FILE.read_text(encoding="utf-8"))
        updated  = False
        for key, default_val in _DEFAULT_CONFIG.items():
            if key not in existing:
                existing[key] = default_val
                updated = True
        if updated:
            API_FILE.write_text(json.dumps(existing, indent=4), encoding="utf-8")
            info("Added missing keys to api_keys.json")
        ok(f"Config found: {API_FILE}")

        # Check which API keys are filled in
        missing_keys = []
        for k in ("groq_api_key", "elevenlabs_api_key", "elevenlabs_voice_id"):
            if not existing.get(k, "").strip():
                missing_keys.append(k)
        if missing_keys:
            warn(f"Missing API keys in config: {', '.join(missing_keys)}")
            info("Edit config/api_keys.json to add them before running JARVIS.")
        else:
            ok("All required API keys are set")
    except Exception as e:
        warn(f"Could not validate config: {e}")


# ── Step 5: Verify critical imports ──────────────────────────────────────────

hdr("Verifying critical packages...")

_checks = [
    ("PyQt6",         "from PyQt6.QtWidgets import QApplication"),
    ("sounddevice",   "import sounddevice"),
    ("numpy",         "import numpy"),
    ("openai",        "from openai import OpenAI"),
    ("elevenlabs",    "from elevenlabs import ElevenLabs"),
    ("requests",      "import requests"),
    ("psutil",        "import psutil"),
    ("pyautogui",     "import pyautogui"),
    ("pyperclip",     "import pyperclip"),
    ("SpeechRecog.",  "import speech_recognition"),
    ("PIL/Pillow",    "from PIL import Image"),
    ("mss",           "import mss"),
    ("pywin32",       "import win32com.client"),
    ("ddgs",          "from ddgs import DDGS"),
    ("pygetwindow",   "import pygetwindow"),
    ("send2trash",    "from send2trash import send2trash"),
]

failed = []
for name, stmt in _checks:
    try:
        exec(stmt)
        ok(f"{name}")
    except ImportError as e:
        err(f"{name} — import failed: {e}")
        failed.append(name)
    except Exception:
        ok(f"{name} (loaded with warnings)")

# Optional packages — warn only
_optional = [
    ("pycaw",         "from pycaw.pycaw import AudioUtilities"),
    ("screen-bright", "import screen_brightness_control"),
    ("yt-transcript", "from youtube_transcript_api import YouTubeTranscriptApi"),
    ("pywinauto",     "from pywinauto import Application"),
    ("win10toast",    "from win10toast import ToastNotifier"),
]
hdr("Optional packages...")
for name, stmt in _optional:
    try:
        exec(stmt)
        ok(f"{name}")
    except ImportError:
        warn(f"{name} — not installed (optional, some features limited)")
    except Exception:
        ok(f"{name}")


# ── Step 6: Summary ───────────────────────────────────────────────────────────

hdr("Setup Summary")
if failed:
    err(f"{len(failed)} package(s) failed to import: {', '.join(failed)}")
    info("Try running:  pip install " + " ".join(failed))
    print(f"\n{YELLOW}⚠️  Setup completed with issues. Fix the errors above before running JARVIS.{RESET}\n")
else:
    print(f"\n{GREEN}{BOLD}✅  Setup complete! Run:  python main.py{RESET}\n")
