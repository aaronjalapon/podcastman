"""ChromaDB vector store management."""

from __future__ import annotations

import chromadb

from config.settings import settings
from models.data import BlogContent, Chunk
from rag.embeddings import embed_texts
from utils.helpers import get_logger

log = get_logger(__name__)

_client: chromadb.ClientAPI | None = None


def get_client() -> chromadb.ClientAPI:
    """Get or create the persistent ChromaDB client."""
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
        log.info("ChromaDB client initialized at %s", settings.chroma_persist_dir)
    return _client


def get_or_create_collection(name: str) -> chromadb.Collection:
    """Get or create a ChromaDB collection."""
    client = get_client()
    return client.get_or_create_collection(
        name=name,
        metadata={"hnsw:space": "cosine"},
    )


def add_chunks(blog: BlogContent) -> str:
    """Add blog content chunks to the vector store.

    Returns the collection name used.
    """
    collection_name = f"blog_{blog.content_hash}"
    collection = get_or_create_collection(collection_name)

    # Skip if already populated
    if collection.count() > 0:
        log.info("Collection '%s' already has %d items, skipping", collection_name, collection.count())
        return collection_name

    texts = [chunk.text for chunk in blog.chunks]
    ids = [chunk.id for chunk in blog.chunks]
    metadatas = [
        {
            "index": chunk.index,
            "source_url": blog.source_url,
            "title": blog.title,
            **{k: str(v) for k, v in chunk.metadata.items()},
        }
        for chunk in blog.chunks
    ]

    # Generate embeddings
    embeddings = embed_texts(texts)

    # Add to ChromaDB
    collection.add(
        ids=ids,
        documents=texts,
        embeddings=embeddings,
        metadatas=metadatas,
    )

    log.info("Added %d chunks to collection '%s'", len(texts), collection_name)
    return collection_name


def delete_collection(name: str) -> None:
    """Delete a ChromaDB collection."""
    client = get_client()
    try:
        client.delete_collection(name)
        log.info("Deleted collection '%s'", name)
    except ValueError:
        log.warning("Collection '%s' not found for deletion", name)
