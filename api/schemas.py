"""Pydantic request/response schemas for the API."""

from __future__ import annotations

from pydantic import BaseModel, Field


# ── Requests ─────────────────────────────────────────────────────────────────


class BlogInput(BaseModel):
    """Input for blog content — provide exactly one of url, text, or markdown."""

    url: str | None = Field(None, description="URL of the blog post to scrape")
    text: str | None = Field(None, description="Raw text content of the blog")
    markdown: str | None = Field(None, description="Markdown content of the blog")
    title: str | None = Field(None, description="Optional title override")


class ScriptRequest(BaseModel):
    """Request to generate a script from previously ingested content."""

    job_id: str = Field(..., description="Job ID from the upload step")


class AudioRequest(BaseModel):
    """Request to generate audio from a previously generated script."""

    job_id: str = Field(..., description="Job ID from the script generation step")


class FullPipelineRequest(BaseModel):
    """Request for full end-to-end podcast generation."""

    url: str | None = Field(None, description="URL of the blog post")
    text: str | None = Field(None, description="Raw text content")
    markdown: str | None = Field(None, description="Markdown content")
    title: str | None = Field(None, description="Optional title override")


# ── Responses ────────────────────────────────────────────────────────────────


class JobResponse(BaseModel):
    """Response with job tracking information."""

    job_id: str
    status: str
    message: str = ""


class ScriptResponse(BaseModel):
    """Response containing the generated podcast script."""

    job_id: str
    script: str
    segment_count: int
    raw_script: str = ""
    errors: list[str] = []


class AudioResponse(BaseModel):
    """Response containing audio generation results."""

    job_id: str
    audio_url: str
    duration_seconds: float = 0.0
    status: str = "completed"


class JobStatusResponse(BaseModel):
    """Response for job status polling."""

    job_id: str
    status: str
    progress: float = 0.0
    message: str = ""
    errors: list[str] = []


class ErrorResponse(BaseModel):
    """Standard error response."""

    detail: str
    errors: list[str] = []
