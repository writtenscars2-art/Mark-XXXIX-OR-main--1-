"""
Rewrites TOOL_DECLARATIONS in main.py with trimmed descriptions.
Shorter descriptions = fewer input tokens = faster NVIDIA NIM response.
"""
from pathlib import Path

src = Path(__file__).parent / "main.py"
txt = src.read_text(encoding="utf-8")

# Find and replace the TOOL_DECLARATIONS block with a tighter version
OLD = 'TOOL_DECLARATIONS = ['
END = ']\n\n\ndef _split_sentences'

i0 = txt.index(OLD)
i1 = txt.index(END) + 1  # keep the closing ]

NEW_TOOLS = '''TOOL_DECLARATIONS = [
    {"name": "open_app",          "description": "Opens any app, program or website on Windows.", "parameters": {"type": "OBJECT", "properties": {"app_name": {"type": "STRING", "description": "App name e.g. Chrome, Spotify"}}, "required": ["app_name"]}},
    {"name": "web_search",        "description": "Searches the live web. Use for any current event, news, price, or fact.", "parameters": {"type": "OBJECT", "properties": {"query": {"type": "STRING"}, "mode": {"type": "STRING"}, "items": {"type": "ARRAY", "items": {"type": "STRING"}}, "aspect": {"type": "STRING"}}, "required": ["query"]}},
    {"name": "weather_report",    "description": "Gets current weather for a city.", "parameters": {"type": "OBJECT", "properties": {"city": {"type": "STRING"}}, "required": ["city"]}},
    {"name": "send_message",      "description": "Sends a message via WhatsApp, Telegram, etc.", "parameters": {"type": "OBJECT", "properties": {"receiver": {"type": "STRING"}, "message_text": {"type": "STRING"}, "platform": {"type": "STRING"}}, "required": ["receiver", "message_text", "platform"]}},
    {"name": "reminder",          "description": "Sets a Windows Task Scheduler reminder.", "parameters": {"type": "OBJECT", "properties": {"date": {"type": "STRING"}, "time": {"type": "STRING"}, "message": {"type": "STRING"}}, "required": ["date", "time", "message"]}},
    {"name": "youtube_video",     "description": "Plays, summarizes, or shows trending YouTube videos.", "parameters": {"type": "OBJECT", "properties": {"action": {"type": "STRING"}, "query": {"type": "STRING"}, "save": {"type": "BOOLEAN"}, "region": {"type": "STRING"}, "url": {"type": "STRING"}}, "required": []}},
    {"name": "screen_process",    "description": "Captures screen or webcam and analyzes with AI vision. Call when user asks what\'s on screen or look at camera. Stay silent after — vision module speaks directly.", "parameters": {"type": "OBJECT", "properties": {"angle": {"type": "STRING"}, "text": {"type": "STRING"}}, "required": ["text"]}},
    {"name": "computer_settings", "description": "Controls PC: volume, brightness, WiFi, screenshots, window management, dark mode, shutdown, scroll, zoom.", "parameters": {"type": "OBJECT", "properties": {"action": {"type": "STRING"}, "description": {"type": "STRING"}, "value": {"type": "STRING"}}, "required": []}},
    {"name": "browser_control",   "description": "Controls browser: open URLs, search, click, scroll, fill forms, get page text.", "parameters": {"type": "OBJECT", "properties": {"action": {"type": "STRING"}, "url": {"type": "STRING"}, "query": {"type": "STRING"}, "selector": {"type": "STRING"}, "text": {"type": "STRING"}, "description": {"type": "STRING"}, "direction": {"type": "STRING"}, "key": {"type": "STRING"}, "incognito": {"type": "BOOLEAN"}}, "required": ["action"]}},
    {"name": "file_controller",   "description": "Manages files/folders: list, read, write, create, delete, move, copy, rename, find, disk usage.", "parameters": {"type": "OBJECT", "properties": {"action": {"type": "STRING"}, "path": {"type": "STRING"}, "destination": {"type": "STRING"}, "new_name": {"type": "STRING"}, "content": {"type": "STRING"}, "name": {"type": "STRING"}, "extension": {"type": "STRING"}, "count": {"type": "INTEGER"}}, "required": ["action"]}},
    {"name": "desktop_control",   "description": "Controls desktop: wallpaper, organize, clean, list, stats.", "parameters": {"type": "OBJECT", "properties": {"action": {"type": "STRING"}, "path": {"type": "STRING"}, "url": {"type": "STRING"}, "mode": {"type": "STRING"}, "task": {"type": "STRING"}}, "required": ["action"]}},
    {"name": "code_helper",       "description": "Writes, edits, explains, runs or builds code.", "parameters": {"type": "OBJECT", "properties": {"action": {"type": "STRING"}, "description": {"type": "STRING"}, "language": {"type": "STRING"}, "output_path": {"type": "STRING"}, "file_path": {"type": "STRING"}, "code": {"type": "STRING"}, "args": {"type": "STRING"}, "timeout": {"type": "INTEGER"}}, "required": ["action"]}},
    {"name": "dev_agent",         "description": "Builds complete multi-file projects from scratch.", "parameters": {"type": "OBJECT", "properties": {"description": {"type": "STRING"}, "language": {"type": "STRING"}, "project_name": {"type": "STRING"}, "timeout": {"type": "INTEGER"}}, "required": ["description"]}},
    {"name": "agent_task",        "description": "Executes complex multi-step tasks needing multiple tools. Not for single actions.", "parameters": {"type": "OBJECT", "properties": {"goal": {"type": "STRING"}, "priority": {"type": "STRING"}}, "required": ["goal"]}},
    {"name": "computer_control",  "description": "Direct mouse/keyboard control: type, click, hotkeys, scroll, screenshot, find screen elements.", "parameters": {"type": "OBJECT", "properties": {"action": {"type": "STRING"}, "text": {"type": "STRING"}, "x": {"type": "INTEGER"}, "y": {"type": "INTEGER"}, "keys": {"type": "STRING"}, "key": {"type": "STRING"}, "direction": {"type": "STRING"}, "amount": {"type": "INTEGER"}, "seconds": {"type": "NUMBER"}, "title": {"type": "STRING"}, "description": {"type": "STRING"}, "path": {"type": "STRING"}}, "required": ["action"]}},
    {"name": "game_updater",      "description": "THE ONLY tool for Steam or Epic Games: update, install, list, schedule. Never use web_search for games.", "parameters": {"type": "OBJECT", "properties": {"action": {"type": "STRING"}, "platform": {"type": "STRING"}, "game_name": {"type": "STRING"}, "app_id": {"type": "STRING"}, "hour": {"type": "INTEGER"}, "minute": {"type": "INTEGER"}, "shutdown_when_done": {"type": "BOOLEAN"}}, "required": []}},
    {"name": "flight_finder",     "description": "Searches Google Flights and speaks best options.", "parameters": {"type": "OBJECT", "properties": {"origin": {"type": "STRING"}, "destination": {"type": "STRING"}, "date": {"type": "STRING"}, "return_date": {"type": "STRING"}, "passengers": {"type": "INTEGER"}, "cabin": {"type": "STRING"}, "save": {"type": "BOOLEAN"}}, "required": ["origin", "destination", "date"]}},
    {"name": "file_processor",    "description": "Processes uploaded files: images, PDFs, Word, Excel, CSV, JSON, code, audio, video, archives, presentations.", "parameters": {"type": "OBJECT", "properties": {"file_path": {"type": "STRING"}, "action": {"type": "STRING"}, "instruction": {"type": "STRING"}, "format": {"type": "STRING"}, "width": {"type": "INTEGER"}, "height": {"type": "INTEGER"}, "quality": {"type": "INTEGER"}, "save": {"type": "BOOLEAN"}}, "required": []}},
    {"name": "shutdown_jarvis",   "description": "Shuts down JARVIS completely. Call when user says goodbye or wants to exit.", "parameters": {"type": "OBJECT", "properties": {}}},
    {"name": "save_memory",       "description": "Silently saves personal facts about the user to long-term memory. Call when user reveals name, job, preferences, plans.", "parameters": {"type": "OBJECT", "properties": {"category": {"type": "STRING"}, "key": {"type": "STRING"}, "value": {"type": "STRING"}}, "required": ["category", "key", "value"]}},
]
'''

txt = txt[:i0] + NEW_TOOLS + txt[i1:]
src.write_text(txt, encoding="utf-8")
print("Tool declarations trimmed OK")
