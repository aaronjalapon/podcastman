"""Coqui XTTS v2 voice synthesis engine."""

from __future__ import annotations

import os
import shutil
import time
import uuid
import warnings
from pathlib import Path

import numpy as np
import scipy.io.wavfile as wavfile

from config.settings import settings
from models.data import Speaker, SpeakerSegment, TTSUnavailableError
from tts.voice_config import get_voice
from utils.helpers import get_logger

# Suppress PyTorch FutureWarnings about weights_only (TTS 0.22.0 uses trusted models)
warnings.filterwarnings("ignore", category=FutureWarning, module="torch")
warnings.filterwarnings("ignore", category=FutureWarning, module="TTS")

log = get_logger(__name__)

# Maximum age (seconds) before an orphaned run directory is considered stale
_MAX_RUN_AGE_SECONDS = 60 * 60  # 1 hour

# ---------------------------------------------------------------------------
# TTS availability detection
# ---------------------------------------------------------------------------
# Set DISABLE_TTS=1 in env / Streamlit secrets to skip TTS entirely.
# Auto-detection also catches ImportError (missing deps) and MemoryError.
_TTS_FORCE_DISABLED = os.environ.get("DISABLE_TTS", "").lower() in ("1", "true", "yes")
_tts_available: bool = not _TTS_FORCE_DISABLED
_tts_unavailable_reason: str = (
    "TTS explicitly disabled via DISABLE_TTS env var" if _TTS_FORCE_DISABLED else ""
)

# Lazy-loaded TTS model
_tts_model = None


def is_tts_available() -> bool:
    """Return whether TTS synthesis is available on this deployment."""
    return _tts_available


def _require_tts() -> None:
    """Raise TTSUnavailableError if TTS is not usable."""
    if not _tts_available:
        raise TTSUnavailableError(_tts_unavailable_reason)


def _get_model():
    """Lazy-load the Coqui TTS model (heavy, ~1.8 GB).

    If the model cannot be loaded (missing deps, OOM, etc.) the global
    ``_tts_available`` flag is set to ``False`` so subsequent calls fail
    fast with :class:`TTSUnavailableError`.
    """
    global _tts_model, _tts_available, _tts_unavailable_reason

    _require_tts()  # fast-fail if already known-unavailable

    if _tts_model is None:
        try:
            log.info("Loading TTS model: %s (this may take a moment)...", settings.coqui_model_name)

            # Add safe globals for PyTorch 2.6+ security
            # Coqui TTS is a trusted source, so we allowlist its config/model classes
            import torch
            safe_globals_list = []
            try:
                from TTS.tts.configs.xtts_config import XttsConfig
                safe_globals_list.append(XttsConfig)
            except ImportError:
                pass
            try:
                from TTS.tts.models.xtts import XttsAudioConfig, XttsArgs
                safe_globals_list.extend([XttsAudioConfig, XttsArgs])
            except ImportError:
                pass
            try:
                from TTS.config.shared_configs import BaseDatasetConfig
                safe_globals_list.append(BaseDatasetConfig)
            except ImportError:
                pass

            if safe_globals_list:
                torch.serialization.add_safe_globals(safe_globals_list)

            from TTS.api import TTS

            _tts_model = TTS(model_name=settings.coqui_model_name)
            log.info("TTS model loaded successfully")

        except ImportError as exc:
            reason = f"TTS dependencies not installed: {exc}"
            log.warning(reason)
            _tts_available = False
            _tts_unavailable_reason = reason
            raise TTSUnavailableError(reason) from exc

        except MemoryError as exc:
            reason = "Not enough memory to load the TTS model (needs ~2 GB)"
            log.warning(reason)
            _tts_available = False
            _tts_unavailable_reason = reason
            raise TTSUnavailableError(reason) from exc

        except Exception as exc:
            reason = f"Failed to load TTS model: {exc}"
            log.warning(reason)
            _tts_available = False
            _tts_unavailable_reason = reason
            raise TTSUnavailableError(reason) from exc

    return _tts_model


def synthesize_segment(
    segment: SpeakerSegment,
    output_dir: Path | None = None,
) -> Path:
    """Synthesize a single speaker segment to a WAV file.

    Args:
        segment: The speaker segment to synthesize.
        output_dir: Directory for output files. Defaults to settings.segments_path.

    Returns:
        Path to the generated WAV file.

    Raises:
        TTSUnavailableError: If TTS is disabled or could not be loaded.
    """
    _require_tts()

    output_dir = output_dir or settings.segments_path
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    voice = get_voice(segment.speaker)
    output_path = output_dir / f"segment_{segment.index:04d}_{segment.speaker.value}.wav"

    log.info(
        "Synthesizing segment %d (%s, %d chars): %.50s...",
        segment.index,
        voice.name,
        len(segment.text),
        segment.text,
    )

    tts = _get_model()

    # XTTS v2 requires speaker_wav for voice cloning
    if not voice.reference_exists:
        raise FileNotFoundError(
            f"Voice reference audio not found for {voice.name} at {voice.reference_audio}\n"
            f"Please add a 6-10 second WAV file of clear speech to: {voice.reference_audio}\n"
            f"XTTS v2 requires reference audio for voice cloning."
        )

    # Synthesize with voice cloning from reference audio
    tts.tts_to_file(
        text=segment.text,
        file_path=str(output_path),
        speaker_wav=str(voice.reference_audio),
        language=voice.language,
    )

    log.info("Segment %d saved to %s", segment.index, output_path)
    return output_path


def synthesize_all(
    segments: list[SpeakerSegment],
    output_dir: Path | None = None,
    on_segment_done: "Callable[[int, int], None] | None" = None,
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

    Raises:
        TTSUnavailableError: If TTS is disabled or could not be loaded.
    """
    _require_tts()

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


def generate_silence(duration_ms: int, sample_rate: int = 22050) -> Path:
    """Generate a silent WAV file of the specified duration.

    Used for inserting pauses between speaker turns.
    """
    output_dir = Path(settings.segments_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / f"silence_{duration_ms}ms.wav"
    if output_path.exists():
        return output_path

    num_samples = int(sample_rate * duration_ms / 1000)
    silence = np.zeros(num_samples, dtype=np.int16)
    wavfile.write(str(output_path), sample_rate, silence)

    return output_path
