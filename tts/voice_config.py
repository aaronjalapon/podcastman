"""Voice persona configuration for the two podcast hosts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from config.settings import settings
from models.data import Speaker


@dataclass
class VoicePersona:
    """Configuration for a single voice persona."""

    name: str
    speaker: Speaker
    reference_audio: Path
    language: str = "en"
    speed: float = 1.0
    description: str = ""

    @property
    def reference_exists(self) -> bool:
        return self.reference_audio.exists()


# ── Default Personas ─────────────────────────────────────────────────────────

HOST_A = VoicePersona(
    name="Mike",
    speaker=Speaker.HOST_A,
    reference_audio=Path(settings.voice_a_reference),
    language=settings.tts_language,
    speed=1.0,
    description="Main presenter, confident and knowledgeable tone",
)

HOST_B = VoicePersona(
    name="Sarah",
    speaker=Speaker.HOST_B,
    reference_audio=Path(settings.voice_b_reference),
    language=settings.tts_language,
    speed=1.0,
    description="Co-host, curious and enthusiastic tone",
)


def get_voice(speaker: Speaker) -> VoicePersona:
    """Get the voice persona for a speaker."""
    if speaker == Speaker.HOST_A:
        return HOST_A
    return HOST_B
