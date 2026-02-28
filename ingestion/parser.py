"""Text normalization for raw text and markdown input."""

from __future__ import annotations

import re

from utils.helpers import get_logger

log = get_logger(__name__)


def normalize_text(text: str) -> str:
    """Clean and normalize raw text content."""
    # Remove HTML entities
    text = _strip_html_entities(text)
    # Collapse excessive whitespace
    text = re.sub(r"[ \t]+", " ", text)
    # Normalize line breaks
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Strip leading/trailing whitespace per line
    lines = [line.strip() for line in text.splitlines()]
    text = "\n".join(lines)
    return text.strip()


def parse_markdown(markdown: str) -> str:
    """Convert markdown to plain text suitable for processing."""
    text = markdown

    # Remove images ![alt](url)
    text = re.sub(r"!\[.*?\]\(.*?\)", "", text)

    # Convert links [text](url) → text
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)

    # Remove markdown headers but keep text
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)

    # Remove bold/italic markers
    text = re.sub(r"\*{1,3}([^*]+)\*{1,3}", r"\1", text)
    text = re.sub(r"_{1,3}([^_]+)_{1,3}", r"\1", text)

    # Remove code blocks
    text = re.sub(r"```[\s\S]*?```", "", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)

    # Remove blockquotes
    text = re.sub(r"^>\s?", "", text, flags=re.MULTILINE)

    # Remove horizontal rules
    text = re.sub(r"^[-*_]{3,}\s*$", "", text, flags=re.MULTILINE)

    # Remove list markers but keep text
    text = re.sub(r"^[\s]*[-*+]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^[\s]*\d+\.\s+", "", text, flags=re.MULTILINE)

    return normalize_text(text)


def segment_sentences(text: str) -> list[str]:
    """Split text into sentences."""
    try:
        import nltk

        try:
            sentences = nltk.sent_tokenize(text)
        except LookupError:
            nltk.download("punkt_tab", quiet=True)
            sentences = nltk.sent_tokenize(text)
        return sentences
    except Exception:
        # Fallback regex-based sentence splitting
        log.warning("NLTK unavailable, using regex sentence splitting")
        return _regex_sentence_split(text)


def _regex_sentence_split(text: str) -> list[str]:
    """Simple regex-based sentence splitter."""
    # Split on sentence-ending punctuation followed by space + capital
    sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z])", text)
    return [s.strip() for s in sentences if s.strip()]


def _strip_html_entities(text: str) -> str:
    """Remove common HTML entities."""
    import html

    return html.unescape(text)
