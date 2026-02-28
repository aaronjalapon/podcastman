"""Embedding model wrapper using LiteLLM."""

from __future__ import annotations

import os

import litellm

from config.settings import settings
from utils.helpers import get_logger

log = get_logger(__name__)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for a list of texts via LiteLLM.

    Supports any embedding model LiteLLM supports (OpenAI, Cohere, etc.).
    """
    if not texts:
        return []

    log.info("Generating embeddings for %d texts using %s", len(texts), settings.embedding_model)

    # Prepare API key based on provider
    api_key = None
    if settings.embedding_model.startswith("jina_ai/"):
        # Jina AI requires JINA_API_KEY environment variable
        if settings.embedding_api_key:
            os.environ["JINA_API_KEY"] = settings.embedding_api_key
            api_key = settings.embedding_api_key
            log.debug("Set JINA_API_KEY for Jina AI")
        else:
            log.warning("JINA_API_KEY not found - check .env for EMBEDDING_API_KEY")
    elif settings.embedding_api_key:
        # For other providers (OpenAI, Cohere, etc.)
        api_key = settings.embedding_api_key

    response = litellm.embedding(
        model=settings.embedding_model,
        input=texts,
        api_key=api_key,
    )

    embeddings = [item["embedding"] for item in response.data]
    log.info("Generated %d embeddings (dim=%d)", len(embeddings), len(embeddings[0]))
    return embeddings


def embed_query(query: str) -> list[float]:
    """Generate embedding for a single query string."""
    result = embed_texts([query])
    return result[0]
