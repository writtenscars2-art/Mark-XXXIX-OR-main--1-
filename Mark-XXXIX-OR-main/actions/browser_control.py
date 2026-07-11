"""
browser_control.py — Controls the user's actual default browser.

NO Playwright. NO separate browser instance.
Uses subprocess to open/navigate URLs in the user's real browser,
and pyautogui for keyboard/mouse control of whatever window is open.

JARVIS controls YOUR browser, not a sandbox.
"""

import json
import platform
import shutil
import subprocess
import sys
import time
import re
from pathlib import Path
from urllib.parse import quote_plus

try:
    import pyautogui
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.05
    _GUI = True
except ImportError:
    _GUI = False

try:
    import pyperclip
    _CLIP = True
except ImportError:
    _CLIP = False


def _get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

_CONFIG_PATH = _get_base_dir() / "config" / "api_keys.json"
_OS = platform.system()


def _load_config() -> dict:
    try:
        return json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _get_browser_exe(incognito: bool = False) -> tuple[str, list[str]]:
    """
    Returns (executable_path, extra_args).
    Incognito flag adds the appropriate private-mode argument.
    """
    cfg     = _load_config()
    browser = cfg.get("default_browser", "msedge").strip().lower()

    exe_map = {
        "msedge": "msedge", "edge": "msedge",
        "chrome": "chrome", "firefox": "firefox",
        "brave":  "brave",  "opera":   "opera",
    }
    exe = exe_map.get(browser, "msedge")

    # Private/incognito flags per browser
    incognito_flags = {
        "msedge":  ["--inprivate"],
        "chrome":  ["--incognito"],
        "firefox": ["--private-window"],
        "brave":   ["--incognito"],
        "opera":   ["--private"],
    }
    extra = incognito_flags.get(exe, []) if incognito else []

    # Check PATH first
    if shutil.which(exe):
        return exe, extra

    # Hard-coded Windows install paths
    candidates = {
        "msedge": [
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        ],
        "chrome": [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ],
        "firefox": [
            r"C:\Program Files\Mozilla Firefox\firefox.exe",
            r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe",
        ],
        "brave": [
            r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
        ],
    }
    for path in candidates.get(exe, []):
        if Path(path).exists():
            return path, extra

    return "", extra


def _open_url(url: str, incognito: bool = False, new_tab: bool = False) -> str:
    """Open a URL in the user's default browser."""
    if not url.startswith(("http://", "https://", "about:", "file:")):
        url = "https://" + url

    browser_exe, extra = _get_browser_exe(incognito=incognito)
    tab_flag = ["--new-tab"] if new_tab and "firefox" not in browser_exe else []
    print(f"[Browser] Opening {url} | incognito={incognito} | exe={browser_exe or 'default'}")

    try:
        if browser_exe:
            subprocess.Popen(
                [browser_exe] + extra + tab_flag + [url],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            subprocess.Popen(
                ["cmd", "/c", "start", "", url],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                shell=False,
            )
        time.sleep(0.8)
        mode = " (private)" if incognito else ""
        return f"Opened{mode}: {url}"
    except Exception as e:
        try:
            import webbrowser
            webbrowser.open(url)
            return f"Opened: {url}"
        except Exception as e2:
            return f"Could not open browser: {e2}"


def _open_browser_only(incognito: bool = False) -> str:
    """Open browser without a URL."""
    browser_exe, extra = _get_browser_exe(incognito=incognito)
    try:
        if browser_exe:
            subprocess.Popen(
                [browser_exe] + extra,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            time.sleep(0.5)
            mode = " (private)" if incognito else ""
            return f"Browser opened{mode}, boss."
        else:
            import webbrowser
            webbrowser.open("about:blank")
            return "Browser opened, boss."
    except Exception as e:
        return f"Could not open browser: {e}"


def _search_web(query: str, engine: str = "google", incognito: bool = False) -> str:
    """Open a web search in the default browser."""
    q = quote_plus(query)
    engines = {
        "google":     f"https://www.google.com/search?q={q}",
        "bing":       f"https://www.bing.com/search?q={q}",
        "duckduckgo": f"https://duckduckgo.com/?q={q}",
        "youtube":    f"https://www.youtube.com/results?search_query={q}",
        "amazon":     f"https://www.amazon.com/s?k={q}",
        "reddit":     f"https://www.reddit.com/search/?q={q}",
        "twitter":    f"https://twitter.com/search?q={q}",
        "wikipedia":  f"https://en.wikipedia.org/w/index.php?search={q}",
    }
    url = engines.get(engine.lower(), engines["google"])
    return _open_url(url, incognito=incognito)


def _navigate_current(url: str) -> str:
    """Navigate the currently focused browser window to a URL using Ctrl+L."""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    if not _GUI:
        return _open_url(url)

    try:
        pyautogui.hotkey("ctrl", "l")
        time.sleep(0.35)
        pyautogui.hotkey("ctrl", "a")
        if _CLIP:
            pyperclip.copy(url)
            pyautogui.hotkey("ctrl", "v")
        else:
            pyautogui.write(url, interval=0.02)
        time.sleep(0.2)
        pyautogui.press("enter")
        time.sleep(0.8)
        return f"Navigated to: {url}"
    except Exception:
        return _open_url(url)


def _new_tab(url: str = "") -> str:
    if not _GUI:
        return _open_url(url) if url else "pyautogui not available."
    try:
        pyautogui.hotkey("ctrl", "t")
        time.sleep(0.4)
        if url:
            return _navigate_current(url)
        return "New tab opened."
    except Exception as e:
        return f"New tab error: {e}"


def _close_tab() -> str:
    if not _GUI:
        return "pyautogui not available."
    pyautogui.hotkey("ctrl", "w")
    return "Tab closed."


def _go_back() -> str:
    if not _GUI:
        return "pyautogui not available."
    pyautogui.hotkey("alt", "left")
    return "Went back."


def _go_forward() -> str:
    if not _GUI:
        return "pyautogui not available."
    pyautogui.hotkey("alt", "right")
    return "Went forward."


def _refresh() -> str:
    if not _GUI:
        return "pyautogui not available."
    pyautogui.press("f5")
    return "Page refreshed."


def _scroll_page(direction: str = "down", amount: int = 500) -> str:
    if not _GUI:
        return "pyautogui not available."
    try:
        scroll = -amount if direction == "down" else amount
        pyautogui.scroll(scroll)
        return f"Scrolled {direction}."
    except Exception as e:
        return f"Scroll error: {e}"


def _type_in_browser(text: str) -> str:
    if not _GUI:
        return "pyautogui not available."
    try:
        if _CLIP:
            pyperclip.copy(text)
            pyautogui.hotkey("ctrl", "v")
        else:
            pyautogui.write(text, interval=0.03)
        return f"Typed: {text[:60]}"
    except Exception as e:
        return f"Type error: {e}"


def _press_key(key: str) -> str:
    if not _GUI:
        return "pyautogui not available."
    try:
        pyautogui.press(key)
        return f"Pressed: {key}"
    except Exception as e:
        return f"Key error: {e}"


def _zoom(direction: str = "in") -> str:
    if not _GUI:
        return "pyautogui not available."
    key = "equal" if direction == "in" else "minus"
    pyautogui.hotkey("ctrl", key)
    return f"Zoomed {direction}."


def _find_in_page(text: str) -> str:
    if not _GUI:
        return "pyautogui not available."
    pyautogui.hotkey("ctrl", "f")
    time.sleep(0.3)
    if _CLIP:
        pyperclip.copy(text)
        pyautogui.hotkey("ctrl", "v")
    else:
        pyautogui.write(text, interval=0.03)
    return f"Searching page for: {text}"


def _bookmark_page() -> str:
    if not _GUI:
        return "pyautogui not available."
    pyautogui.hotkey("ctrl", "d")
    time.sleep(0.3)
    pyautogui.press("enter")
    return "Page bookmarked."


def _open_downloads() -> str:
    if not _GUI:
        return "pyautogui not available."
    pyautogui.hotkey("ctrl", "j")
    return "Downloads opened."


def _open_history() -> str:
    if not _GUI:
        return "pyautogui not available."
    pyautogui.hotkey("ctrl", "h")
    return "History opened."


def _open_settings() -> str:
    """Open browser settings page."""
    cfg     = _load_config()
    browser = cfg.get("default_browser", "msedge").strip().lower()
    urls = {
        "msedge":  "edge://settings",
        "edge":    "edge://settings",
        "chrome":  "chrome://settings",
        "firefox": "about:preferences",
        "brave":   "brave://settings",
    }
    url = urls.get(browser, "edge://settings")
    return _open_url(url)


def _mute_tab() -> str:
    """Mute/unmute current tab (Chrome/Edge only)."""
    # There's no universal keyboard shortcut; focus the tab bar area is platform-specific.
    # Best we can do is inform the user.
    return "To mute a tab, right-click the tab and select 'Mute tab', boss."


def _get_page_text() -> str:
    """Copy all visible text from the current page via Ctrl+A, Ctrl+C."""
    if not _GUI:
        return "pyautogui not available."
    try:
        pyautogui.hotkey("ctrl", "a")
        time.sleep(0.3)
        pyautogui.hotkey("ctrl", "c")
        time.sleep(0.4)
        if _CLIP:
            text = pyperclip.paste()
            return text[:2000] if text else "Nothing copied from page."
        return "Text copied to clipboard (pyperclip unavailable to read)."
    except Exception as e:
        return f"Get text error: {e}"


def _screenshot_page() -> str:
    """Take a full-page screenshot using the browser."""
    if not _GUI:
        return "pyautogui not available."
    # Use browser's built-in screenshot if available (Edge/Chrome: F12 → DevTools)
    # Simplest cross-browser method: pyautogui screenshot
    try:
        import pyautogui as _pg
        from pathlib import Path as _P
        import datetime
        ts   = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        path = _P.home() / "Desktop" / f"browser_screenshot_{ts}.png"
        _pg.screenshot(str(path))
        return f"Screenshot saved: {path}"
    except Exception as e:
        return f"Screenshot failed: {e}"


# ── Public API ────────────────────────────────────────────────────────────────

def browser_control(
    parameters: dict,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    """
    Controls the user's actual default browser.
    No Playwright — subprocess for URLs, pyautogui for interaction.

    actions:
        open / go_to / navigate  — open a URL (add incognito=true for private)
        open_browser             — just open the browser (no URL)
        search                   — search in browser (engine: google/bing/youtube/etc.)
        navigate_current         — navigate current window to URL
        new_tab                  — open new tab (+ optional URL)
        close_tab                — close current tab
        scroll                   — scroll the page (direction: up/down)
        click                    — Ctrl+F search on page for text
        type                     — type text into focused input
        back / forward           — browser navigation
        refresh / reload         — reload page
        press                    — press a keyboard key
        zoom_in / zoom_out       — browser zoom
        find                     — Ctrl+F in-page search
        bookmark                 — bookmark current page
        downloads                — open downloads
        history                  — open history
        settings                 — open browser settings
        get_text                 — copy all page text
        screenshot               — screenshot current page
    """
    params   = parameters or {}
    action   = params.get("action", "").lower().strip()
    url      = params.get("url", "").strip()
    query    = params.get("query", "").strip()
    incognito = bool(params.get("incognito", False))

    result = "Unknown browser action."

    try:
        # ── URL / navigate actions ─────────────────────────────────────────
        if action in ("go_to", "open", "navigate", "visit"):
            if url:
                result = _open_url(url, incognito=incognito)
            elif query:
                # If query looks like a URL, open it directly
                if re.match(r"^(https?://|www\.)", query) or "." in query.split()[0]:
                    result = _open_url(query, incognito=incognito)
                else:
                    result = _search_web(query, incognito=incognito)
            else:
                result = _open_browser_only(incognito=incognito)

        elif action == "open_browser":
            result = _open_browser_only(incognito=incognito)

        elif action == "search":
            q      = query or params.get("text", "")
            engine = params.get("engine", "google")
            result = _search_web(q, engine=engine, incognito=incognito) if q \
                     else "No search query provided."

        elif action == "navigate_current":
            result = _navigate_current(url or query)

        elif action == "new_tab":
            result = _new_tab(url)

        elif action == "close_tab":
            result = _close_tab()

        elif action == "scroll":
            result = _scroll_page(
                params.get("direction", "down"),
                int(params.get("amount", 500))
            )

        elif action == "click":
            text = params.get("text") or params.get("selector") or query
            result = _find_in_page(text) if text else "No click target."

        elif action == "type":
            result = _type_in_browser(params.get("text", "") or query)

        elif action == "back":
            result = _go_back()

        elif action == "forward":
            result = _go_forward()

        elif action in ("refresh", "reload"):
            result = _refresh()

        elif action == "press":
            result = _press_key(params.get("key", "enter"))

        elif action in ("zoom_in", "zoom in"):
            result = _zoom("in")

        elif action in ("zoom_out", "zoom out"):
            result = _zoom("out")

        elif action == "find":
            text = params.get("text", "") or query
            result = _find_in_page(text) if text else "No search text."

        elif action == "bookmark":
            result = _bookmark_page()

        elif action == "downloads":
            result = _open_downloads()

        elif action == "history":
            result = _open_history()

        elif action == "settings":
            result = _open_settings()

        elif action in ("get_text", "read_page"):
            result = _get_page_text()

        elif action == "screenshot":
            result = _screenshot_page()

        else:
            # Treat unknown action as a URL if it looks like one
            if re.match(r"^(https?://|www\.)", action) or ("." in action and " " not in action):
                result = _open_url(action, incognito=incognito)
            elif action:
                # Last resort — try as a Google search
                result = _search_web(action, incognito=incognito)
            else:
                result = "No action or URL provided."

    except Exception as e:
        result = f"Browser error: {e}"

    print(f"[Browser] {result[:100]}")
    if player:
        player.write_log(f"[Browser] {result[:60]}")

    return result
