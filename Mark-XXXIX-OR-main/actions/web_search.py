# web_search.py
# Primary: DuckDuckGo text search (with short timeout)
# News queries: RSS feeds from BBC / Al Jazeera / NPR (no DDG dependency)
# Fallback: LLM knowledge (clearly flagged as not real-time)

import json
import sys
from pathlib import Path


def _get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BASE_DIR        = _get_base_dir()
API_CONFIG_PATH = BASE_DIR / "config" / "api_keys.json"

_HDR = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# ── RSS news feeds (fast, reliable, no DDG) ───────────────────────────────────

_NEWS_FEEDS = [
    ("BBC World",    "https://feeds.bbci.co.uk/news/world/rss.xml"),
    ("Guardian",     "https://www.theguardian.com/world/rss"),
    ("NPR",          "https://feeds.npr.org/1001/rss.xml"),
    ("CNN",          "http://rss.cnn.com/rss/edition_world.rss"),
    ("Al Jazeera",   "https://www.aljazeera.com/xml/rss/all.xml"),
]


def _rss_news(max_items: int = 5) -> list[dict]:
    """Fetch top headlines from RSS feeds in parallel. Fast and reliable."""
    import requests
    import xml.etree.ElementTree as ET
    import concurrent.futures

    def _fetch(source_url):
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
                if title and len(title) > 10:
                    results.append({"title": title, "snippet": desc[:200], "url": link, "source": source})
            return results
        except Exception as e:
            print(f"[WebSearch] RSS {source} failed: {e}")
            return []

    all_results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
        futs = [ex.submit(_fetch, f) for f in _NEWS_FEEDS]
        for fut in concurrent.futures.as_completed(futs, timeout=8):
            try:
                all_results.extend(fut.result())
            except Exception:
                pass

    return all_results[:max_items] if all_results else []


def _format_rss(results: list[dict], query: str) -> str:
    if not results:
        return f"No news results found for: {query}"
    lines = [f"Live news results for: {query}\n"]
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. {r['title']}  [{r['source']}]")
        if r.get("snippet"):
            lines.append(f"   {r['snippet'][:150]}")
        if r.get("url"):
            lines.append(f"   {r['url']}")
        lines.append("")
    return "\n".join(lines).strip()


# ── DuckDuckGo text search ─────────────────────────────────────────────────────

def _ddg_search(query: str, max_results: int = 6) -> list[dict]:
    """DDG text search with a hard timeout to prevent hanging."""
    import concurrent.futures

    def _do_search():
        # Try new package name first, fall back to old
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append({
                    "title":   r.get("title",  ""),
                    "snippet": r.get("body",   ""),
                    "url":     r.get("href",   ""),
                })
        return results

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        future = ex.submit(_do_search)
        try:
            return future.result(timeout=8)
        except concurrent.futures.TimeoutError:
            print("[WebSearch] DDG timed out after 8s")
            return []
        except Exception as e:
            print(f"[WebSearch] DDG error: {e}")
            return []


def _format_ddg(query: str, results: list[dict]) -> str:
    if not results:
        return f"No results found for: {query}"
    lines = [f"Web results for: {query}\n"]
    for i, r in enumerate(results, 1):
        if r.get("title"):   lines.append(f"{i}. {r['title']}")
        if r.get("snippet"): lines.append(f"   {r['snippet'][:150]}")
        if r.get("url"):     lines.append(f"   {r['url']}")
        lines.append("")
    return "\n".join(lines).strip()


# ── Compare mode ──────────────────────────────────────────────────────────────

def _compare(items: list[str], aspect: str) -> str:
    all_results: dict[str, list] = {}
    for item in items:
        all_results[item] = _ddg_search(f"{item} {aspect}", max_results=3)

    lines = [f"Comparison — {aspect.upper()}", "─" * 40]
    for item in items:
        lines.append(f"\n▸ {item}")
        for r in all_results.get(item, [])[:2]:
            if r.get("snippet"):
                lines.append(f"  • {r['snippet'][:120]}")
    return "\n".join(lines)


# ── Public interface ───────────────────────────────────────────────────────────

_NEWS_KW = {
    "news", "today", "latest", "current", "breaking", "happening",
    "headline", "2024", "2025", "2026", "update", "recent", "now",
    "world", "event", "crisis", "war", "election", "summit",
}


def web_search(
    parameters:     dict,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    params = parameters or {}
    query  = params.get("query", "").strip()
    mode   = params.get("mode",  "search").lower().strip()
    items  = params.get("items", [])
    aspect = params.get("aspect", "general").strip() or "general"

    if not query and not items:
        return "Please provide a search query, boss."

    if items and mode != "compare":
        mode = "compare"

    if player:
        player.write_log(f"[Search] {query or ', '.join(items)}")

    print(f"[WebSearch] Query: {query!r}  Mode: {mode}")

    # Compare mode
    if mode == "compare" and items:
        return _compare(items, aspect)

    # News / current events → RSS first (fast, reliable)
    is_news = any(kw in query.lower() for kw in _NEWS_KW)
    if is_news:
        rss = _rss_news(max_items=5)
        if rss:
            result = _format_rss(rss, query)
            print(f"[WebSearch] RSS: {len(rss)} results")
            return result

    # General search → DDG text
    ddg = _ddg_search(query, max_results=6)
    if ddg:
        result = _format_ddg(query, ddg)
        print(f"[WebSearch] DDG: {len(ddg)} results")
        return result

    # Last resort: LLM knowledge
    try:
        from claude_client import generate as _gen
        result = _gen(
            f"Answer this query (not real-time, from training knowledge): {query}",
            system="Answer factually. State clearly you are using training knowledge, not live data.",
        )
        print("[WebSearch] LLM fallback (no live data)")
        return result
    except Exception as e:
        return f"Web search unavailable, boss: {e}"
