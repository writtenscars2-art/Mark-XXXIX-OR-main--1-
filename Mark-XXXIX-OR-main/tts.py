"""
tts.py — ElevenLabs TTS engine for JARVIS
Streams audio from ElevenLabs directly into sounddevice output.
Falls back to a simple print if ElevenLabs is unavailable.
"""
import json
import threading
import queue
import sys
from pathlib import Path

import sounddevice as sd
import numpy as np

# ── Config ────────────────────────────────────────────────────────────────────
def _get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent

BASE_DIR        = _get_base_dir()
API_CONFIG_PATH = BASE_DIR / "config" / "api_keys.json"

SAMPLE_RATE = 22050   # ElevenLabs PCM output rate
CHANNELS    = 1
CHUNK_SIZE  = 4096


def _load_el_config() -> tuple[str, str]:
    try:
        with open(API_CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return (
            data.get("elevenlabs_api_key",  "").strip(),
            data.get("elevenlabs_voice_id", "").strip(),
        )
    except Exception as e:
        print(f"[TTS] ERROR Could not load config: {e}")
        return "", ""


# ── ElevenLabs streaming TTS ─────────────────────────────────────────────────
class ElevenLabsTTS:
    """
    Thread-safe TTS engine.
    Streams MP3/PCM audio from ElevenLabs and plays it via sounddevice.
    A serial queue ensures responses never overlap.
    """

    def __init__(self, on_speaking_change=None):
        self._api_key, self._voice_id = _load_el_config()
        self._on_speaking_change = on_speaking_change   # callback(bool)
        self._q: queue.Queue = queue.Queue()
        self._worker = threading.Thread(target=self._run, daemon=True)
        self._worker.start()
        self._available = bool(self._api_key and self._voice_id)
        if self._available:
            print(f"[TTS] OK ElevenLabs ready -- voice: {self._voice_id}")
        else:
            print("[TTS] WARNING ElevenLabs not configured -- using silent fallback")

    # public -----------------------------------------------------------------

    def speak(self, text: str):
        """Queue text for speech. Non-blocking."""
        text = (text or "").strip()
        if not text:
            return
        self._q.put(text)

    def stop(self):
        """Signal worker to stop."""
        self._q.put(None)

    # internal ---------------------------------------------------------------

    def _run(self):
        while True:
            item = self._q.get()
            if item is None:
                break
            # Play immediately — sentences arrive one at a time now
            self._play(item)

    def _play(self, text: str):
        if not self._available:
            print(f"[TTS] (no voice) {text}")
            return

        self._set_speaking(True)
        try:
            from elevenlabs import ElevenLabs
            client = ElevenLabs(api_key=self._api_key)

            # Request PCM_22050 so we don't need an MP3 decoder
            audio_iter = client.text_to_speech.convert(
                voice_id=self._voice_id,
                text=text,
                model_id="eleven_flash_v2_5",
                output_format="pcm_22050",
            )

            stream = sd.RawOutputStream(
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                dtype="int16",
                blocksize=CHUNK_SIZE,
            )
            stream.start()
            try:
                for chunk in audio_iter:
                    if chunk:
                        stream.write(chunk)
            finally:
                stream.stop()
                stream.close()

        except Exception as e:
            print(f"[TTS] ERROR ElevenLabs error: {e}")
        finally:
            self._set_speaking(False)

    def _set_speaking(self, value: bool):
        if self._on_speaking_change:
            try:
                self._on_speaking_change(value)
            except Exception:
                pass


# ── Module-level singleton ────────────────────────────────────────────────────
_tts_instance: ElevenLabsTTS | None = None
_lock = threading.Lock()


def get_tts(on_speaking_change=None) -> ElevenLabsTTS:
    global _tts_instance
    with _lock:
        if _tts_instance is None:
            _tts_instance = ElevenLabsTTS(on_speaking_change=on_speaking_change)
        return _tts_instance


def speak(text: str):
    """Module-level convenience function."""
    get_tts().speak(text)
