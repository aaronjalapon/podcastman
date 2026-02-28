"""Semantic chunking engine for blog content."""

from __future__ import annotations

from models.data import Chunk
from utils.helpers import count_tokens, get_logger

log = get_logger(__name__)

DEFAULT_CHUNK_SIZE = 800  # tokens
DEFAULT_CHUNK_OVERLAP = 100  # tokens


def chunk_text(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    metadata: dict | None = None,
) -> list[Chunk]:
    """Split text into overlapping semantic chunks.

    Attempts to split at paragraph boundaries, falling back to sentence
    boundaries, then word boundaries.
    """
    metadata = metadata or {}

    paragraphs = _split_paragraphs(text)
    chunks: list[Chunk] = []
    current_text = ""
    current_tokens = 0

    for para in paragraphs:
        para_tokens = count_tokens(para)

        if para_tokens > chunk_size:
            # Paragraph too large — flush current, then split paragraph
            if current_text.strip():
                chunks.append(_make_chunk(current_text.strip(), len(chunks), metadata))
                current_text = _get_overlap_text(current_text, chunk_overlap)
                current_tokens = count_tokens(current_text)

            sub_chunks = _split_large_paragraph(para, chunk_size, chunk_overlap, len(chunks), metadata)
            chunks.extend(sub_chunks)
            current_text = _get_overlap_text(chunks[-1].text, chunk_overlap) if chunks else ""
            current_tokens = count_tokens(current_text)
            continue

        if current_tokens + para_tokens > chunk_size and current_text.strip():
            chunks.append(_make_chunk(current_text.strip(), len(chunks), metadata))
            # Keep overlap from end of previous chunk
            current_text = _get_overlap_text(current_text, chunk_overlap)
            current_tokens = count_tokens(current_text)

        current_text += "\n\n" + para if current_text else para
        current_tokens += para_tokens

    # Flush remaining
    if current_text.strip():
        chunks.append(_make_chunk(current_text.strip(), len(chunks), metadata))

    log.info("Created %d chunks from %d tokens of text", len(chunks), count_tokens(text))
    return chunks


def _split_paragraphs(text: str) -> list[str]:
    """Split text into paragraphs."""
    paras = text.split("\n\n")
    return [p.strip() for p in paras if p.strip()]


def _split_large_paragraph(
    text: str,
    chunk_size: int,
    chunk_overlap: int,
    start_index: int,
    metadata: dict,
) -> list[Chunk]:
    """Split an oversized paragraph by sentences, then words."""
    import re

    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks: list[Chunk] = []
    current = ""
    current_tokens = 0

    for sent in sentences:
        sent_tokens = count_tokens(sent)
        if current_tokens + sent_tokens > chunk_size and current.strip():
            chunks.append(_make_chunk(current.strip(), start_index + len(chunks), metadata))
            current = _get_overlap_text(current, chunk_overlap)
            current_tokens = count_tokens(current)

        current += " " + sent if current else sent
        current_tokens += sent_tokens

    if current.strip():
        chunks.append(_make_chunk(current.strip(), start_index + len(chunks), metadata))

    return chunks


def _get_overlap_text(text: str, overlap_tokens: int) -> str:
    """Get the last N tokens worth of text for overlap."""
    words = text.split()
    # Approximate: ~1.3 tokens per word on average
    approx_words = int(overlap_tokens / 1.3)
    if approx_words >= len(words):
        return text
    return " ".join(words[-approx_words:])


def _make_chunk(text: str, index: int, metadata: dict) -> Chunk:
    """Create a Chunk with computed metadata."""
    return Chunk(
        text=text,
        index=index,
        metadata={
            **metadata,
            "token_count": count_tokens(text),
            "char_count": len(text),
        },
    )
