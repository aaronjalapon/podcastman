"""RAG retriever: query → relevant chunks from the vector store."""

from __future__ import annotations

from models.data import Chunk
from rag.embeddings import embed_query
from rag.vectorstore import get_or_create_collection
from utils.helpers import get_logger

log = get_logger(__name__)


def retrieve(
    query: str,
    collection_name: str,
    top_k: int = 5,
) -> list[Chunk]:
    """Retrieve the most relevant chunks for a query.

    Args:
        query: The search query.
        collection_name: ChromaDB collection to search.
        top_k: Number of results to return.

    Returns:
        List of Chunk objects ranked by relevance.
    """
    collection = get_or_create_collection(collection_name)

    if collection.count() == 0:
        log.warning("Collection '%s' is empty", collection_name)
        return []

    query_embedding = embed_query(query)

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(top_k, collection.count()),
        include=["documents", "metadatas", "distances"],
    )

    chunks: list[Chunk] = []
    if results["documents"] and results["documents"][0]:
        for i, doc in enumerate(results["documents"][0]):
            meta = results["metadatas"][0][i] if results["metadatas"] else {}
            distance = results["distances"][0][i] if results["distances"] else 0.0
            chunks.append(
                Chunk(
                    text=doc,
                    index=int(meta.get("index", i)),
                    metadata={**meta, "distance": distance},
                )
            )

    log.info(
        "Retrieved %d chunks for query '%s' from '%s'",
        len(chunks),
        query[:60],
        collection_name,
    )
    return chunks


def retrieve_all(collection_name: str) -> list[Chunk]:
    """Retrieve all chunks from a collection."""
    collection = get_or_create_collection(collection_name)
    count = collection.count()

    if count == 0:
        return []

    results = collection.get(include=["documents", "metadatas"])
    chunks: list[Chunk] = []
    for i, doc in enumerate(results["documents"]):
        meta = results["metadatas"][i] if results["metadatas"] else {}
        chunks.append(
            Chunk(
                text=doc,
                index=int(meta.get("index", i)),
                metadata=meta,
            )
        )

    chunks.sort(key=lambda c: c.index)
    return chunks
