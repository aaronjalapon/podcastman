"""Tests for the RAG knowledge base."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from models.data import BlogContent, Chunk


class TestEmbeddings:
    @patch("rag.embeddings.litellm")
    def test_embed_texts(self, mock_litellm):
        from rag.embeddings import embed_texts

        mock_response = type("R", (), {
            "data": [{"embedding": [0.1, 0.2, 0.3]} for _ in range(3)]
        })()
        mock_litellm.embedding.return_value = mock_response

        result = embed_texts(["text1", "text2", "text3"])
        assert len(result) == 3
        assert len(result[0]) == 3

    @patch("rag.embeddings.litellm")
    def test_embed_empty_list(self, mock_litellm):
        from rag.embeddings import embed_texts

        result = embed_texts([])
        assert result == []
        mock_litellm.embedding.assert_not_called()


class TestVectorStore:
    @patch("rag.vectorstore.embed_texts")
    def test_add_chunks(self, mock_embed):
        from rag.vectorstore import add_chunks, delete_collection, get_client

        mock_embed.return_value = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]

        blog = BlogContent(
            title="Test Blog",
            text="Full text here",
            chunks=[
                Chunk(text="First chunk of text", index=0),
                Chunk(text="Second chunk of text", index=1),
            ],
            source_url="https://example.com",
        )

        collection_name = add_chunks(blog)
        assert collection_name.startswith("blog_")

        # Clean up
        delete_collection(collection_name)


class TestRetriever:
    @patch("rag.retriever.embed_query")
    def test_retrieve_from_empty_collection(self, mock_embed):
        from rag.retriever import retrieve

        mock_embed.return_value = [0.1, 0.2, 0.3]

        # Use a non-existent collection name
        results = retrieve("test query", "nonexistent_collection_xyz")
        assert results == []
