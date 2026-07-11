"""
tts.py — TTS engine for JARVIS
Primary  : ElevenLabs Flash v2.5 (streaming PCM, high quality)
Fallback : Windows SAPI via win32com (free, built-in, works offline)

Features:
  - Automatic SAPI fallback on quota or network error
  - clear() method to cancel all pending speech instantly
  - Configurable speed/stability via api_keys.json
  - Better SAPI voice selection (prefers female English voice)
  - Queue size cap to prevent speech pileup
  - Auto-retry ElevenLabs after cooldown
"""
import json
import threading
import queue
import sys
import time
from pathlib import Path

import sounddevice as sd


def _get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent


BASE_DIR        = _get_base_dir()
API_CONFIG_PATH = BASE_DIR / "config" / "api_keys.json"

SAMPLE_RATE   = 22050
CHANNELS      = 1
CHUNK_SIZE    = 4096
MAX_QUEUE     = 6      # max pending utterances — older ones dropped if exceeded


def _load_el_config() -> tuple[str, str, dict]:
    """Returns (api_key, voice_id, extra_settings)."""
    try:
        with open(API_CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return (
            data.get("elevenlabs_api_key",  "").strip(),
            data.get("elevenlabs_voice_id", "").strip(),
            {
                "stability":        float(data.get("tts_stability",        0.45)),
                "similarity_boost": float(data.get("tts_similarity_boost", 0.85)),
                "style":            float(data.get("tts_style",            0.0)),
                "speed":            float(data.get("tts_speed",            1.0)),
            },
        )
    except Exception as e:
        print(f"[TTS] ERROR Could not load config: {e}")
        return "", "", {}


def _sapi_speak(text: str):
    """Windows SAPI TTS — offline, no quota, instant."""
    try:
        from win32com.client import Dispatch
        sapi   = Dispatch("SAPI.SpVoice")

        # Prefer female English voice for JARVIS
        voices = sapi.GetVoices()
        chosen = None
        for i in range(voices.Count):
            v    = voices.Item(i)
            desc = v.GetDescription().lower()
            if any(n in desc for n in ("zira", "hazel", "helen", "eva", "female")):
                chosen = v
                break
        if chosen is None and voices.Count > 0:
            chosen = voices.Item(0)   # fallback: first available
        if chosen:
            sapi.Voice = chosen

        sapi.Rate   = 2      # slightly fast — matches ElevenLabs cadence better
        sapi.Volume = 100
        sapi.Speak(text)
    except Exception as e:
        print(f"[TTS] SAPI error: {e}")
        print(f"JARVIS: {text}")


class ElevenLabsTTS:
    """
    Thread-safe TTS with automatic SAPI fallback and queue management.
    """

    def __init__(self, on_speaking_change=None):
        self._api_key, self._voice_id, self._settings = _load_el_config()
        self._on_speaking_change = on_speaking_change
        self._q: queue.Queue     = queue.Queue(maxsize=MAX_QUEUE)
        self._el_available       = bool(self._api_key and self._voice_id)
        self._quota_exceeded     = False
        self._quota_retry_at     = 0.0
        self._stop_flag          = threading.Event()   # set to interrupt current playback
        self._lock               = threading.Lock()

        self._worker = threading.Thread(target=self._run, daemon=True)
        self._worker.start()

        if self._el_available:
            print(f"[TTS] OK ElevenLabs ready — voice: {self._voice_id}")
        else:
            print("[TTS] ElevenLabs not configured — using SAPI fallback")

    def speak(self, text: str):
        """Queue text for speech. Drops oldest item if queue is full."""
        text = (text or "").strip()
        if not text:
            return
        try:
            self._q.put_nowait(text)
        except queue.Full:
            # Queue full — discard oldest, add new
            try:
                self._q.get_nowait()
            except queue.Empty:
                pass
            try:
                self._q.put_nowait(text)
            except queue.Full:
                pass

    def clear(self):
        """Cancel all pending speech and stop current playback immediately."""
        self._stop_flag.set()
        # Drain the queue
        while not self._q.empty():
            try:
                self._q.get_nowait()
            except queue.Empty:
                break
        # Reset the stop flag after a short pause so future speech works
        threading.Timer(0.15, self._stop_flag.clear).start()

    def stop(self):
        """Graceful shutdown — sends sentinel to worker thread."""
        self._q.put(None)

    def _run(self):
        while True:
            item = self._q.get()
            if item is None:
                break
            if not self._stop_flag.is_set():
                self._play(item)

    def _play(self, text: str):
        self._set_speaking(True)
        try:
            # Retry ElevenLabs after cooldown
            if self._quota_exceeded and time.time() > self._quota_retry_at:
                self._quota_exceeded = False
                print("[TTS] Retrying ElevenLabs after cooldown...")

            if self._el_available and not self._quota_exceeded:
                try:
                    self._play_elevenlabs(text)
                    return
                except Exception as e:
                    err = str(e).lower()
                    if any(x in err for x in ("quota_exceeded", "quota exceeded", "0 credits")):
                        self._quota_exceeded = True
                        self._quota_retry_at = time.time() + 300   # 5 min
                        print("[TTS] ElevenLabs quota exhausted — SAPI for 5 min")
                    elif any(x in err for x in (
                        "getaddrinfo", "name resolution", "network",
                        "connection", "timeout", "unreachable", "errno 11001",
                    )):
                        self._quota_exceeded = True
                        self._quota_retry_at = time.time() + 30    # 30s retry
                        print("[TTS] ElevenLabs unreachable — SAPI fallback (30s retry)")
                    else:
                        print(f"[TTS] ElevenLabs error: {str(e)[:120]}")

            _sapi_speak(text)

        finally:
            self._set_speaking(False)

    def _play_elevenlabs(self, text: str):
        from elevenlabs import ElevenLabs
        client     = ElevenLabs(api_key=self._api_key)
        settings   = self._settings

        audio_iter = client.text_to_speech.convert(
            voice_id              = self._voice_id,
            text                  = text,
            model_id              = "eleven_flash_v2_5",
            output_format         = "pcm_22050",
            voice_settings        = {
                "stability":        settings.get("stability",        0.45),
                "similarity_boost": settings.get("similarity_boost", 0.85),
                "style":            settings.get("style",            0.0),
                "speed":            settings.get("speed",            1.0),
            },
        )
        stream = sd.RawOutputStream(
            samplerate = SAMPLE_RATE,
            channels   = CHANNELS,
            dtype      = "int16",
            blocksize  = CHUNK_SIZE,
        )
        stream.start()
        try:
            for chunk in audio_iter:
                if self._stop_flag.is_set():
                    break
                if chunk:
                    stream.write(chunk)
        finally:
            stream.stop()
            stream.close()

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
    get_tts().speak(text)
