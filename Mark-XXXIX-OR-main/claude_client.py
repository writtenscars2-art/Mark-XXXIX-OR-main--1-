"""
claude_client.py — AI generation wrapper for JARVIS.
Primary  : NVIDIA NIM  (nvapi key, OpenAI-compatible, free tier)
Fallback : Anthropic Claude (claude_api_key, if credits available)

All subsystems (planner, executor, memory, tools) call generate() here.
"""
import json
import sys
import base64
import re
from pathlib import Path


def _get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent


API_CONFIG_PATH = _get_base_dir() / "config" / "api_keys.json"

# NVIDIA NIM — OpenAI-compatible endpoint
NVIDIA_BASE_URL   = "https://integrate.api.nvidia.com/v1"
NVIDIA_MODEL      = "meta/llama-3.3-70b-instruct"
NVIDIA_MODEL_FAST = "meta/llama-3.3-70b-instruct"


def _load_config() -> dict:
    try:
        with open(API_CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _get_nvidia_key() -> str:
    return _load_config().get("nvidia_api_key", "").strip()


def _get_claude_key() -> str:
    return _load_config().get("claude_api_key", "").strip()


def _get_nvidia_model() -> str:
    """Read model from config — change nvidia_model in api_keys.json to switch."""
    return _load_config().get("nvidia_model", "meta/llama-3.3-70b-instruct").strip() or "meta/llama-3.3-70b-instruct"


def _pick_nvidia_model(model: str) -> str:
    """Map any model hint to the configured NVIDIA model."""
    configured = _get_nvidia_model()
    # If caller explicitly passed a valid nvidia model name, honour it
    if model and model.startswith(("meta/", "nvidia/", "mistral/", "google/", "qwen/")):
        return model
    return configured


def generate(
    prompt: str,
    system: str = "",
    model: str = "nvidia/llama-3.3-nemotron-super-49b-v1",
    *,
    image_bytes: bytes | None = None,
    mime_type: str = "image/png",
) -> str:
    """
    Generate a text response.
    Tries NVIDIA NIM first, falls back to Anthropic Claude if NIM key missing.
    """
    nvidia_key = _get_nvidia_key()

    if nvidia_key:
        return _generate_nvidia(prompt, system, model, image_bytes, mime_type, nvidia_key)

    # Fallback to Anthropic
    claude_key = _get_claude_key()
    if claude_key:
        return _generate_claude(prompt, system, model, image_bytes, mime_type, claude_key)

    raise RuntimeError(
        "No AI API key configured. Add nvidia_api_key or claude_api_key to config/api_keys.json."
    )


def _generate_nvidia(
    prompt: str,
    system: str,
    model: str,
    image_bytes: bytes | None,
    mime_type: str,
    api_key: str,
) -> str:
    from openai import OpenAI

    client = OpenAI(
        base_url=NVIDIA_BASE_URL,
        api_key=api_key,
    )

    nim_model = _pick_nvidia_model(model)

    messages = []
    if system:
        messages.append({"role": "system", "content": system})

    if image_bytes:
        # Vision: encode image as base64 data URL
        b64 = base64.standard_b64encode(image_bytes).decode()
        messages.append({
            "role": "user",
            "content": [
                {"type": "text",      "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64}"}},
            ],
        })
    else:
        messages.append({"role": "user", "content": prompt})

    response = client.chat.completions.create(
        model=nim_model,
        messages=messages,
        max_tokens=2048,
        temperature=0.6,
    )

    return (response.choices[0].message.content or "").strip()


def _generate_claude(
    prompt: str,
    system: str,
    model: str,
    image_bytes: bytes | None,
    mime_type: str,
    api_key: str,
) -> str:
    from anthropic import Anthropic

    # Map non-Claude model names
    if not model.startswith("claude"):
        if any(x in model.lower() for x in ("lite", "flash", "haiku", "fast")):
            model = "claude-3-5-haiku-20241022"
        else:
            model = "claude-3-5-sonnet-20241022"

    client = Anthropic(api_key=api_key)

    content: list = []
    if image_bytes:
        content.append({
            "type": "image",
            "source": {
                "type":       "base64",
                "media_type": mime_type,
                "data":       base64.standard_b64encode(image_bytes).decode(),
            },
        })
    content.append({"type": "text", "text": prompt})

    response = client.messages.create(
        model=model,
        max_tokens=2048,
        system=system if system else None,
        messages=[{"role": "user", "content": content}],
    )

    parts = [b.text for b in response.content if hasattr(b, "text")]
    return "".join(parts).strip()


def generate_json(
    prompt: str,
    system: str = "Return ONLY valid JSON. No markdown fences, no extra text.",
    model: str = "nvidia/llama-3.3-nemotron-super-49b-v1",
) -> dict | list:
    """Generate and parse a JSON response."""
    raw   = generate(prompt, system=system, model=model)
    clean = raw.strip()
    clean = re.sub(r"^```(?:json)?\s*", "", clean)
    clean = re.sub(r"\s*```$", "", clean)
    return json.loads(clean.strip())
