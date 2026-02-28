"""Tests for the FastAPI endpoints."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


class TestHealthCheck:
    def test_health(self):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"


class TestUploadBlog:
    @patch("api.routes.add_chunks")
    @patch("api.routes.chunk_text")
    @patch("api.routes.normalize_text")
    def test_upload_raw_text(self, mock_normalize, mock_chunk, mock_add):
        from models.data import Chunk

        mock_normalize.return_value = "Normalized text content."
        mock_chunk.return_value = [Chunk(text="chunk1", index=0)]
        mock_add.return_value = "blog_abc123"

        response = client.post(
            "/api/v1/upload-blog",
            json={"text": "Some blog content here.", "title": "Test Blog"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ingested"
        assert "job_id" in data

    def test_upload_no_content(self):
        response = client.post("/api/v1/upload-blog", json={})
        assert response.status_code == 400

    @patch("api.routes.add_chunks")
    @patch("api.routes.chunk_text")
    @patch("api.routes.parse_markdown")
    def test_upload_markdown(self, mock_parse, mock_chunk, mock_add):
        from models.data import Chunk

        mock_parse.return_value = "Parsed markdown content."
        mock_chunk.return_value = [Chunk(text="chunk1", index=0)]
        mock_add.return_value = "blog_abc123"

        response = client.post(
            "/api/v1/upload-blog",
            json={"markdown": "# Title\n\nSome **bold** content."},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ingested"


class TestJobStatus:
    def test_nonexistent_job(self):
        response = client.get("/api/v1/job/nonexistent-id")
        assert response.status_code == 404

    def test_nonexistent_download(self):
        response = client.get("/api/v1/download/nonexistent-id")
        assert response.status_code == 404
