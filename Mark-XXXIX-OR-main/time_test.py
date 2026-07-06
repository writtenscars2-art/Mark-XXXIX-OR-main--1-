"""Time every step of JARVIS's response pipeline."""
import sys, time, json
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = r"c:\Users\user\Downloads\Mark-XXXIX-OR-main (1)\Mark-XXXIX-OR-main"
cfg  = json.load(open(BASE + r"\config\api_keys.json"))

from openai import OpenAI
client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=cfg["nvidia_api_key"]
)
model = cfg.get("nvidia_model", "meta/llama-3.3-70b-instruct")

print(f"Model: {model}")
print()

# -- Test 1: non-streaming, simple reply --
print("=== TEST 1: Non-streaming simple reply ===")
t0 = time.perf_counter()
r = client.chat.completions.create(
    model=model,
    messages=[{"role":"user","content":"Say: All systems online."}],
    max_tokens=10, temperature=0.1, stream=False
)
print(f"Non-stream: {time.perf_counter()-t0:.2f}s — {r.choices[0].message.content!r}")

# -- Test 2: streaming, time to first token --
print()
print("=== TEST 2: Streaming — time to first token ===")
t0 = time.perf_counter()
first_token_t = None
full = ""
stream = client.chat.completions.create(
    model=model,
    messages=[{"role":"user","content":"Briefly: what is 2+2?"}],
    max_tokens=20, temperature=0.1, stream=True
)
for chunk in stream:
    delta = chunk.choices[0].delta
    if delta.content:
        if first_token_t is None:
            first_token_t = time.perf_counter()
            print(f"  First token: {first_token_t-t0:.2f}s")
        full += delta.content
total_t = time.perf_counter() - t0
print(f"  Full reply: {total_t:.2f}s — {full!r}")

# -- Test 3: with tools (like JARVIS does) --
print()
print("=== TEST 3: Streaming with tools ===")
tools = [{"type":"function","function":{"name":"web_search","description":"Search web","parameters":{"type":"object","properties":{"query":{"type":"string"}},"required":["query"]}}}]
t0 = time.perf_counter()
first_t = None
full2 = ""
stream2 = client.chat.completions.create(
    model=model,
    messages=[{"role":"user","content":"What time is it?"}],
    tools=tools, tool_choice="auto",
    max_tokens=50, temperature=0.1, stream=True
)
finish = None
for chunk in stream2:
    delta = chunk.choices[0].delta
    finish = chunk.choices[0].finish_reason
    if delta.content:
        if first_t is None:
            first_t = time.perf_counter()
            print(f"  First token: {first_t-t0:.2f}s")
        full2 += delta.content
total2 = time.perf_counter() - t0
print(f"  Full reply: {total2:.2f}s | finish_reason: {finish} | text: {full2!r}")
