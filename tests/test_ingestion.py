"""Tests for the content ingestion module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from ingestion.chunker import chunk_text
from ingestion.parser import normalize_text, parse_markdown, segment_sentences


# ── Parser Tests ─────────────────────────────────────────────────────────────


class TestNormalizeText:
    def test_strips_extra_whitespace(self):
        result = normalize_text("  hello   world  ")
        assert result == "hello world"

    def test_collapses_newlines(self):
        result = normalize_text("hello\n\n\n\n\nworld")
        assert result == "hello\n\nworld"

    def test_unescapes_html_entities(self):
        result = normalize_text("Tom &amp; Jerry &lt;3")
        assert result == "Tom & Jerry <3"

    def test_empty_input(self):
        assert normalize_text("") == ""


class TestParseMarkdown:
    def test_removes_headers(self):
        result = parse_markdown("# Title\n\nSome content")
        assert "Title" in result
        assert "#" not in result

    def test_converts_links(self):
        result = parse_markdown("Check [this link](https://example.com)")
        assert "this link" in result
        assert "https://example.com" not in result

    def test_removes_images(self):
        result = parse_markdown("![alt text](image.png)\n\nParagraph")
        assert "alt text" not in result
        assert "Paragraph" in result

    def test_removes_code_blocks(self):
        result = parse_markdown("Text\n\n```python\nprint('hi')\n```\n\nMore text")
        assert "print" not in result
        assert "More text" in result

    def test_strips_bold_italic(self):
        result = parse_markdown("This is **bold** and *italic*")
        assert "bold" in result
        assert "italic" in result
        assert "*" not in result


class TestSentenceSegmentation:
    def test_basic_sentences(self):
        text = "Hello world. How are you? Fine thanks!"
        sentences = segment_sentences(text)
        assert len(sentences) >= 2

    def test_single_sentence(self):
        sentences = segment_sentences("Just one sentence.")
        assert len(sentences) == 1


# ── Chunker Tests ────────────────────────────────────────────────────────────


class TestChunker:
    def test_creates_chunks(self):
        text = "First paragraph about topic A.\n\n" * 30
        chunks = chunk_text(text, chunk_size=100, chunk_overlap=20)
        assert len(chunks) > 1

    def test_chunk_indices_sequential(self):
        text = ("This is a test paragraph with some content. " * 20 + "\n\n") * 10
        chunks = chunk_text(text, chunk_size=100, chunk_overlap=20)
        for i, chunk in enumerate(chunks):
            assert chunk.index == i

    def test_chunks_have_text(self):
        text = "Content here.\n\n" * 50
        chunks = chunk_text(text, chunk_size=100, chunk_overlap=20)
        for chunk in chunks:
            assert chunk.text.strip()

    def test_metadata_propagated(self):
        text = "Some content.\n\n" * 20
        chunks = chunk_text(text, chunk_size=100, metadata={"source": "test"})
        for chunk in chunks:
            assert chunk.metadata.get("source") == "test"

    def test_single_paragraph(self):
        text = "Short paragraph."
        chunks = chunk_text(text, chunk_size=100)
        assert len(chunks) == 1
        assert chunks[0].text == "Short paragraph."


# ── Scraper Tests (mocked) ──────────────────────────────────────────────────


class TestScraper:
    @patch("ingestion.scraper.Article")
    def test_scrape_with_newspaper(self, MockArticle):
        from ingestion.scraper import scrape_url

        mock_article = MagicMock()
        mock_article.title = "Test Title"
        mock_article.text = "This is the article body. " * 10
        mock_article.authors = ["Author A"]
        mock_article.publish_date = None
        MockArticle.return_value = mock_article

        result = scrape_url("https://example.com/test")

        assert result["title"] == "Test Title"
        assert len(result["text"]) > 50
        assert result["authors"] == ["Author A"]
