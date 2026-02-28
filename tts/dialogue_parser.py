"""Parse final podcast script into per-speaker segments."""

from __future__ import annotations

import re

from models.data import Speaker, SpeakerSegment
from utils.helpers import get_logger

log = get_logger(__name__)

# Pattern: "HOST_A:" or "HOST_B:" at the start of a line (with optional cues)
_SPEAKER_PATTERN = re.compile(
    r"^(HOST_[AB])\s*:\s*(.+?)$",
    re.MULTILINE | re.DOTALL,
)

# Pattern: "**Name:**" or "Name:" at the start of a line (markdown dialogue format)
_DIALOGUE_PATTERN = re.compile(
    r"^\*{0,2}(\w+)\*{0,2}\s*:\s*",
    re.MULTILINE,
)

# Pattern: [cue] markers in text
_CUE_PATTERN = re.compile(r"\[(\w+(?:\s+\w+)?)\]")

# Maximum characters per segment before splitting
_MAX_SEGMENT_CHARS = 500


def parse_script(script: str) -> list[SpeakerSegment]:
    """Parse a HOST_A/HOST_B dialogue script into SpeakerSegment list.

    Handles multi-line turns, extracts cue markers, and splits long segments.
    """
    segments: list[SpeakerSegment] = []

    # Split script into speaker turns
    turns = _split_into_turns(script)

    for i, (speaker_str, text) in enumerate(turns):
        speaker = Speaker.HOST_A if speaker_str == "HOST_A" else Speaker.HOST_B

        # Extract cues from text
        cues = _CUE_PATTERN.findall(text)
        # Remove cue markers from spoken text
        clean_text = _CUE_PATTERN.sub("", text).strip()
        # Collapse extra whitespace left by cue removal
        clean_text = re.sub(r"\s{2,}", " ", clean_text)

        if not clean_text:
            continue

        # Split long segments
        if len(clean_text) > _MAX_SEGMENT_CHARS:
            sub_texts = _split_long_segment(clean_text)
            for j, sub in enumerate(sub_texts):
                segments.append(
                    SpeakerSegment(
                        speaker=speaker,
                        text=sub,
                        index=len(segments),
                        cues=cues if j == 0 else [],
                    )
                )
        else:
            segments.append(
                SpeakerSegment(
                    speaker=speaker,
                    text=clean_text,
                    index=len(segments),
                    cues=cues,
                )
            )

    log.info("Parsed %d speaker segments from script", len(segments))
    return segments


def parse_dialogue(
    script: str,
    name_map: dict[str, Speaker] | None = None,
) -> list[SpeakerSegment]:
    """Parse a dialogue script with natural speaker names into SpeakerSegment list.

    Supports formats:
    - **Mike:** Welcome to the show!  (markdown bold)
    - Mike: Welcome to the show!      (plain)
    - HOST_A: Welcome to the show!    (legacy)

    Args:
        script: Multi-line dialogue script
        name_map: Optional mapping from speaker names to Speaker enum.
                  Defaults to {"Mike": HOST_A, "Sarah": HOST_B}

    Returns:
        List of SpeakerSegment objects compatible with TTS pipeline.

    Note:
        The segment.speaker will be a Speaker enum (HOST_A/HOST_B).
        To get the display name, use: get_voice(segment.speaker).name
    """
    if name_map is None:
        # Build default mapping dynamically from voice_config personas
        from tts.voice_config import HOST_A as VOICE_A, HOST_B as VOICE_B

        name_map = {
            VOICE_A.name: Speaker.HOST_A,
            VOICE_B.name: Speaker.HOST_B,
            "HOST_A": Speaker.HOST_A,
            "HOST_B": Speaker.HOST_B,
        }

    segments: list[SpeakerSegment] = []

    # Split script into speaker turns using dialogue pattern
    turns = _split_into_turns(script, pattern=_DIALOGUE_PATTERN)

    for i, (speaker_name, text) in enumerate(turns):
        # Map speaker name to Speaker enum
        speaker = name_map.get(speaker_name)
        if speaker is None:
            log.warning("Unknown speaker '%s', skipping segment", speaker_name)
            continue

        # Extract cues from text
        cues = _CUE_PATTERN.findall(text)
        # Remove cue markers from spoken text
        clean_text = _CUE_PATTERN.sub("", text).strip()
        # Collapse extra whitespace left by cue removal
        clean_text = re.sub(r"\s{2,}", " ", clean_text)

        if not clean_text:
            continue

        # Split long segments
        if len(clean_text) > _MAX_SEGMENT_CHARS:
            sub_texts = _split_long_segment(clean_text)
            for j, sub in enumerate(sub_texts):
                segments.append(
                    SpeakerSegment(
                        speaker=speaker,
                        text=sub,
                        index=len(segments),
                        cues=cues if j == 0 else [],
                    )
                )
        else:
            segments.append(
                SpeakerSegment(
                    speaker=speaker,
                    text=clean_text,
                    index=len(segments),
                    cues=cues,
                )
            )

    log.info("Parsed %d speaker segments from dialogue", len(segments))
    return segments


def _split_into_turns(
    script: str,
    pattern: re.Pattern | None = None,
) -> list[tuple[str, str]]:
    """Split script text into (speaker, text) tuples.

    Args:
        script: The script text to parse
        pattern: Regex pattern to use. Defaults to HOST_A/HOST_B pattern

    Returns:
        List of (speaker_identifier, text) tuples
    """
    if pattern is None:
        pattern = re.compile(r"^(HOST_[AB])\s*:", re.MULTILINE)

    turns: list[tuple[str, str]] = []

    # Find all speaker markers and their positions
    markers = list(re.finditer(pattern, script))

    for i, match in enumerate(markers):
        speaker = match.group(1)
        start = match.end()
        end = markers[i + 1].start() if i + 1 < len(markers) else len(script)
        text = script[start:end].strip()
        
        # Remove any leading ** that might have been left from markdown bold
        text = text.lstrip("*").strip()
        
        if text:
            turns.append((speaker, text))

    return turns


def _split_long_segment(text: str) -> list[str]:
    """Split a long text segment at sentence boundaries."""
    sentences = re.split(r"(?<=[.!?])\s+", text)
    parts: list[str] = []
    current = ""

    for sent in sentences:
        if len(current) + len(sent) > _MAX_SEGMENT_CHARS and current:
            parts.append(current.strip())
            current = sent
        else:
            current = f"{current} {sent}" if current else sent

    if current.strip():
        parts.append(current.strip())

    return parts


def segments_to_script(segments: list[SpeakerSegment]) -> str:
    """Convert segments back to script text format (for debugging)."""
    lines: list[str] = []
    for seg in segments:
        cues_str = " ".join(f"[{c}]" for c in seg.cues)
        prefix = f"{cues_str} " if cues_str else ""
        lines.append(f"{seg.speaker.value}: {prefix}{seg.text}")
    return "\n\n".join(lines)
