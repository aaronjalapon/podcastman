"""Shared data models used across the pipeline."""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


# ── Content Models ───────────────────────────────────────────────────────────


@dataclass
class Chunk:
    """A single semantic chunk of blog content."""

    text: str
    index: int
    metadata: dict = field(default_factory=dict)

    @property
    def id(self) -> str:
        return f"chunk-{self.index}-{hashlib.md5(self.text[:50].encode()).hexdigest()[:8]}"


@dataclass
class BlogContent:
    """Structured representation of an ingested blog post."""

    title: str
    text: str
    chunks: list[Chunk]
    source_url: str = ""
    author: str = ""
    publish_date: str = ""
    ingested_at: str = field(default_factory=lambda: datetime.now().isoformat())

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(self.text.encode()).hexdigest()[:16]


# ── Script Models ────────────────────────────────────────────────────────────


class Speaker(str, Enum):
    HOST_A = "HOST_A"
    HOST_B = "HOST_B"


@dataclass
class SpeakerSegment:
    """A single segment of dialogue in the podcast script."""

    speaker: Speaker
    text: str
    index: int
    cues: list[str] = field(default_factory=list)  # e.g. ["pause", "emphasis"]


@dataclass
class PodcastScript:
    """The complete podcast script with metadata."""

    raw_script: str = ""
    accuracy_checked_script: str = ""
    enhanced_script: str = ""
    final_script: str = ""
    segments: list[SpeakerSegment] = field(default_factory=list)


# ── Pipeline State ───────────────────────────────────────────────────────────


class JobStatus(str, Enum):
    PENDING = "pending"
    INGESTING = "ingesting"
    GENERATING_SCRIPT = "generating_script"
    ENHANCING_SCRIPT = "enhancing_script"
    SYNTHESIZING = "synthesizing"
    POST_PROCESSING = "post_processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class PipelineState:
    """Full state carried through the LangGraph pipeline."""

    job_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: JobStatus = JobStatus.PENDING
    blog_content: BlogContent | None = None
    script: PodcastScript = field(default_factory=PodcastScript)
    audio_file: str = ""
    errors: list[str] = field(default_factory=list)
    progress: float = 0.0
