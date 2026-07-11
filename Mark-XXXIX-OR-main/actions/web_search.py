"""
web_search.py — Live web search for JARVIS.

Primary  : DuckDuckGo text/news (ddgs package)
News     : Multi-source RSS (BBC, Guardian, NPR, CNN, Al Jazeera, Reuters)
Fallback : LLM knowledge (clearly flagged as training data, not live)
Extras   : compare mode, image search (opens browser), site-specific search
"""

import json
import sys
from pathlib import Path
from urllib.parse import quote_plus


def _get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BASE_DIR        = _get_base_dir()
API_CONFIG_PATH = BASE_DIR / "config" / "api_keys.json"

_HDR = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

# ── RSS news feeds ─────────────────────────────────────────────────────────────

_NEWS_FEEDS = [
    ("BBC World",   "https://feeds.bbci.co.uk/news/world/rss.xml"),
    ("Guardian",    "https://www.theguardian.com/world/rss"),
    ("NPR",         "https://feeds.npr.org/1001/rss.xml"),
    ("CNN",         "http://rss.cnn.com/rss/edition_world.rss"),
    ("Al Jazeera",  "https://www.aljazeera.com/xml/rss/all.xml"),
    ("Reuters",     "https://feeds.reuters.com/reuters/topNews"),
    ("TechCrunch",  "https://techcrunch.com/feed/"),
    ("Hacker News", "https://hnrss.org/frontpage"),
]


def _rss_news(query: str = "", max_items: int = 6) -> list[dict]:
    """Fetch headlines from RSS feeds in parallel. Fast, reliable, no API key."""
    import requests
    import xml.etree.ElementTree as ET
    import concurrent.futures

    query_lower = query.lower()

    # Pick topic-specific feeds when query matches a category
    feeds = _NEWS_FEEDS
    if any(k in query_lower for k in ("tech", "technology", "software", "ai", "startup")):
        feeds = [f for f in _NEWS_FEEDS if f[0] in ("TechCrunch", "Hacker News")] + feeds[:4]
    elif any(k in query_lower for k in ("sport", "football", "soccer", "nba", "nfl")):
        feeds = [("ESPN", "https://www.espn.com/espn/rss/news")] + feeds[:3]

    def _fetch(source_url: tuple) -> list[dict]:
        source, url = source_url
        try:
            resp  = requests.get(url, timeout=5, headers=_HDR)
            resp.raise_for_status()
            root  = ET.fromstring(resp.content)
            items = root.findall("./channel/item") or root.findall(".//item")
            results = []
            for item in items[:max_items]:
                title_el = item.find("title")
                desc_el  = item.find("description")
                link_el  = item.find("link")
                title    = (title_el.text or "").strip() if title_el is not None else ""
                desc     = (desc_el.text  or "").strip() if desc_el  is not None else ""
                link     = (link_el.text  or "").strip() if link_el  is not None else ""
                # Strip HTML tags from description
                import re
                desc = re.sub(r"<[^>]+>", "", desc)[:200]
                if title and len(title) > 10:
                    results.append({
                        "title":   title,
                        "snippet": desc,
                        "url":     link,
                        "source":  source,
                    })
            return results
        except Exception as e:
            print(f"[WebSearch] RSS {source} failed: {e}")
            return []

    all_results: list[dict] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
        futs = [ex.submit(_fetch, f) for f in feeds]
        for fut in concurrent.futures.as_completed(futs, timeout=8):
            try:
                all_results.extend(fut.result())
            except Exception:
                pass
            if len(all_results) >= max_items * 2:
                break

    # Deduplicate by title
    seen, unique = set(), []
    for r in all_results:
        if r["title"] not in seen:
            seen.add(r["title"])
            unique.append(r)

    return unique[:max_items]


def _format_rss(results: list[dict], query: str) -> str:
    if not results:
        return f"No news results found for: {query}"
    lines = [f"Live news — {query}\n"]
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. {r['title']}  [{r['source']}]")
        if r.get("snippet"):
            lines.append(f"   {r['snippet'][:160]}")
        if r.get("url"):
            lines.append(f"   {r['url']}")
        lines.append("")
    return "\n".join(lines).strip()


# ── DuckDuckGo search ──────────────────────────────────────────────────────────

def _ddg_search(query: str, max_results: int = 6) -> list[dict]:
    """DuckDuckGo text search with hard timeout."""
    import concurrent.futures

    def _do():
        try:
            from ddgs import DDGS
        except ImportError:
            try:
                from duckduckgo_search import DDGS
            except ImportError:
                return []
        results = []
        try:
            with DDGS() as ddgs:
                for r in ddgs.text(query, max_results=max_results):
                    results.append({
                        "title":   r.get("title",  ""),
                        "snippet": r.get("body",   ""),
                        "url":     r.get("href",   ""),
                        "source":  "DuckDuckGo",
                    })
        except Exception as e:
            print(f"[WebSearch] DDG text error: {e}")
        return results

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(_do)
        try:
            return fut.result(timeout=9)
        except concurrent.futures.TimeoutError:
            print("[WebSearch] DDG timed out")
            return []
        except Exception as e:
            print(f"[WebSearch] DDG outer error: {e}")
            return []


def _ddg_news(query: str, max_results: int = 5) -> list[dict]:
    """DuckDuckGo news search — more current than text search for news queries."""
    import concurrent.futures

    def _do():
        try:
            from ddgs import DDGS
        except ImportError:
            try:
                from duckduckgo_search import DDGS
            except ImportError:
                return []
        results = []
        try:
            with DDGS() as ddgs:
                for r in ddgs.news(query, max_results=max_results):
                    results.append({
                        "title":   r.get("title",  ""),
                        "snippet": r.get("body",   "") or r.get("excerpt", ""),
                        "url":     r.get("url",    ""),
                        "source":  r.get("source", "DDG News"),
                    })
        except Exception as e:
            print(f"[WebSearch] DDG news error: {e}")
        return results

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(_do)
        try:
            return fut.result(timeout=9)
        except Exception:
            return []


def _format_ddg(query: str, results: list[dict]) -> str:
    if not results:
        return f"No results found for: {query}"
    lines = [f"Web results — {query}\n"]
    for i, r in enumerate(results, 1):
        if r.get("title"):   lines.append(f"{i}. {r['title']}")
        if r.get("snippet"): lines.append(f"   {r['snippet'][:160]}")
        if r.get("url"):     lines.append(f"   {r['url']}")
        lines.append("")
    return "\n".join(lines).strip()


# ── Image search (opens browser) ──────────────────────────────────────────────

def _image_search(query: str, engine: str = "google") -> str:
    """Open an image search in the default browser."""
    q = quote_plus(query)
    urls = {
        "google": f"https://www.google.com/search?q={q}&tbm=isch",
        "bing":   f"https://www.bing.com/images/search?q={q}",
        "pinterest": f"https://www.pinterest.com/search/pins/?q={q}",
    }
    url = urls.get(engine.lower(), urls["google"])
    try:
        import subprocess, json as _j
        from pathlib import Path as _P
        cfg  = _j.loads((_P(__file__).resolve().parent.parent / "config" / "api_keys.json")
                         .read_text(encoding="utf-8"))
        exe_map = {"msedge": "msedge", "edge": "msedge", "chrome": "chrome",
                   "firefox": "firefox", "brave": "brave"}
        exe  = exe_map.get(cfg.get("default_browser", "msedge").lower(), "msedge")
        subprocess.Popen([exe, url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return f"Opened {engine} image search for: {query}"
    except Exception as e:
        try:
            import webbrowser
            webbrowser.open(url)
            return f"Opened image search for: {query}"
        except Exception:
            return f"Image search URL: {url}"


# ── Compare mode ───────────────────────────────────────────────────────────────

def _compare(items: list[str], aspect: str) -> str:
    all_results: dict[str, list] = {}
    for item in items:
        all_results[item] = _ddg_search(f"{item} {aspect}", max_results=3)

    lines = [f"Comparison — {aspect.upper()}", "─" * 40]
    for item in items:
        lines.append(f"\n▸ {item}")
        for r in all_results.get(item, [])[:2]:
            if r.get("snippet"):
                lines.append(f"  • {r['snippet'][:130]}")
    return "\n".join(lines)


# ── Keyword classifiers ────────────────────────────────────────────────────────

_NEWS_KW = {
    "news", "today", "latest", "current", "breaking", "happening",
    "headline", "2024", "2025", "2026", "update", "recent", "now",
    "world", "event", "crisis", "war", "election", "summit", "announcement",
}
_IMAGE_KW = {
    "image", "photo", "picture", "wallpaper", "meme", "logo", "screenshot",
    "show me", "what does", "look like",
}


# ── Public interface ───────────────────────────────────────────────────────────

def web_search(
    parameters:     dict,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    """
    parameters:
        query   : search query string (required unless items set)
        mode    : "search" | "news" | "compare" | "image" (default: auto-detect)
        items   : list of items to compare
        aspect  : comparison aspect (default: "general")
        engine  : image search engine for mode=image (google/bing/pinterest)
        site    : restrict search to this site (e.g. "reddit.com")
    """
    params = parameters or {}
    query  = params.get("query", "").strip()
    mode   = params.get("mode",  "").lower().strip()
    items  = params.get("items", [])
    aspect = params.get("aspect", "general").strip() or "general"
    engine = params.get("engine", "google").strip()
    site   = params.get("site", "").strip()

    if not query and not items:
        return "Please provide a search query, boss."

    if items and mode not in ("compare",):
        mode = "compare"

    # Add site restriction
    if site and "site:" not in query:
        query = f"{query} site:{site}"

    if player:
        player.write_log(f"[Search] {query or ', '.join(items)}")

    print(f"[WebSearch] Query: {query!r}  Mode: {mode or 'auto'}")

    # ── Compare mode ──────────────────────────────────────────────────────
    if mode == "compare" and items:
        return _compare(items, aspect)

    # ── Image mode ────────────────────────────────────────────────────────
    is_image = mode == "image" or any(kw in query.lower() for kw in _IMAGE_KW)
    if is_image and mode != "news" and mode != "search":
        return _image_search(query, engine=engine)

    # ── News mode ─────────────────────────────────────────────────────────
    is_news = (mode == "news" or any(kw in query.lower() for kw in _NEWS_KW))

    if is_news:
        # Try DDG news first (most current)
        ddg_news = _ddg_news(query, max_results=5)
        if ddg_news:
            result = _format_ddg(query, ddg_news)
            print(f"[WebSearch] DDG news: {len(ddg_news)} results")
            return result

        # RSS fallback
        rss = _rss_news(query=query, max_items=5)
        if rss:
            result = _format_rss(rss, query)
            print(f"[WebSearch] RSS: {len(rss)} results")
            return result

    # ── General DDG text search ───────────────────────────────────────────
    ddg = _ddg_search(query, max_results=6)
    if ddg:
        result = _format_ddg(query, ddg)
        print(f"[WebSearch] DDG: {len(ddg)} results")
        return result

    # ── LLM fallback ─────────────────────────────────────────────────────
    print("[WebSearch] All live sources failed — using LLM knowledge fallback")
    try:
        from openai import OpenAI
        cfg       = json.loads(API_CONFIG_PATH.read_text(encoding="utf-8"))
        groq_key  = cfg.get("groq_api_key",  "").strip()
        nim_key   = cfg.get("nvidia_api_key", "").strip()

        if groq_key and groq_key not in ("", "YOUR_GROQ_KEY_HERE"):
            client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=groq_key)
            model  = cfg.get("groq_model", "llama-3.3-70b-versatile")
        elif nim_key:
            client = OpenAI(base_url="https://integrate.api.nvidia.com/v1", api_key=nim_key)
            model  = cfg.get("nvidia_model", "meta/llama-3.3-70b-instruct")
        else:
            return f"Web search unavailable and no AI key configured, boss."

        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": (
                    "Answer the query using your training knowledge. "
                    "Always state clearly this is from training data, not a live web search."
                )},
                {"role": "user", "content": query},
            ],
            max_tokens=400,
            temperature=0.1,
        )
        answer = (resp.choices[0].message.content or "").strip()
        return f"[Training knowledge — not live]\n{answer}"

    except Exception as e:
        return f"Web search unavailable, boss: {e}"
