"""
gemini_client.py — Compatibility shim.
All AI generation is now handled by claude_client.py (Anthropic Claude).
This module re-exports claude_client's interface so any legacy import still works.
"""

# Re-export everything from claude_client for drop-in compatibility
from claude_client import generate, generate_json

__all__ = ["generate", "generate_json"]
