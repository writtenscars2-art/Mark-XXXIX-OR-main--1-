"""
send_message.py — Universal messaging for JARVIS.

Supported platforms:
  WhatsApp  — Windows desktop app (most reliable)
  Telegram  — Windows desktop app
  Instagram — Browser-based (instagram.com/direct/new/)
  Discord   — Windows desktop app
  Signal    — Windows desktop app
  Messenger — Browser-based (messenger.com/new)
  Generic   — Any desktop messaging app (open → Ctrl+F → type → enter)

Uses pyperclip for clipboard-based typing so Unicode/emoji work correctly.
All responses address the user as "boss".
"""

import json
import subprocess
import time
from pathlib import Path

try:
    import pyautogui
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE    = 0.06
    _GUI = True
except ImportError:
    _GUI = False

try:
    import pyperclip
    _CLIP = True
except ImportError:
    _CLIP = False


def _get_config() -> dict:
    try:
        cfg_path = Path(__file__).resolve().parent.parent / "config" / "api_keys.json"
        return json.loads(cfg_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _get_browser_exe() -> str:
    cfg     = _get_config()
    browser = cfg.get("default_browser", "msedge").strip().lower()
    import shutil
    exe_map = {"msedge": "msedge", "edge": "msedge", "chrome": "chrome",
               "firefox": "firefox", "brave": "brave"}
    exe = exe_map.get(browser, "msedge")
    if shutil.which(exe):
        return exe
    candidates = {
        "msedge": [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                   r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"],
        "chrome": [r"C:\Program Files\Google\Chrome\Application\chrome.exe"],
        "firefox":[r"C:\Program Files\Mozilla Firefox\firefox.exe"],
    }
    for p in candidates.get(exe, []):
        if Path(p).exists():
            return p
    return exe


def _type_text(text: str):
    """Type text using clipboard (handles Unicode, emoji, special chars)."""
    if not _GUI:
        return
    if _CLIP:
        pyperclip.copy(text)
        time.sleep(0.1)
        pyautogui.hotkey("ctrl", "v")
    else:
        pyautogui.write(text, interval=0.04)


def _open_app(app_name: str) -> bool:
    """Open an app via Windows Start search."""
    if not _GUI:
        return False
    try:
        pyautogui.press("win")
        time.sleep(0.5)
        _type_text(app_name)
        time.sleep(0.6)
        pyautogui.press("enter")
        time.sleep(2.5)
        return True
    except Exception as e:
        print(f"[SendMessage] Could not open {app_name}: {e}")
        return False


def _open_url_in_browser(url: str):
    """Open a URL in the configured default browser."""
    exe = _get_browser_exe()
    try:
        subprocess.Popen([exe, url], stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
    except Exception:
        import webbrowser
        webbrowser.open(url)
    time.sleep(4.0)   # wait for page/app load


# ── Platform senders ──────────────────────────────────────────────────────────

def _send_whatsapp(receiver: str, message: str) -> str:
    """Send via WhatsApp Windows desktop app."""
    if not _GUI:
        return "pyautogui not available for WhatsApp."
    try:
        if not _open_app("WhatsApp"):
            return "Could not open WhatsApp, boss."

        # Search for contact
        pyautogui.hotkey("ctrl", "f")
        time.sleep(0.5)
        pyautogui.hotkey("ctrl", "a")
        _type_text(receiver)
        time.sleep(1.2)
        pyautogui.press("enter")
        time.sleep(1.0)

        # Type and send message
        _type_text(message)
        time.sleep(0.3)
        pyautogui.press("enter")
        time.sleep(0.5)

        return f"Message sent to {receiver} via WhatsApp, boss."
    except Exception as e:
        return f"WhatsApp error: {e}"


def _send_telegram(receiver: str, message: str) -> str:
    """Send via Telegram Windows desktop app."""
    if not _GUI:
        return "pyautogui not available for Telegram."
    try:
        if not _open_app("Telegram"):
            return "Could not open Telegram, boss."

        # Ctrl+F opens search in Telegram
        pyautogui.hotkey("ctrl", "f")
        time.sleep(0.5)
        _type_text(receiver)
        time.sleep(1.2)
        pyautogui.press("enter")
        time.sleep(0.8)

        _type_text(message)
        time.sleep(0.3)
        pyautogui.press("enter")

        return f"Message sent to {receiver} via Telegram, boss."
    except Exception as e:
        return f"Telegram error: {e}"


def _send_instagram(receiver: str, message: str) -> str:
    """Send via Instagram DM in the browser."""
    if not _GUI:
        return "pyautogui not available for Instagram."
    try:
        _open_url_in_browser("https://www.instagram.com/direct/new/")

        # The search box has focus after load — type the contact name
        pyautogui.hotkey("ctrl", "a")
        time.sleep(0.2)
        _type_text(receiver)
        time.sleep(1.8)

        # Select first result
        pyautogui.press("down")
        time.sleep(0.4)
        pyautogui.press("enter")
        time.sleep(0.5)

        # Click the Next/Chat button (usually accessible via Tab+Enter)
        for _ in range(3):
            pyautogui.press("tab")
            time.sleep(0.15)
        pyautogui.press("enter")
        time.sleep(2.5)

        # Type and send
        _type_text(message)
        time.sleep(0.3)
        pyautogui.press("enter")

        return f"Message sent to {receiver} via Instagram, boss."
    except Exception as e:
        return f"Instagram error: {e}"


def _send_discord(receiver: str, message: str) -> str:
    """Send via Discord Windows desktop app."""
    if not _GUI:
        return "pyautogui not available for Discord."
    try:
        if not _open_app("Discord"):
            return "Could not open Discord, boss."

        # Ctrl+K opens Quick Switcher for searching users/channels
        pyautogui.hotkey("ctrl", "k")
        time.sleep(0.6)
        _type_text(receiver)
        time.sleep(1.2)
        pyautogui.press("enter")
        time.sleep(0.8)

        _type_text(message)
        time.sleep(0.3)
        pyautogui.press("enter")

        return f"Message sent to {receiver} via Discord, boss."
    except Exception as e:
        return f"Discord error: {e}"


def _send_signal(receiver: str, message: str) -> str:
    """Send via Signal Windows desktop app."""
    if not _GUI:
        return "pyautogui not available for Signal."
    try:
        if not _open_app("Signal"):
            return "Could not open Signal, boss."

        # Ctrl+F or just typing opens search in Signal
        pyautogui.hotkey("ctrl", "f")
        time.sleep(0.5)
        _type_text(receiver)
        time.sleep(1.2)
        pyautogui.press("enter")
        time.sleep(0.8)

        _type_text(message)
        time.sleep(0.3)
        pyautogui.press("enter")

        return f"Message sent to {receiver} via Signal, boss."
    except Exception as e:
        return f"Signal error: {e}"


def _send_messenger(receiver: str, message: str) -> str:
    """Send via Facebook Messenger in the browser."""
    if not _GUI:
        return "pyautogui not available for Messenger."
    try:
        _open_url_in_browser("https://www.messenger.com/new")

        # Type the contact name in the search field
        pyautogui.hotkey("ctrl", "a")
        time.sleep(0.2)
        _type_text(receiver)
        time.sleep(1.8)

        pyautogui.press("down")
        time.sleep(0.4)
        pyautogui.press("enter")
        time.sleep(2.0)

        _type_text(message)
        time.sleep(0.3)
        pyautogui.press("enter")

        return f"Message sent to {receiver} via Messenger, boss."
    except Exception as e:
        return f"Messenger error: {e}"


def _send_generic(platform: str, receiver: str, message: str) -> str:
    """
    Generic sender — works for any desktop messaging app.
    Opens app → Ctrl+F to search contact → Enter → type → Enter.
    """
    if not _GUI:
        return f"pyautogui not available for {platform}."
    try:
        if not _open_app(platform):
            return f"Could not open {platform}, boss."

        pyautogui.hotkey("ctrl", "f")
        time.sleep(0.5)
        _type_text(receiver)
        time.sleep(1.2)
        pyautogui.press("enter")
        time.sleep(0.8)

        _type_text(message)
        time.sleep(0.3)
        pyautogui.press("enter")

        return f"Message sent to {receiver} via {platform}, boss."
    except Exception as e:
        return f"{platform} error: {e}"


# ── Public entry point ────────────────────────────────────────────────────────

def send_message(
    parameters:     dict,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    """
    Send a message via a messaging platform.

    parameters:
        receiver     : Contact name or username
        message_text : The message to send
        platform     : whatsapp | telegram | instagram | discord |
                       signal | messenger | <any app name>
                       (default: whatsapp)
    """
    params       = parameters or {}
    receiver     = params.get("receiver",     "").strip()
    message_text = params.get("message_text", "").strip()
    platform     = params.get("platform",     "whatsapp").strip().lower()

    if not receiver:
        return "Please specify who to send the message to, boss."
    if not message_text:
        return "Please specify what message to send, boss."

    print(f"[SendMessage] {platform} → {receiver}: {message_text[:50]}")
    if player:
        player.write_log(f"[msg] {platform} → {receiver}")

    if any(x in platform for x in ("whatsapp", "wp", "wapp", "wa")):
        result = _send_whatsapp(receiver, message_text)

    elif any(x in platform for x in ("telegram", "tg")):
        result = _send_telegram(receiver, message_text)

    elif any(x in platform for x in ("instagram", "ig", "insta")):
        result = _send_instagram(receiver, message_text)

    elif any(x in platform for x in ("discord", "dc")):
        result = _send_discord(receiver, message_text)

    elif "signal" in platform:
        result = _send_signal(receiver, message_text)

    elif any(x in platform for x in ("messenger", "facebook messenger", "fb messenger")):
        result = _send_messenger(receiver, message_text)

    else:
        # Try to open any app by name generically
        result = _send_generic(platform, receiver, message_text)

    print(f"[SendMessage] {result}")
    if player:
        player.write_log(f"[msg] {result[:60]}")

    return result
