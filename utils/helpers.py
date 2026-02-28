"""Utility helpers: logging, file I/O, token counting."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import tiktoken

from config.settings import settings


def get_logger(name: str) -> logging.Logger:
    """Return a configured logger."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter("%(asctime)s | %(name)-20s | %(levelname)-7s | %(message)s")
        )
        logger.addHandler(handler)
    logger.setLevel(settings.log_level)
    return logger


def count_tokens(text: str, model: str = "gpt-4o") -> int:
    """Count tokens in text using tiktoken."""
    try:
        enc = tiktoken.encoding_for_model(model)
    except KeyError:
        enc = tiktoken.get_encoding("cl100k_base")
    return len(enc.encode(text))


def write_text(path: Path | str, content: str) -> Path:
    """Write text to a file, creating parent dirs."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


def read_text(path: Path | str) -> str:
    """Read text from a file."""
    return Path(path).read_text(encoding="utf-8")
