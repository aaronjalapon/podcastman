"""Google Cloud TTS voice synthesis engine."""

from __future__ import annotations

import os
import shutil
import time
import uuid
from pathlib import Path
from typing import Callable

from google.cloud import texttospeech

from config.settings import settings
from models.data import SpeakerSegment
from tts.voice_config import get_voice
from utils.helpers import get_logger

log = get_logger(__name__)

# Maximum age (seconds) before an orphaned run directory is considered stale
_MAX_RUN_AGE_SECONDS = 60 * 60  # 1 hour

# Lazy-initialised client
_tts_client: texttospeech.TextToSpeechClient | None = None


def _get_client() -> texttospeech.TextToSpeechClient:
    """Return a (cached) Google Cloud TTS client."""
    global _tts_client
    if _tts_client is None:
        # If a path is provided (local/dev), use it. In Cloud Run, ADC is preferred.
        if settings.google_application_credentials:
            os.environ.setdefault(
                "GOOGLE_APPLICATION_CREDENTIALS",
                settings.google_application_credentials,
            )
            log.info("Initialising TTS client using GOOGLE_APPLICATION_CREDENTIALS path")
        else:
            log.info("Initialising TTS client using Application Default Credentials")
        _tts_client = texttospeech.TextToSpeechClient()
        log.info("Google Cloud TTS client initialised")
    return _tts_client


# ── SSML builder ─────────────────────────────────────────────────────────────

_SSML_CUE_MAP: dict[str, tuple[str, str]] = {
    "pause": ('<break time="500ms"/>', ""),
    "emphasis": ('<emphasis level="strong">', "</emphasis>"),
    "excited": ('<prosody rate="fast" pitch="+2st">', "</prosody>"),
    "thoughtful": ('<prosody rate="slow">', "</prosody>"),
    "serious": ('<prosody rate="slow" pitch="-1st">', "</prosody>"),
    "laughing": ('<prosody pitch="+1st">', "</prosody>"),
}


def _build_ssml(text: str, cues: list[str]) -> str:
    """Wrap *text* in an SSML ``<speak>`` element, applying cue markers."""
    # Escape XML special characters in the text
    escaped = (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )

    prefix_tags: list[str] = []
    suffix_tags: list[str] = []

    for cue in cues:
        mapping = _SSML_CUE_MAP.get(cue.lower())
        if mapping is None:
            continue
        opening, closing = mapping
        if closing:
            prefix_tags.append(opening)
            suffix_tags.insert(0, closing)
        else:
            # Self-closing tag (e.g. <break/>) — prepend before text
            prefix_tags.append(opening)

    inner = "".join(prefix_tags) + escaped + "".join(suffix_tags)
    return f"<speak>{inner}</speak>"


# ── Synthesis ────────────────────────────────────────────────────────────────


def synthesize_segment(
    segment: SpeakerSegment,
    output_dir: Path | None = None,
) -> Path:
    """Synthesize a single speaker segment to a WAV file via Google Cloud TTS.

    Args:
        segment: The speaker segment to synthesize.
        output_dir: Directory for output files. Defaults to settings.segments_path.

    Returns:
        Path to the generated WAV file.
    """
    output_dir = output_dir or settings.segments_path
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    voice_cfg = get_voice(segment.speaker)
    output_path = output_dir / f"segment_{segment.index:04d}_{segment.speaker.value}.wav"

    log.info(
        "Synthesizing segment %d (%s / %s, %d chars): %.50s...",
        segment.index,
        voice_cfg.name,
        voice_cfg.voice_name,
        len(segment.text),
        segment.text,
    )

    client = _get_client()

    ssml = _build_ssml(segment.text, segment.cues)

    synthesis_input = texttospeech.SynthesisInput(ssml=ssml)

    voice_params = texttospeech.VoiceSelectionParams(
        language_code=voice_cfg.language_code,
        name=voice_cfg.voice_name,
    )

    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.LINEAR16,
        speaking_rate=voice_cfg.speed,
    )

    response = client.synthesize_speech(
        input=synthesis_input,
        voice=voice_params,
        audio_config=audio_config,
    )

    output_path.write_bytes(response.audio_content)

    log.info("Segment %d saved to %s", segment.index, output_path)
    return output_path


def synthesize_all(
    segments: list[SpeakerSegment],
    output_dir: Path | None = None,
    on_segment_done: Callable[[int, int], None] | None = None,
    run_id: str | None = None,
) -> tuple[list[Path], Path]:
    """Synthesize all segments into an isolated per-run subdirectory.

    Each call gets its own directory keyed by run_id, so concurrent users
    never interfere with each other's files.

    Args:
        segments: List of speaker segments to synthesize.
        output_dir: Base directory for segments. Defaults to settings.segments_path.
        on_segment_done: Optional callback(completed, total) called after each segment.
        run_id: Unique identifier for this run. Auto-generated UUID if not provided.

    Returns:
        Tuple of (list of WAV paths, run_dir). Pass run_dir to cleanup_run()
        after assembly to free disk space.
    """
    base_dir = Path(output_dir or settings.segments_path)

    # Each run gets its own isolated subdirectory — safe for concurrent users
    run_id = run_id or uuid.uuid4().hex
    run_dir = base_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    log.info("Run [%s] segments directory: %s", run_id, run_dir)

    total = len(segments)
    log.info("Synthesizing %d segments...", total)
    paths: list[Path] = []

    for i, segment in enumerate(segments):
        path = synthesize_segment(segment, run_dir)
        paths.append(path)
        if on_segment_done is not None:
            on_segment_done(i + 1, total)

    log.info("All %d segments synthesized for run [%s]", len(paths), run_id)
    return paths, run_dir


# ── Cleanup helpers ──────────────────────────────────────────────────────────


def cleanup_run(run_dir: Path) -> None:
    """Remove a run's temporary segment directory after assembly completes."""
    run_dir = Path(run_dir)
    if run_dir.exists():
        shutil.rmtree(run_dir)
        log.info("Cleaned up run directory: %s", run_dir)


def cleanup_stale_runs(base_dir: Path | None = None) -> None:
    """Remove orphaned run directories older than _MAX_RUN_AGE_SECONDS.

    Orphaned directories are left behind when a run crashes or the user
    disconnects mid-synthesis. Call this at app startup and periodically
    (e.g. hourly) to prevent unbounded disk growth.
    """
    base_dir = Path(base_dir or settings.segments_path)
    if not base_dir.exists():
        return

    now = time.time()
    for run_dir in base_dir.iterdir():
        if not run_dir.is_dir():
            continue
        age = now - run_dir.stat().st_mtime
        if age > _MAX_RUN_AGE_SECONDS:
            shutil.rmtree(run_dir)
            log.warning(
                "Removed stale run directory (%.0f mins old): %s",
                age / 60,
                run_dir,
            )
