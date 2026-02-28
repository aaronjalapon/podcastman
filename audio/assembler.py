"""Audio assembler: merge segments into final podcast episode."""

from __future__ import annotations

from pathlib import Path

from pydub import AudioSegment

from config.settings import settings
from models.data import SpeakerSegment
from utils.helpers import get_logger

log = get_logger(__name__)


def assemble_podcast(
    processed_segments: list[AudioSegment],
    speaker_segments: list[SpeakerSegment],
    output_path: Path | None = None,
    pause_ms: int | None = None,
) -> Path:
    """Assemble processed audio segments into a final podcast file.

    - Inserts pauses between different speakers.
    - Handles [pause] cues with longer silence.
    - Adds optional intro/outro music.
    - Exports as MP3.

    Args:
        processed_segments: Post-processed audio segments (from postprocess_all).
        speaker_segments: Corresponding SpeakerSegment metadata.
        output_path: Final output file path. Defaults to output/audio/podcast_final.mp3.
        pause_ms: Pause duration between speakers in ms. Defaults from settings.

    Returns:
        Path to the final MP3 file.
    """
    output_path = output_path or (settings.audio_path / "podcast_final.mp3")
    pause_ms = pause_ms or settings.pause_between_speakers_ms

    log.info("Assembling %d segments into podcast", len(processed_segments))

    # Start with empty audio
    podcast = AudioSegment.empty()

    # Add intro if configured
    intro = _load_optional_audio(settings.intro_audio)
    if intro:
        podcast += intro
        podcast += AudioSegment.silent(duration=500)
        log.info("Added intro music")

    # Assemble speaker segments with pauses
    prev_speaker = None
    for i, (audio, meta) in enumerate(zip(processed_segments, speaker_segments)):
        # Add pause between different speakers
        if prev_speaker is not None and meta.speaker != prev_speaker:
            podcast += AudioSegment.silent(duration=pause_ms)

        # Handle [pause] cue with extra silence
        if "pause" in meta.cues:
            podcast += AudioSegment.silent(duration=800)

        podcast += audio
        prev_speaker = meta.speaker

    # Add outro if configured
    outro = _load_optional_audio(settings.outro_audio)
    if outro:
        podcast += AudioSegment.silent(duration=500)
        podcast += outro
        log.info("Added outro music")

    # Export
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if output_path.suffix.lower() == ".mp3":
        podcast.export(str(output_path), format="mp3", bitrate="192k")
    else:
        podcast.export(str(output_path), format="wav")

    duration_s = len(podcast) / 1000
    log.info(
        "Podcast assembled: %s (%.1f seconds / %.1f minutes)",
        output_path,
        duration_s,
        duration_s / 60,
    )
    return output_path


def _load_optional_audio(path_str: str) -> AudioSegment | None:
    """Load an optional audio file (intro/outro). Returns None if not found."""
    if not path_str:
        return None

    path = Path(path_str)
    if not path.exists():
        log.debug("Optional audio not found: %s", path)
        return None

    try:
        return AudioSegment.from_file(str(path))
    except Exception as e:
        log.warning("Failed to load audio %s: %s", path, e)
        return None
