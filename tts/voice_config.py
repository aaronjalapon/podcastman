"""Voice persona configuration for the two podcast hosts."""

from __future__ import annotations

from dataclasses import dataclass

from config.settings import settings
from models.data import Speaker


@dataclass
class VoicePersona:
    """Configuration for a single voice persona."""

    name: str
    speaker: Speaker
    voice_name: str
    language_code: str = "en-US"
    speed: float = 1.0
    description: str = ""


# ── Default Personas ─────────────────────────────────────────────────────────

HOST_A = VoicePersona(
    name="Mike",
    speaker=Speaker.HOST_A,
    voice_name=settings.google_tts_voice_a,
    language_code=settings.google_tts_language_code,
    speed=1.0,
    description="Main presenter, confident and knowledgeable tone",
)

HOST_B = VoicePersona(
    name="Sarah",
    speaker=Speaker.HOST_B,
    voice_name=settings.google_tts_voice_b,
    language_code=settings.google_tts_language_code,
    speed=1.0,
    description="Co-host, curious and enthusiastic tone",
)


def get_voice(speaker: Speaker) -> VoicePersona:
    """Get the voice persona for a speaker."""
    if speaker == Speaker.HOST_A:
        return HOST_A
    return HOST_B
