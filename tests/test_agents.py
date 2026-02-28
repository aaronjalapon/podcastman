"""Tests for the multi-agent script pipeline."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


SAMPLE_SCRIPT = """HOST_A: Welcome to the show! Today we're talking about AI.

HOST_B: That's right! It's a fascinating topic. So what's the big deal with AI anyway?

HOST_A: Well, the article we're covering today dives deep into how large language models work.

HOST_B: [excited] Oh, I love this stuff. Tell me more!

HOST_A: [pause] So basically, LLMs are trained on massive amounts of text data.

HOST_B: And they learn patterns from all that data, right?

HOST_A: Exactly. Thanks for listening, everyone!
"""


class TestScriptGenerator:
    @patch("agents.script_generator.litellm")
    @patch("agents.script_generator.retrieve_all")
    def test_generates_script(self, mock_retrieve, mock_litellm):
        from agents.script_generator import generate_script
        from models.data import Chunk

        mock_retrieve.return_value = [
            Chunk(text="AI is transforming industries.", index=0)
        ]

        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content=SAMPLE_SCRIPT))]
        mock_litellm.completion.return_value = mock_response

        result = generate_script("AI Article", "Full article text...", "test_collection")

        assert "HOST_A:" in result
        assert "HOST_B:" in result
        mock_litellm.completion.assert_called_once()


class TestAccuracyAgent:
    @patch("agents.accuracy_agent.litellm")
    @patch("agents.accuracy_agent.retrieve_all")
    def test_accuracy_check(self, mock_retrieve, mock_litellm):
        from agents.accuracy_agent import check_accuracy
        from models.data import Chunk

        mock_retrieve.return_value = [
            Chunk(text="Original source content.", index=0)
        ]

        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content=SAMPLE_SCRIPT))]
        mock_litellm.completion.return_value = mock_response

        result = check_accuracy(SAMPLE_SCRIPT, "test_collection")
        assert "HOST_A:" in result


class TestStorytellingAgent:
    @patch("agents.storytelling_agent.litellm")
    def test_enhance_storytelling(self, mock_litellm):
        from agents.storytelling_agent import enhance_storytelling

        enhanced = SAMPLE_SCRIPT + "\nHOST_A: [thoughtful] Let me think about that..."
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content=enhanced))]
        mock_litellm.completion.return_value = mock_response

        result = enhance_storytelling(SAMPLE_SCRIPT)
        assert "HOST_A:" in result


class TestEngagementAgent:
    @patch("agents.engagement_agent.litellm")
    def test_optimize_engagement(self, mock_litellm):
        from agents.engagement_agent import optimize_engagement

        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content=SAMPLE_SCRIPT))]
        mock_litellm.completion.return_value = mock_response

        result = optimize_engagement(SAMPLE_SCRIPT)
        assert "HOST_A:" in result


class TestGraphPipeline:
    @patch("agents.graph.optimize_engagement")
    @patch("agents.graph.enhance_storytelling")
    @patch("agents.graph.check_accuracy")
    @patch("agents.graph.generate_script")
    def test_full_pipeline(
        self, mock_gen, mock_acc, mock_story, mock_engage
    ):
        from agents.graph import run_pipeline

        mock_gen.return_value = SAMPLE_SCRIPT
        mock_acc.return_value = SAMPLE_SCRIPT
        mock_story.return_value = SAMPLE_SCRIPT
        mock_engage.return_value = SAMPLE_SCRIPT

        result = run_pipeline("Test Title", "Test content", "test_collection")

        assert result["final_script"] == SAMPLE_SCRIPT
        assert result["raw_script"] == SAMPLE_SCRIPT
        assert result["errors"] == []
        mock_gen.assert_called_once()
        mock_acc.assert_called_once()
        mock_story.assert_called_once()
        mock_engage.assert_called_once()
