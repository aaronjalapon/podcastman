"""HTTP client for the podcastman FastAPI backend."""
from __future__ import annotations

import requests

API_BASE = "http://localhost:8000/api/v1"


def _post(path: str, payload: dict) -> dict:
    resp = requests.post(f"{API_BASE}{path}", json=payload, timeout=120)
    resp.raise_for_status()
    return resp.json()


def _get(path: str) -> requests.Response:
    resp = requests.get(f"{API_BASE}{path}", timeout=30)
    resp.raise_for_status()
    return resp


# ---------------------------------------------------------------------------
# Pipeline endpoints
# ---------------------------------------------------------------------------

def upload_blog(input_data: dict) -> dict:
    """POST /upload-blog — ingest content, returns {job_id, status, message}."""
    return _post("/upload-blog", input_data)


def generate_script(job_id: str) -> dict:
    """POST /generate-script — start script generation (returns immediately)."""
    return _post("/generate-script", {"job_id": job_id})


def get_script(job_id: str) -> dict:
    """GET /job/{job_id}/script — fetch generated script (once ready)."""
    return _get(f"/job/{job_id}/script").json()


def generate_audio(job_id: str) -> dict:
    """POST /generate-audio — enqueue TTS synthesis, returns {job_id, audio_url, duration_seconds}."""
    return _post("/generate-audio", {"job_id": job_id})


def generate_podcast(input_data: dict) -> dict:
    """POST /generate-podcast — full one-shot pipeline, returns {job_id, status, message}."""
    return _post("/generate-podcast", input_data)


def get_job_status(job_id: str) -> dict:
    """GET /job/{job_id} — returns {status, progress, message, errors}."""
    return _get(f"/job/{job_id}").json()


def get_audio_bytes(job_id: str) -> bytes:
    """GET /download/{job_id} — returns raw MP3 bytes."""
    return _get(f"/download/{job_id}").content
