"""
video_search.py — Multi-platform video search and playback for JARVIS.

Supported platforms:
  YouTube   — search, play, trending, summarize transcript
  TikTok    — search (opens browser)
  Instagram — search Reels (opens browser)
  Twitter/X — search videos (opens browser)
  Reddit    — search video posts (opens browser)
  Facebook  — search videos (opens browser)
  Twitch    — open channel or search streams
  Vimeo     — search videos (opens browser)

All platforms use subprocess to open the user's real browser — no API keys needed.
"""

import json
import re
import sys
import time
import subprocess
import shutil
from pathlib import Path
from urllib.parse import quote_plus

try:
    import requests
    _REQUESTS_OK = True
except ImportError:
    _REQUESTS_OK = False

try:
    from youtube_transcript_api import YouTubeTranscriptApi
    _TRANSCRIPT_OK = True
except ImportError:
    _TRANSCRIPT_OK = False


def _get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BASE_DIR        = _get_base_dir()
API_CONFIG_PATH = BASE_DIR / "config" / "api_keys.json"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

_YT_VIDEO_FILTER = "EgIQAQ%3D%3D"   # YouTube "Videos only" filter


# ── Config helpers ─────────────────────────────────────────────────────────────

def _load_config() -> dict:
    try:
        return json.loads(API_CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _get_browser_exe() -> str:
    cfg     = _load_config()
    browser = cfg.get("default_browser", "msedge").strip().lower()
    exe_map = {"msedge": "msedge", "edge": "msedge", "chrome": "chrome",
               "firefox": "firefox", "brave": "brave"}
    exe     = exe_map.get(browser, "msedge")
    if shutil.which(exe):
        return exe
    candidates = {
        "msedge": [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                   r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"],
        "chrome": [r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                   r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"],
        "firefox":[r"C:\Program Files\Mozilla Firefox\firefox.exe"],
    }
    for path in candidates.get(exe, []):
        if Path(path).exists():
            return path
    return ""


def _open_url(url: str) -> None:
    """Open a URL in the user's default browser."""
    exe = _get_browser_exe()
    try:
        if exe:
            subprocess.Popen([exe, url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.Popen(["cmd", "/c", "start", "", url],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, shell=False)
        time.sleep(0.5)
    except Exception as e:
        print(f"[VideoSearch] open_url failed: {e}")
        try:
            import webbrowser
            webbrowser.open(url)
        except Exception:
            pass


# ── YouTube ───────────────────────────────────────────────────────────────────

def _yt_scrape_first_video(query: str) -> str | None:
    """Scrape the first non-Shorts video URL from YouTube search results."""
    if not _REQUESTS_OK:
        return None
    url = (f"https://www.youtube.com/results"
           f"?search_query={quote_plus(query)}&sp={_YT_VIDEO_FILTER}")
    try:
        r    = requests.get(url, headers=_HEADERS, timeout=10)
        html = r.text
        ids  = re.findall(r'"videoId":"([A-Za-z0-9_-]{11})"', html)
        seen = set()
        for vid in ids:
            if vid in seen:
                continue
            seen.add(vid)
            if f"/shorts/{vid}" in html:
                continue
            return f"https://www.youtube.com/watch?v={vid}"
    except Exception as e:
        print(f"[VideoSearch] YT scrape failed: {e}")
    return None


def _yt_extract_video_id(url: str) -> str | None:
    m = re.search(r"(?:v=|\/v\/|youtu\.be\/|\/embed\/|\/shorts\/)([A-Za-z0-9_-]{11})", url)
    return m.group(1) if m else None


def _yt_get_transcript(video_id: str) -> str | None:
    if not _TRANSCRIPT_OK:
        return None
    try:
        tl     = YouTubeTranscriptApi.list_transcripts(video_id)
        langs  = ["en", "en-US", "en-GB", "fr", "de", "es", "pt", "it", "ja", "ko", "ar", "ru"]
        tr     = None
        try:
            tr = tl.find_manually_created_transcript(langs)
        except Exception:
            pass
        if tr is None:
            try:
                tr = tl.find_generated_transcript(langs)
            except Exception:
                for t in tl:
                    tr = t; break
        if tr is None:
            return None
        return " ".join(e["text"] for e in tr.fetch())
    except Exception as e:
        print(f"[VideoSearch] Transcript fetch failed: {e}")
        return None


def _yt_summarize(transcript: str, url: str, speak=None) -> str:
    """Summarize a YouTube transcript via NVIDIA/Groq."""
    try:
        from openai import OpenAI
        cfg       = _load_config()
        groq_key  = cfg.get("groq_api_key",  "").strip()
        nim_key   = cfg.get("nvidia_api_key", "").strip()

        if groq_key and groq_key not in ("", "YOUR_GROQ_KEY_HERE"):
            client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=groq_key)
            model  = cfg.get("groq_model", "llama-3.3-70b-versatile")
        elif nim_key:
            client = OpenAI(base_url="https://integrate.api.nvidia.com/v1", api_key=nim_key)
            model  = cfg.get("nvidia_model", "meta/llama-3.3-70b-instruct")
        else:
            return "No AI key configured for summarization."

        trunc = transcript[:12000]
        resp  = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": (
                    "You are JARVIS. Summarize the YouTube transcript clearly and concisely. "
                    "Give a 1-sentence overview then 3-5 bullet-point key takeaways. "
                    "Address the user as 'boss'."
                )},
                {"role": "user", "content": f"Transcript:\n{trunc}"},
            ],
            max_tokens=500,
            temperature=0.3,
        )
        return (resp.choices[0].message.content or "Could not summarize.").strip()
    except Exception as e:
        return f"Summarization failed: {e}"


def _yt_trending(region: str = "US", max_results: int = 8) -> list[dict]:
    if not _REQUESTS_OK:
        return []
    url = f"https://www.youtube.com/feed/trending?gl={region.upper()}"
    try:
        r       = requests.get(url, headers=_HEADERS, timeout=12)
        html    = r.text
        titles  = re.findall(r'"title":\{"runs":\[\{"text":"([^"]+)"\}\]', html)
        chans   = re.findall(r'"ownerText":\{"runs":\[\{"text":"([^"]+)"', html)
        results, seen = [], set()
        for i, title in enumerate(titles):
            if title in seen or len(title) < 5:
                continue
            seen.add(title)
            results.append({
                "rank":    len(results) + 1,
                "title":   title,
                "channel": chans[i] if i < len(chans) else "Unknown",
                "platform": "YouTube",
            })
            if len(results) >= max_results:
                break
        return results
    except Exception as e:
        print(f"[VideoSearch] YT trending failed: {e}")
        return []


# ── Platform-specific search URL builders ────────────────────────────────────

def _platform_search_url(platform: str, query: str) -> str:
    q = quote_plus(query)
    urls = {
        "youtube":   f"https://www.youtube.com/results?search_query={q}&sp={_YT_VIDEO_FILTER}",
        "tiktok":    f"https://www.tiktok.com/search?q={q}",
        "instagram": f"https://www.instagram.com/explore/search/keyword/?q={q}",
        "twitter":   f"https://twitter.com/search?q={q}&f=video",
        "x":         f"https://twitter.com/search?q={q}&f=video",
        "reddit":    f"https://www.reddit.com/search/?q={q}&type=link",
        "facebook":  f"https://www.facebook.com/search/videos/?q={q}",
        "twitch":    f"https://www.twitch.tv/search?term={q}",
        "vimeo":     f"https://vimeo.com/search?q={q}",
        "dailymotion": f"https://www.dailymotion.com/search/{q}",
        "rumble":    f"https://rumble.com/search/video?q={q}",
    }
    return urls.get(platform.lower(), urls["youtube"])


# ── Handlers ──────────────────────────────────────────────────────────────────

def _handle_play(params: dict, player) -> str:
    query    = params.get("query", "").strip()
    platform = params.get("platform", "youtube").lower().strip()

    if not query:
        return "Please tell me what you'd like to watch, boss."

    if player:
        player.write_log(f"[VideoSearch] {platform}: {query}")

    if platform == "youtube":
        # Try to scrape direct video URL first
        video_url = _yt_scrape_first_video(query)
        if video_url:
            print(f"[VideoSearch] Playing: {video_url}")
            _open_url(video_url)
            return f"Playing '{query}' on YouTube, boss."
        # Fallback: open YouTube search page
        fallback = _platform_search_url("youtube", query)
        _open_url(fallback)
        return f"Opened YouTube search for '{query}', boss."

    # Other platforms — open their search page
    url = _platform_search_url(platform, query)
    _open_url(url)
    platform_names = {
        "tiktok": "TikTok", "instagram": "Instagram", "twitter": "Twitter/X",
        "x": "Twitter/X", "reddit": "Reddit", "facebook": "Facebook",
        "twitch": "Twitch", "vimeo": "Vimeo", "dailymotion": "Dailymotion",
        "rumble": "Rumble",
    }
    name = platform_names.get(platform, platform.capitalize())
    return f"Opened {name} search for '{query}', boss."


def _handle_search_all(params: dict, player) -> str:
    """Search across multiple platforms and return URL list."""
    query     = params.get("query", "").strip()
    platforms = params.get("platforms", ["youtube", "tiktok", "instagram", "twitter", "reddit"])
    if not query:
        return "Please provide a search query, boss."

    if isinstance(platforms, str):
        platforms = [p.strip() for p in platforms.split(",")]

    lines = [f"Video search results for '{query}':\n"]
    for p in platforms:
        url  = _platform_search_url(p, query)
        name = p.capitalize()
        lines.append(f"• {name}: {url}")

    # Open the first platform (YouTube by default)
    first_url = _platform_search_url(platforms[0] if platforms else "youtube", query)
    _open_url(first_url)
    lines.append(f"\nOpened {platforms[0].capitalize()} in your browser, boss.")
    return "\n".join(lines)


def _handle_summarize(params: dict, player, speak) -> str:
    if not _TRANSCRIPT_OK:
        return "youtube-transcript-api is not installed. Run: pip install youtube-transcript-api"

    url = params.get("url", "").strip()
    if not url:
        return "Please provide a YouTube video URL to summarize, boss."
    if "youtube.com" not in url and "youtu.be" not in url:
        return "Summarization currently supports YouTube links only, boss."

    video_id = _yt_extract_video_id(url)
    if not video_id:
        return "Could not extract video ID from that URL, boss."

    if player:
        player.write_log(f"[VideoSearch] Summarizing: {url}")
    if speak:
        speak("Fetching transcript now, boss. One moment.")

    transcript = _yt_get_transcript(video_id)
    if not transcript:
        return "I couldn't retrieve a transcript for that video, boss."

    if speak:
        speak("Transcript retrieved. Generating summary now, boss.")

    summary = _yt_summarize(transcript, url, speak=speak)

    if params.get("save", False):
        from datetime import datetime
        ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = Path.home() / "Desktop" / f"video_summary_{ts}.txt"
        path.write_text(
            f"JARVIS Video Summary\n{'─'*50}\nURL: {url}\n\n{summary}",
            encoding="utf-8"
        )
        try:
            subprocess.Popen(["notepad.exe", str(path)])
        except Exception:
            pass
        return f"Summary saved to Desktop: {path.name}\n\n{summary}"

    return summary


def _handle_trending(params: dict, player, speak) -> str:
    region   = params.get("region", "US").upper()
    platform = params.get("platform", "youtube").lower()

    if platform != "youtube":
        # Other platforms don't have easy programmatic trending — open their trending page
        trending_urls = {
            "tiktok":    "https://www.tiktok.com/trending",
            "instagram": "https://www.instagram.com/explore/",
            "twitter":   "https://twitter.com/explore/tabs/trending",
            "reddit":    "https://www.reddit.com/r/videos/top/?t=day",
            "youtube":   f"https://www.youtube.com/feed/trending?gl={region}",
        }
        url = trending_urls.get(platform, trending_urls["youtube"])
        _open_url(url)
        return f"Opened {platform.capitalize()} trending in your browser, boss."

    if player:
        player.write_log(f"[VideoSearch] Trending: {region}")

    trending = _yt_trending(region=region, max_results=8)
    if not trending:
        url = f"https://www.youtube.com/feed/trending?gl={region}"
        _open_url(url)
        return f"Could not scrape trending list, opened YouTube trending for {region}, boss."

    lines  = [f"Top trending on YouTube ({region}):"]
    lines += [f"{v['rank']}. {v['title']} — {v['channel']}" for v in trending]
    result = "\n".join(lines)

    if speak:
        top3   = trending[:3]
        spoken = "Top trending videos: " + ". ".join(
            f"Number {v['rank']}: {v['title']} by {v['channel']}" for v in top3
        )
        speak(spoken)

    return result


def _handle_open_channel(params: dict, player) -> str:
    """Open a specific channel or profile on any platform."""
    channel  = params.get("channel", "").strip()
    platform = params.get("platform", "youtube").lower()

    if not channel:
        return "Please provide a channel name, boss."

    urls = {
        "youtube":   f"https://www.youtube.com/@{quote_plus(channel)}",
        "tiktok":    f"https://www.tiktok.com/@{quote_plus(channel)}",
        "instagram": f"https://www.instagram.com/{quote_plus(channel)}/",
        "twitter":   f"https://twitter.com/{quote_plus(channel)}",
        "twitch":    f"https://www.twitch.tv/{quote_plus(channel)}",
    }
    url = urls.get(platform, urls["youtube"])
    _open_url(url)
    return f"Opened {platform.capitalize()} channel: {channel}, boss."


# ── Public entry point ────────────────────────────────────────────────────────

def video_search(
    parameters:     dict,
    response=None,
    player=None,
    session_memory=None,
    speak=None,
) -> str:
    """
    Multi-platform video search and playback.

    parameters:
        action   : play | search_all | summarize | trending | open_channel
        query    : search term
        platform : youtube | tiktok | instagram | twitter | reddit |
                   facebook | twitch | vimeo | dailymotion | rumble
                   (default: youtube for play/trending; opens browser for others)
        platforms: list of platforms for search_all
        url      : YouTube URL for summarize
        region   : region code for trending (e.g. US, NG, GB)
        channel  : channel/username for open_channel
        save     : bool — save summary to Desktop
    """
    params = parameters or {}
    action = params.get("action", "play").lower().strip()

    if player:
        player.write_log(f"[VideoSearch] Action: {action}")
    print(f"[VideoSearch] Action: {action}  Params: {params}")

    try:
        if action == "play":
            return _handle_play(params, player) or "Done."

        elif action == "search_all":
            return _handle_search_all(params, player) or "Done."

        elif action == "summarize":
            return _handle_summarize(params, player, speak) or "Done."

        elif action == "trending":
            return _handle_trending(params, player, speak) or "Done."

        elif action in ("open_channel", "channel"):
            return _handle_open_channel(params, player) or "Done."

        else:
            # Treat unknown action as a play query
            if action:
                params["query"] = params.get("query", "") or action
                return _handle_play(params, player) or "Done."
            return (
                "Unknown action. Available: play, search_all, summarize, trending, open_channel."
            )

    except Exception as e:
        print(f"[VideoSearch] Error in {action}: {e}")
        return f"Video search failed, boss: {e}"
