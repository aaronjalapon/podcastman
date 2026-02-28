"""Tests for TTS dialogue parsing."""

from __future__ import annotations

import pytest

from models.data import Speaker
from tts.dialogue_parser import parse_dialogue, parse_script, segments_to_script


SAMPLE_SCRIPT = """HOST_A: Welcome to the show! Today we're talking about AI.

HOST_B: That's right! It's a fascinating topic.

HOST_A: [pause] So basically, LLMs are trained on massive amounts of text data.

HOST_B: [excited] Oh, I love this stuff. Tell me more about how they work!

HOST_A: Sure! The key insight is the transformer architecture.

HOST_B: And it uses attention mechanisms, right?

HOST_A: Exactly. Thanks for listening, everyone!
"""


class TestDialogueParser:
    def test_parses_speakers(self):
        segments = parse_script(SAMPLE_SCRIPT)
        assert len(segments) >= 5

        # First segment should be HOST_A
        assert segments[0].speaker == Speaker.HOST_A

    def test_alternating_speakers(self):
        segments = parse_script(SAMPLE_SCRIPT)
        # Should have both speakers
        speakers = {s.speaker for s in segments}
        assert Speaker.HOST_A in speakers
        assert Speaker.HOST_B in speakers

    def test_extracts_cues(self):
        segments = parse_script(SAMPLE_SCRIPT)
        # Find the segment with [pause]
        pause_segs = [s for s in segments if "pause" in s.cues]
        assert len(pause_segs) >= 1

        # Find the segment with [excited]
        excited_segs = [s for s in segments if "excited" in s.cues]
        assert len(excited_segs) >= 1

    def test_removes_cues_from_text(self):
        segments = parse_script(SAMPLE_SCRIPT)
        for seg in segments:
            assert "[pause]" not in seg.text
            assert "[excited]" not in seg.text

    def test_sequential_indices(self):
        segments = parse_script(SAMPLE_SCRIPT)
        for i, seg in enumerate(segments):
            assert seg.index == i

    def test_empty_script(self):
        segments = parse_script("")
        assert segments == []

    def test_segments_have_text(self):
        segments = parse_script(SAMPLE_SCRIPT)
        for seg in segments:
            assert seg.text.strip()

    def test_roundtrip(self):
        """Parse and convert back — should preserve speaker/text structure."""
        segments = parse_script(SAMPLE_SCRIPT)
        reconstructed = segments_to_script(segments)
        assert "HOST_A:" in reconstructed
        assert "HOST_B:" in reconstructed

    def test_long_segment_splitting(self):
        """Very long speaking turn should be split."""
        long_text = "This is a sentence. " * 50  # ~1000 chars
        script = f"HOST_A: {long_text}"
        segments = parse_script(script)
        # Should produce multiple segments since text > 500 chars
        assert len(segments) >= 2
        # All should be HOST_A
        for seg in segments:
            assert seg.speaker == Speaker.HOST_A


class TestParseDialogue:
    """Tests for parse_dialogue() with natural speaker names."""

    def test_markdown_format(self):
        """Test parsing **Name:** markdown bold format."""
        script = """
**Mike:** Welcome to the show!
**Sarah:** Thanks for having me!
**Mike:** Let's dive in.
"""
        segments = parse_dialogue(script)
        assert len(segments) == 3
        assert segments[0].speaker == Speaker.HOST_A
        assert segments[0].text == "Welcome to the show!"
        assert segments[1].speaker == Speaker.HOST_B
        assert segments[1].text == "Thanks for having me!"
        assert segments[2].speaker == Speaker.HOST_A

    def test_plain_name_format(self):
        """Test parsing Name: plain format."""
        script = """
Mike: Welcome!
Sarah: Thanks!
"""
        segments = parse_dialogue(script)
        assert len(segments) == 2
        assert segments[0].speaker == Speaker.HOST_A
        assert segments[1].speaker == Speaker.HOST_B

    def test_legacy_host_format(self):
        """Test backward compatibility with HOST_A/HOST_B format."""
        script = """
HOST_A: Welcome!
HOST_B: Thanks!
"""
        segments = parse_dialogue(script)
        assert len(segments) == 2
        assert segments[0].speaker == Speaker.HOST_A
        assert segments[1].speaker == Speaker.HOST_B

    def test_custom_name_mapping(self):
        """Test custom speaker name mapping."""
        script = """
**Sam:** Hello!
**Taylor:** Hey there!
"""
        name_map = {
            "Sam": Speaker.HOST_A,
            "Taylor": Speaker.HOST_B,
        }
        segments = parse_dialogue(script, name_map=name_map)
        assert len(segments) == 2
        assert segments[0].speaker == Speaker.HOST_A
        assert segments[1].speaker == Speaker.HOST_B

    def test_unknown_speaker_skipped(self):
        """Test that unknown speakers are skipped with warning."""
        script = """
**Mike:** Hello!
**Unknown:** This should be skipped.
**Sarah:** Hey!
"""
        segments = parse_dialogue(script)
        # Only Mike and Sarah should be parsed
        assert len(segments) == 2
        assert segments[0].speaker == Speaker.HOST_A
        assert segments[1].speaker == Speaker.HOST_B

    def test_extracts_cues_from_dialogue(self):
        """Test cue extraction works with dialogue format."""
        script = """
**Mike:** [pause] This is important.
**Sarah:** [excited] I agree!
"""
        segments = parse_dialogue(script)
        assert len(segments) == 2
        assert "pause" in segments[0].cues
        assert "excited" in segments[1].cues
        assert "[pause]" not in segments[0].text
        assert "[excited]" not in segments[1].text

    def test_long_segment_splitting_dialogue(self):
        """Test long segments are split with dialogue format."""
        long_text = "This is a sentence. " * 50  # ~1000 chars
        script = f"**Mike:** {long_text}"
        segments = parse_dialogue(script)
        # Should produce multiple segments
        assert len(segments) >= 2
        # All should be HOST_A
        for seg in segments:
            assert seg.speaker == Speaker.HOST_A

    def test_sequential_indices_dialogue(self):
        """Test segments have sequential indices."""
        script = """
**Mike:** First.
**Sarah:** Second.
**Mike:** Third.
"""
        segments = parse_dialogue(script)
        for i, seg in enumerate(segments):
            assert seg.index == i

    def test_empty_dialogue(self):
        """Test empty script returns empty list."""
        segments = parse_dialogue("")
        assert segments == []

    def test_mixed_format(self):
        """Test mixed markdown and plain format."""
        script = """
**Mike:** Opening with markdown.
Sarah: Responding without markdown.
**Mike:** Back to markdown.
"""
        segments = parse_dialogue(script)
        assert len(segments) == 3
        assert segments[0].speaker == Speaker.HOST_A
        assert segments[1].speaker == Speaker.HOST_B
        assert segments[2].speaker == Speaker.HOST_A
