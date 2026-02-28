"""Audio post-processing: normalize, denoise, trim silence."""

from __future__ import annotations

from pathlib import Path

from pydub import AudioSegment
from pydub.effects import normalize

from utils.helpers import get_logger

log = get_logger(__name__)


def postprocess_segment(audio_path: Path) -> AudioSegment:
    """Post-process a single audio segment.

    - Load WAV
    - Normalize volume
    - Trim leading/trailing silence
    - Apply noise reduction (optional)

    Returns a pydub AudioSegment.
    """
    log.debug("Post-processing: %s", audio_path)

    audio = AudioSegment.from_file(str(audio_path))

    # Normalize volume
    audio = normalize(audio)

    # Trim leading/trailing silence (threshold: -40 dBFS)
    audio = _trim_silence(audio)

    return audio


def postprocess_all(audio_paths: list[Path]) -> list[AudioSegment]:
    """Post-process all audio segments."""
    log.info("Post-processing %d audio segments", len(audio_paths))
    segments = []
    for path in audio_paths:
        seg = postprocess_segment(path)
        segments.append(seg)
    log.info("Post-processing complete")
    return segments


def apply_noise_reduction(audio_path: Path, output_path: Path | None = None) -> Path:
    """Apply noise reduction to an audio file using noisereduce.

    This is an optional step — useful for cleaning up TTS artifacts.
    """
    import numpy as np
    import noisereduce as nr
    import scipy.io.wavfile as wavfile

    output_path = output_path or audio_path

    rate, data = wavfile.read(str(audio_path))

    # Convert to float for noisereduce
    data_float = data.astype(np.float32)

    # Apply stationary noise reduction
    reduced = nr.reduce_noise(
        y=data_float,
        sr=rate,
        stationary=True,
        prop_decrease=0.75,
    )

    # Convert back to int16
    reduced_int = np.clip(reduced, -32768, 32767).astype(np.int16)
    wavfile.write(str(output_path), rate, reduced_int)

    log.info("Noise reduction applied: %s", output_path)
    return output_path


def _trim_silence(
    audio: AudioSegment,
    silence_thresh: int = -40,
    chunk_size: int = 50,
) -> AudioSegment:
    """Trim silence from beginning and end of an AudioSegment."""
    # Find start of non-silence
    start = 0
    while start < len(audio) - chunk_size:
        chunk = audio[start : start + chunk_size]
        if chunk.dBFS > silence_thresh:
            break
        start += chunk_size

    # Find end of non-silence
    end = len(audio)
    while end > chunk_size:
        chunk = audio[end - chunk_size : end]
        if chunk.dBFS > silence_thresh:
            break
        end -= chunk_size

    if start >= end:
        return audio  # Don't trim to nothing

    return audio[start:end]
