"""
transport_finder.py — All-modes transport search for JARVIS.

For every transport request, JARVIS builds a clean HTML results page showing
multiple booking options with direct links, then opens it in the user's browser.

Modes: flight | train | bus | taxi | ride | car_rental | ferry | any
"""

import json
import re
import subprocess
import sys
import shutil
import time
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote_plus


def _get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BASE_DIR        = _get_base_dir()
API_CONFIG_PATH = BASE_DIR / "config" / "api_keys.json"


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
        "chrome": [r"C:\Program Files\Google\Chrome\Application\chrome.exe"],
        "firefox": [r"C:\Program Files\Mozilla Firefox\firefox.exe"],
    }
    for path in candidates.get(exe, []):
        if Path(path).exists():
            return path
    return ""


def _open_url(url: str) -> None:
    """Open a URL in the user's default browser."""
    import os as _os
    print(f"[Transport] Opening: {url[:100]}")

    # Local HTML files — use os.startfile (works from any thread)
    if url.startswith("file:///") or url.startswith("file://"):
        try:
            local = url.replace("file:///", "").replace("file://", "").replace("/", "\\")
            _os.startfile(local)
            time.sleep(0.8)
            return
        except Exception:
            pass
        try:
            import webbrowser
            webbrowser.open(url)
            time.sleep(0.8)
            return
        except Exception:
            pass
        return

    # Web URLs
    exe = _get_browser_exe()
    try:
        if exe:
            subprocess.Popen([exe, url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.Popen(["cmd", "/c", "start", "", url],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, shell=False)
        time.sleep(0.6)
    except Exception:
        try:
            import webbrowser
            webbrowser.open(url)
        except Exception as e:
            print(f"[Transport] Could not open browser: {e}")


# ── Date parsing ──────────────────────────────────────────────────────────────

_MONTH_MAP = {
    "january":1,"february":2,"march":3,"april":4,"may":5,"june":6,
    "july":7,"august":8,"september":9,"october":10,"november":11,"december":12,
    "jan":1,"feb":2,"mar":3,"apr":4,"jun":6,"jul":7,"aug":8,
    "sep":9,"oct":10,"nov":11,"dec":12,
}

def _parse_date(raw: str) -> str:
    if not raw:
        return datetime.now().strftime("%Y-%m-%d")
    raw = raw.strip(); lower = raw.lower(); today = datetime.now()
    if re.match(r"\d{4}-\d{2}-\d{2}$", raw):
        return raw
    for fmt in ("%d/%m/%Y","%m/%d/%Y","%d.%m.%Y","%d-%m-%Y",
                "%d/%m/%y","%m/%d/%y","%B %d %Y","%b %d %Y","%d %B %Y","%d %b %Y"):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    if "today" in lower:     return today.strftime("%Y-%m-%d")
    if "tomorrow" in lower:  return (today+timedelta(days=1)).strftime("%Y-%m-%d")
    if "day after" in lower: return (today+timedelta(days=2)).strftime("%Y-%m-%d")
    m = re.search(r"in\s+(\d+)\s+days?", lower)
    if m: return (today+timedelta(days=int(m.group(1)))).strftime("%Y-%m-%d")
    day_m = re.search(r"(\d{1,2})(?:st|nd|rd|th)?", raw)
    for mn, mv in _MONTH_MAP.items():
        if mn in lower and day_m:
            day  = int(day_m.group(1))
            year = today.year if mv > today.month or (mv == today.month and day >= today.day) else today.year+1
            return f"{year}-{mv:02d}-{day:02d}"
    try:
        from openai import OpenAI
        cfg = _load_config()
        gk  = cfg.get("groq_api_key","").strip()
        nk  = cfg.get("nvidia_api_key","").strip()
        if gk and gk not in ("","YOUR_GROQ_KEY_HERE"):
            cl = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=gk)
            md = cfg.get("groq_model","llama-3.3-70b-versatile")
        elif nk:
            cl = OpenAI(base_url="https://integrate.api.nvidia.com/v1", api_key=nk)
            md = cfg.get("nvidia_model","meta/llama-3.3-70b-instruct")
        else:
            return today.strftime("%Y-%m-%d")
        r = cl.chat.completions.create(
            model=md,
            messages=[{"role":"system","content":"Convert to YYYY-MM-DD. Return ONLY the date."},
                      {"role":"user","content":f"Today={today.strftime('%Y-%m-%d')}. Convert: '{raw}'"}],
            max_tokens=20, temperature=0)
        res = (r.choices[0].message.content or "").strip()
        if re.match(r"\d{4}-\d{2}-\d{2}$", res): return res
    except Exception:
        pass
    return today.strftime("%Y-%m-%d")


# ── Transport option definitions ──────────────────────────────────────────────
# Each entry: (site_name, emoji, description, url_builder_lambda)

def _get_options(mode: str, origin: str, destination: str,
                 date: str, return_date: str | None,
                 passengers: int, cabin: str) -> list[dict]:
    """Return a list of transport option dicts for the HTML results page."""
    q_orig = quote_plus(origin)
    q_dest = quote_plus(destination)
    q_date = quote_plus(date)
    q_ret  = quote_plus(return_date) if return_date else ""
    cc     = {"economy":"1","premium":"2","business":"3","first":"4"}.get(cabin,"1")
    pax    = str(passengers)

    if mode in ("flight","flights","fly","plane","air"):
        return [
            {"name":"Google Flights",   "emoji":"✈️",  "desc":"Compare all airlines — best prices",
             "url":f"https://www.google.com/travel/flights?q={quote_plus(f'Flights from {origin} to {destination} on {date}')}&curr=USD&cabin={cc}&adults={pax}"},
            {"name":"Skyscanner",       "emoji":"🔍",  "desc":"Search hundreds of airlines at once",
             "url":f"https://www.skyscanner.net/transport/flights/{q_orig}/{q_dest}/{date.replace('-','')}/{q_ret.replace('-','') if q_ret else ''}/?adults={pax}&cabinclass={cabin}"},
            {"name":"Kayak Flights",    "emoji":"🛫",  "desc":"Find deals and set price alerts",
             "url":f"https://www.kayak.com/flights/{origin.replace(' ','-')}/{destination.replace(' ','-')}/{date}?adults={pax}&cabin={cabin}"},
            {"name":"Booking.com Flights","emoji":"🏷️","desc":"Flexible booking options",
             "url":f"https://flights.booking.com/flights/{q_orig}-{q_dest}/?adults={pax}&cabin_class={cabin}&depart_date={date}"},
            {"name":"Momondo",          "emoji":"💰",  "desc":"Budget flight comparison",
             "url":f"https://www.momondo.com/flight-search/{origin.replace(' ','-')}/{destination.replace(' ','-')}/{date}?adults={pax}"},
        ]

    elif mode in ("train","rail","railway"):
        return [
            {"name":"Rome2rio (Train)",  "emoji":"🚆", "desc":"All train routes worldwide",
             "url":f"https://www.rome2rio.com/s/{q_orig}/{q_dest}"},
            {"name":"Google Maps Transit","emoji":"🗺️","desc":"Step-by-step transit directions",
             "url":f"https://www.google.com/maps/dir/{q_orig}/{q_dest}/?travelmode=transit"},
            {"name":"Trainline",         "emoji":"🎫", "desc":"Book train tickets across Europe",
             "url":f"https://www.thetrainline.com/book/results?origin={q_orig}&destination={q_dest}&outwardDate={date}&passengers={pax}"},
            {"name":"Omio (Rail)",       "emoji":"🚂", "desc":"Trains across Europe & beyond",
             "url":f"https://www.omio.com/trains/{q_orig}/{q_dest}/{date}?adults={pax}"},
            {"name":"Rail Europe",       "emoji":"🇪🇺", "desc":"European train passes & tickets",
             "url":f"https://www.raileurope.com/en/train-search?origin={q_orig}&destination={q_dest}&date={date}"},
        ]

    elif mode in ("bus","coach"):
        return [
            {"name":"Rome2rio (Bus)",    "emoji":"🚌", "desc":"Bus routes worldwide",
             "url":f"https://www.rome2rio.com/s/{q_orig}/{q_dest}"},
            {"name":"FlixBus",           "emoji":"🟢", "desc":"Affordable intercity buses",
             "url":f"https://shop.flixbus.com/search?rideDate={date}&adult={pax}&_locale=en&from={q_orig}&to={q_dest}"},
            {"name":"Omio (Bus)",        "emoji":"🚍", "desc":"Buses across Europe",
             "url":f"https://www.omio.com/buses/{q_orig}/{q_dest}/{date}?adults={pax}"},
            {"name":"Google Maps Transit","emoji":"🗺️","desc":"Transit + bus directions",
             "url":f"https://www.google.com/maps/dir/{q_orig}/{q_dest}/?travelmode=transit"},
            {"name":"Busbud",            "emoji":"🎒", "desc":"Buses worldwide — compare prices",
             "url":f"https://www.busbud.com/en/bus-tickets/{q_orig}/{q_dest}?outbound_date={date}"},
        ]

    elif mode in ("taxi","cab","car","drive","driving"):
        return [
            {"name":"Google Maps Drive", "emoji":"🗺️", "desc":"Get driving directions & ETA",
             "url":f"https://www.google.com/maps/dir/{q_orig}/{q_dest}/?travelmode=driving"},
            {"name":"Waze",              "emoji":"📍",  "desc":"Live traffic & fastest route",
             "url":f"https://waze.com/ul?navigate=yes&from={q_orig}&to={q_dest}"},
            {"name":"Uber",              "emoji":"🚖",  "desc":"Book a taxi or ride-share",
             "url":f"https://m.uber.com/go/product-select?pickup={q_orig}&destination={q_dest}"},
            {"name":"Bolt",              "emoji":"⚡",  "desc":"Affordable taxi booking",
             "url":f"https://bolt.eu/en/"},
            {"name":"inDrive",           "emoji":"🚕",  "desc":"Negotiate your fare",
             "url":f"https://indrive.com/"},
        ]

    elif mode in ("ride","uber","bolt","rideshare","ride-share","ride_share"):
        return [
            {"name":"Uber",              "emoji":"🚖",  "desc":"Book a ride now",
             "url":f"https://m.uber.com/go/product-select?pickup={q_orig}&destination={q_dest}"},
            {"name":"Bolt",              "emoji":"⚡",  "desc":"Affordable rides",
             "url":f"https://bolt.eu/en/"},
            {"name":"inDrive",           "emoji":"🚕",  "desc":"Negotiate your price",
             "url":f"https://indrive.com/"},
            {"name":"Lyft",              "emoji":"🩷",  "desc":"Rides in the US & Canada",
             "url":f"https://www.lyft.com/"},
            {"name":"Google Maps Drive", "emoji":"🗺️", "desc":"See route & travel time",
             "url":f"https://www.google.com/maps/dir/{q_orig}/{q_dest}/?travelmode=driving"},
        ]

    elif mode in ("car_rental","car rental","rent","rental","hire"):
        return [
            {"name":"Google Car Rentals","emoji":"🚗",  "desc":"Compare all rental companies",
             "url":f"https://www.google.com/travel/search?q={quote_plus(f'car rental {origin} {date}')}"},
            {"name":"Kayak Car Rental",  "emoji":"🔑",  "desc":"Best rental deals",
             "url":f"https://www.kayak.com/cars/{q_orig}/{date}/{return_date or date}"},
            {"name":"Rentalcars.com",    "emoji":"🏎️", "desc":"100+ suppliers worldwide",
             "url":f"https://www.rentalcars.com/en/pickuplocation/{q_orig}?pickup={date}&return={return_date or date}"},
            {"name":"Booking.com Cars",  "emoji":"🏷️", "desc":"Flexible car hire",
             "url":f"https://www.booking.com/cars/results/{q_orig}.html?pickup_date={date}"},
            {"name":"Enterprise",        "emoji":"🚙",  "desc":"Global car rental",
             "url":f"https://www.enterprise.com/en/car-rental/search.html"},
        ]

    elif mode in ("ferry","boat","ship","cruise"):
        return [
            {"name":"Rome2rio (Ferry)",  "emoji":"⛴️", "desc":"Ferry routes worldwide",
             "url":f"https://www.rome2rio.com/s/{q_orig}/{q_dest}"},
            {"name":"Direct Ferries",    "emoji":"🚢",  "desc":"Book ferry tickets online",
             "url":f"https://www.directferries.com/ferries.htm?from={q_orig}&to={q_dest}&depart={date}"},
            {"name":"Ferryscanner",      "emoji":"🌊",  "desc":"Compare ferry prices",
             "url":f"https://www.ferryscanner.com/en/ferries/{q_orig}/{q_dest}/{date}?adults={pax}"},
            {"name":"Aferry",            "emoji":"⚓",  "desc":"European ferry booking",
             "url":f"https://www.aferry.com/ferry-booking/{q_orig}/{q_dest}/{date}"},
            {"name":"Google Maps Ferry", "emoji":"🗺️", "desc":"Transit directions by water",
             "url":f"https://www.google.com/maps/dir/{q_orig}/{q_dest}/?travelmode=transit"},
        ]

    else:  # "any" — show all modes
        return [
            {"name":"Rome2rio",          "emoji":"🌍",  "desc":"ALL transport modes — flights, trains, buses, ferries",
             "url":f"https://www.rome2rio.com/s/{q_orig}/{q_dest}"},
            {"name":"Google Flights",    "emoji":"✈️",  "desc":"Compare flights",
             "url":f"https://www.google.com/travel/flights?q={quote_plus(f'Flights from {origin} to {destination} on {date}')}"},
            {"name":"Google Maps Transit","emoji":"🚆", "desc":"Trains, buses & transit",
             "url":f"https://www.google.com/maps/dir/{q_orig}/{q_dest}/?travelmode=transit"},
            {"name":"Uber",              "emoji":"🚖",  "desc":"Taxi / ride-share",
             "url":f"https://m.uber.com/go/product-select?pickup={q_orig}&destination={q_dest}"},
            {"name":"Skyscanner",        "emoji":"🔍",  "desc":"Flights + hotels comparison",
             "url":f"https://www.skyscanner.net/transport/flights/{q_orig}/{q_dest}/{date.replace('-','')}/"},
        ]


# ── HTML results page builder ─────────────────────────────────────────────────

def _build_html_page(
    options: list[dict],
    origin: str, destination: str,
    date: str, mode_str: str,
    return_date: str | None = None,
    passengers: int = 1,
) -> str:
    """Build a JARVIS-themed HTML page showing transport options with clickable links."""

    ret_line = f"<div class='sub'>Return: <b>{return_date}</b></div>" if return_date else ""
    pax_line = f"<div class='sub'>{passengers} passenger{'s' if passengers > 1 else ''}</div>" if passengers > 1 else ""

    cards = ""
    for opt in options:
        name  = opt["name"].replace("<","&lt;").replace(">","&gt;")
        desc  = opt["desc"].replace("<","&lt;")
        emoji = opt["emoji"]
        url   = opt["url"]
        cards += f"""
        <a class="card" href="{url}" target="_blank">
            <div class="card-icon">{emoji}</div>
            <div class="card-body">
                <div class="card-title">{name}</div>
                <div class="card-desc">{desc}</div>
            </div>
            <div class="card-arrow">→</div>
        </a>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>JARVIS — {mode_str}: {origin} → {destination}</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{background:#00060a;color:#8ffcff;font-family:'Segoe UI',sans-serif;padding:24px;min-height:100vh}}
  .hdr{{display:flex;align-items:center;gap:14px;margin-bottom:20px;border-bottom:1px solid #0d3347;padding-bottom:16px}}
  .logo{{color:#00d4ff;font-size:1.5rem;font-weight:700;letter-spacing:3px}}
  .title{{font-size:1.1rem;color:#d8f8ff;font-weight:600}}
  .route{{font-size:1.4rem;color:#00d4ff;font-weight:700;margin-bottom:6px;letter-spacing:1px}}
  .sub{{font-size:.85rem;color:#3a8a9a;margin-bottom:3px}}
  .mode-badge{{display:inline-block;background:#001f2e;border:1px solid #00d4ff;
               color:#00d4ff;padding:3px 12px;border-radius:20px;font-size:.8rem;
               font-weight:600;letter-spacing:1px;margin-bottom:18px;text-transform:uppercase}}
  .grid{{display:grid;grid-template-columns:1fr;gap:12px;max-width:700px}}
  .card{{display:flex;align-items:center;gap:16px;background:#010d14;
         border:1px solid #0d3347;border-radius:10px;padding:16px 20px;
         text-decoration:none;color:inherit;transition:border-color .2s,background .2s,transform .1s}}
  .card:hover{{border-color:#00d4ff;background:#011520;transform:translateX(4px)}}
  .card-icon{{font-size:2rem;flex-shrink:0;width:44px;text-align:center}}
  .card-body{{flex:1}}
  .card-title{{font-size:1rem;color:#d8f8ff;font-weight:600;margin-bottom:4px}}
  .card-desc{{font-size:.82rem;color:#3a8a9a}}
  .card-arrow{{color:#00d4ff;font-size:1.2rem;flex-shrink:0;opacity:.6}}
  .card:hover .card-arrow{{opacity:1}}
  .footer{{margin-top:24px;font-size:.75rem;color:#1a4a5a;border-top:1px solid #0d3347;padding-top:14px}}
</style>
</head>
<body>
<div class="hdr">
  <span class="logo">J.A.R.V.I.S</span>
  <div>
    <div class="title">Transport Search Results</div>
  </div>
</div>
<div class="route">{origin} → {destination}</div>
<div class="sub">Departure: <b>{date}</b></div>
{ret_line}{pax_line}
<div class="mode-badge">{mode_str}</div>
<div class="grid">{cards}
</div>
<div class="footer">Click any option to open the booking site in a new tab. Searched at {datetime.now().strftime('%Y-%m-%d %H:%M')}.</div>
</body>
</html>"""

    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".html", delete=False,
        prefix="jarvis_transport_", encoding="utf-8"
    )
    tmp.write(html)
    tmp.close()
    return Path(tmp.name).as_uri()


# ── Public entry point ────────────────────────────────────────────────────────

def transport_finder(
    parameters: dict,
    player=None,
    speak=None,
    response=None,
    session_memory=None,
) -> str:
    """
    Find transport options, build a results page and open it in the user's browser.

    parameters:
        mode        : flight | train | bus | taxi | ride | car_rental | ferry | any
        origin      : departure city / address
        destination : arrival city / address
        date        : departure date (natural language or YYYY-MM-DD)
        return_date : return date for round trips
        passengers  : number of passengers (default: 1)
        cabin       : economy | premium | business | first (flights)
        save        : also save results text to Desktop
    """
    params      = parameters or {}
    mode        = params.get("mode",        "any").lower().strip()
    origin      = params.get("origin",      "").strip()
    destination = params.get("destination", "").strip()
    date_raw    = params.get("date",        "").strip()
    return_raw  = params.get("return_date", "").strip()
    passengers  = max(1, int(params.get("passengers", 1)))
    cabin       = params.get("cabin",       "economy").strip().lower()
    save        = bool(params.get("save",   False))

    if not origin:
        return "Please provide an origin (departure location), boss."
    if not destination:
        return "Please provide a destination, boss."

    date        = _parse_date(date_raw) if date_raw else datetime.now().strftime("%Y-%m-%d")
    return_date = _parse_date(return_raw) if return_raw else None

    if player:
        player.write_log(f"[Transport] {mode}: {origin} → {destination}")

    print(f"[Transport] {mode}: {origin} → {destination} | {date} | {passengers} pax")

    # ── Map mode to display name ──────────────────────────────────────────────
    mode_names = {
        "flight":"Flights","flights":"Flights","fly":"Flights","plane":"Flights","air":"Flights",
        "train":"Trains","rail":"Trains","railway":"Trains",
        "bus":"Bus / Coach","coach":"Bus / Coach",
        "taxi":"Taxi / Driving","cab":"Taxi / Driving","car":"Taxi / Driving",
        "drive":"Taxi / Driving","driving":"Taxi / Driving",
        "ride":"Ride-Share","uber":"Ride-Share","bolt":"Ride-Share",
        "rideshare":"Ride-Share","ride-share":"Ride-Share","ride_share":"Ride-Share",
        "car_rental":"Car Rental","car rental":"Car Rental",
        "rent":"Car Rental","rental":"Car Rental","hire":"Car Rental",
        "ferry":"Ferry / Boat","boat":"Ferry / Boat","ship":"Ferry / Boat","cruise":"Ferry / Boat",
    }
    mode_str = mode_names.get(mode, "All Transport Options")

    # ── Get options and build HTML results page ───────────────────────────────
    options  = _get_options(mode, origin, destination, date, return_date, passengers, cabin)
    page_url = _build_html_page(options, origin, destination, date, mode_str,
                                return_date=return_date, passengers=passengers)

    print(f"[Transport] Opening results page: {page_url[:80]}")
    _open_url(page_url)

    # ── Build spoken response ─────────────────────────────────────────────────
    try:
        date_spoken = datetime.strptime(date, "%Y-%m-%d").strftime("%B %d")
    except Exception:
        date_spoken = date

    ret_spoken = ""
    if return_date:
        try:
            ret_spoken = f" returning {datetime.strptime(return_date,'%Y-%m-%d').strftime('%B %d')}"
        except Exception:
            ret_spoken = f" returning {return_date}"

    pax_spoken = f" for {passengers} passengers" if passengers > 1 else ""
    site_count = len(options)

    spoken = (
        f"I found {site_count} {mode_str.lower()} options from {origin} to {destination} "
        f"on {date_spoken}{ret_spoken}{pax_spoken}, boss. "
        f"Opening the results in your browser now — click any option to book."
    )

    if speak:
        speak(spoken)

    # ── Optional Desktop save ─────────────────────────────────────────────────
    if save:
        ts    = datetime.now().strftime("%Y%m%d_%H%M%S")
        fname = f"transport_{origin}_{destination}_{ts}.txt".replace(" ", "_")
        fpath = Path.home() / "Desktop" / fname
        lines = [
            f"JARVIS — {mode_str} Search Results",
            "─" * 50,
            f"From       : {origin}",
            f"To         : {destination}",
            f"Date       : {date}",
        ]
        if return_date:
            lines.append(f"Return     : {return_date}")
        lines += [
            f"Passengers : {passengers}",
            f"Searched   : {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "─" * 50,
            "",
        ]
        for i, opt in enumerate(options, 1):
            lines.append(f"{i}. {opt['emoji']} {opt['name']}")
            lines.append(f"   {opt['desc']}")
            lines.append(f"   {opt['url']}")
            lines.append("")
        fpath.write_text("\n".join(lines), encoding="utf-8")
        try:
            subprocess.Popen(["notepad.exe", str(fpath)])
        except Exception:
            pass
        spoken += f" Also saved to Desktop: {fpath.name}"

    return spoken


# ── Backwards-compatibility alias ─────────────────────────────────────────────

def flight_finder(parameters: dict, player=None, speak=None,
                  response=None, session_memory=None) -> str:
    """Legacy alias — routes to transport_finder with mode=flight."""
    p = dict(parameters or {})
    if "mode" not in p:
        p["mode"] = "flight"
    return transport_finder(p, player=player, speak=speak)
