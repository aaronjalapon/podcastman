"""API routes for the blog-to-podcast pipeline."""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse

from agents.graph import run_pipeline
from api.schemas import (
    AudioRequest,
    AudioResponse,
    BlogInput,
    ErrorResponse,
    FullPipelineRequest,
    JobResponse,
    JobStatusResponse,
    ScriptRequest,
    ScriptResponse,
)
from audio.assembler import assemble_podcast
from audio.postprocess import postprocess_all
from config.settings import settings
from ingestion.chunker import chunk_text
from ingestion.parser import normalize_text, parse_markdown
from ingestion.scraper import scrape_url
from models.data import BlogContent, JobStatus
from rag.vectorstore import add_chunks
from tts.dialogue_parser import parse_dialogue
from tts.engine import cleanup_run, synthesize_all
from utils.helpers import get_logger, write_text

log = get_logger(__name__)
router = APIRouter()

# ── In-memory job store ──────────────────────────────────────────────────────
# In production, replace with Redis or a database.
_jobs: dict[str, dict] = {}


# ── Helpers ──────────────────────────────────────────────────────────────────


def _ingest_content(input_data: BlogInput | FullPipelineRequest) -> BlogContent:
    """Ingest blog content from URL, text, or markdown."""
    if input_data.url:
        scraped = scrape_url(input_data.url)
        title = input_data.title or scraped["title"]
        text = normalize_text(scraped["text"])
        source_url = input_data.url
        author = ", ".join(scraped.get("authors", []))
    elif input_data.markdown:
        text = parse_markdown(input_data.markdown)
        title = input_data.title or "Untitled"
        source_url = ""
        author = ""
    elif input_data.text:
        text = normalize_text(input_data.text)
        title = input_data.title or "Untitled"
        source_url = ""
        author = ""
    else:
        raise HTTPException(400, "Provide one of: url, text, or markdown")

    chunks = chunk_text(text, metadata={"title": title, "source_url": source_url})

    return BlogContent(
        title=title,
        text=text,
        chunks=chunks,
        source_url=source_url,
        author=author,
    )


# ── Routes ───────────────────────────────────────────────────────────────────


@router.post("/upload-blog", response_model=JobResponse)
async def upload_blog(input_data: BlogInput):
    """Ingest blog content and index in the RAG knowledge base."""
    job_id = str(uuid.uuid4())
    _jobs[job_id] = {"status": JobStatus.INGESTING, "progress": 0.1}

    try:
        blog = _ingest_content(input_data)
        collection_name = add_chunks(blog)

        _jobs[job_id] = {
            "status": JobStatus.PENDING,
            "progress": 1.0,
            "blog": blog,
            "collection_name": collection_name,
        }

        return JobResponse(
            job_id=job_id,
            status="ingested",
            message=f"Ingested '{blog.title}' — {len(blog.chunks)} chunks indexed",
        )
    except HTTPException:
        raise
    except Exception as e:
        _jobs[job_id] = {"status": JobStatus.FAILED, "error": str(e)}
        raise HTTPException(500, str(e))


@router.post("/generate-script", response_model=JobResponse)
async def generate_script(request: ScriptRequest, background_tasks: BackgroundTasks):
    """Start podcast script generation in the background.

    Returns immediately with a job ID. Poll /job/{job_id} for status,
    then GET /job/{job_id}/script to retrieve the finished script.
    """
    job = _jobs.get(request.job_id)
    if not job or "blog" not in job:
        raise HTTPException(404, "Job not found or blog not ingested")

    _jobs[request.job_id]["status"] = JobStatus.GENERATING_SCRIPT
    _jobs[request.job_id]["progress"] = 0.2

    background_tasks.add_task(_generate_script_task, request.job_id)

    return JobResponse(
        job_id=request.job_id,
        status="generating_script",
        message="Script generation started. Poll /job/{job_id} for status.",
    )


@router.post("/generate-audio", response_model=AudioResponse)
async def generate_audio(request: AudioRequest, background_tasks: BackgroundTasks):
    """Generate audio from a previously generated script.

    Audio synthesis runs as a background task since it's slow.
    """
    job = _jobs.get(request.job_id)
    if not job or "segments" not in job:
        raise HTTPException(404, "Job not found or script not generated")

    _jobs[request.job_id]["status"] = JobStatus.SYNTHESIZING
    _jobs[request.job_id]["progress"] = 0.6

    background_tasks.add_task(_synthesize_audio, request.job_id)

    return AudioResponse(
        job_id=request.job_id,
        audio_url=f"/download/{request.job_id}",
        status="synthesizing",
    )


@router.post("/generate-podcast", response_model=JobResponse)
async def generate_podcast(
    input_data: FullPipelineRequest,
    background_tasks: BackgroundTasks,
):
    """Full end-to-end pipeline: blog → podcast audio.

    Runs the entire pipeline in the background. Poll /job/{job_id} for status.
    """
    job_id = str(uuid.uuid4())
    _jobs[job_id] = {"status": JobStatus.INGESTING, "progress": 0.0}

    background_tasks.add_task(_full_pipeline, job_id, input_data)

    return JobResponse(
        job_id=job_id,
        status="started",
        message="Full pipeline started. Poll /job/{job_id} for status.",
    )


@router.get("/job/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    """Poll job status."""
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")

    return JobStatusResponse(
        job_id=job_id,
        status=job.get("status", JobStatus.PENDING).value
        if hasattr(job.get("status"), "value")
        else str(job.get("status", "unknown")),
        progress=job.get("progress", 0.0),
        message=job.get("message", ""),
        errors=job.get("errors", []),
    )


@router.get("/job/{job_id}/script", response_model=ScriptResponse)
async def get_job_script(job_id: str):
    """Retrieve the generated script for a job.

    Returns 404 if the job doesn't exist, or 202 if the script is not yet ready.
    """
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")

    if "script" not in job:
        raise HTTPException(202, "Script not ready yet")

    segments = job.get("segments", [])
    result = job.get("pipeline_result", {})

    return ScriptResponse(
        job_id=job_id,
        script=job["script"],
        segment_count=len(segments),
        raw_script=job.get("raw_script", ""),
        errors=result.get("errors", []),
    )


@router.get("/download/{job_id}")
async def download_audio(job_id: str):
    """Download the generated podcast audio file."""
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")

    audio_file = job.get("audio_file")
    if not audio_file or not Path(audio_file).exists():
        raise HTTPException(404, "Audio file not ready or not found")

    return FileResponse(
        audio_file,
        media_type="audio/mpeg",
        filename=f"podcast_{job_id[:8]}.mp3",
    )


# ── Background Tasks ────────────────────────────────────────────────────────
# NOTE: These are plain `def` (not `async def`) so that Starlette runs them
# in a threadpool, keeping the async event loop free for other requests.


def _generate_script_task(job_id: str) -> None:
    """Background task: generate podcast script via the LangGraph pipeline."""
    job = _jobs[job_id]
    blog: BlogContent = job["blog"]
    collection_name: str = job["collection_name"]

    try:
        result = run_pipeline(
            title=blog.title,
            content=blog.text,
            collection_name=collection_name,
        )

        final_script = result.get("final_script", result.get("raw_script", ""))

        if not final_script or not final_script.strip():
            errors = result.get("errors", [])
            error_msg = f"Script generation produced empty content. Errors: {errors}"
            log.error(error_msg)
            _jobs[job_id].update({
                "status": JobStatus.FAILED,
                "errors": job.get("errors", []) + [error_msg],
            })
            return

        segments = parse_dialogue(final_script)

        # Save script to disk
        write_text(settings.scripts_path / f"{job_id}.txt", final_script)

        _jobs[job_id].update({
            "status": JobStatus.ENHANCING_SCRIPT,
            "progress": 0.5,
            "script": final_script,
            "raw_script": result.get("raw_script", ""),
            "segments": segments,
            "pipeline_result": result,
            "message": "Script generated successfully",
        })
    except Exception as e:
        log.error("Script generation failed for job %s: %s", job_id, e)
        _jobs[job_id].update({
            "status": JobStatus.FAILED,
            "errors": job.get("errors", []) + [str(e)],
        })


def _synthesize_audio(job_id: str) -> None:
    """Background task: synthesize audio from script segments."""
    job = _jobs[job_id]
    try:
        segments = job["segments"]

        def _on_segment(done: int, total: int) -> None:
            # Map synthesis progress across the 0.6 → 0.8 range
            pct = 0.6 + 0.2 * (done / total)
            _jobs[job_id]["progress"] = round(pct, 2)
            _jobs[job_id]["message"] = f"Synthesized segment {done}/{total}"

        # Synthesize into an isolated per-job directory
        audio_paths, run_dir = synthesize_all(
            segments, on_segment_done=_on_segment, run_id=job_id
        )

        # Post-process
        _jobs[job_id]["status"] = JobStatus.POST_PROCESSING
        _jobs[job_id]["progress"] = 0.8
        processed = postprocess_all(audio_paths)

        # Assemble
        output_path = settings.audio_path / f"podcast_{job_id[:8]}.mp3"
        final_path = assemble_podcast(processed, segments, output_path)

        # Free temporary segment files now that assembly is complete
        cleanup_run(run_dir)

        _jobs[job_id].update({
            "status": JobStatus.COMPLETED,
            "progress": 1.0,
            "audio_file": str(final_path),
            "message": "Podcast generated successfully",
        })
    except Exception as e:
        log.error("Audio synthesis failed for job %s: %s", job_id, e)
        _jobs[job_id].update({
            "status": JobStatus.FAILED,
            "errors": job.get("errors", []) + [str(e)],
        })


def _full_pipeline(job_id: str, input_data: FullPipelineRequest) -> None:
    """Background task: run the complete blog → podcast pipeline."""
    try:
        # Step 1: Ingest
        _jobs[job_id].update({"status": JobStatus.INGESTING, "progress": 0.1})
        blog = _ingest_content(input_data)
        collection_name = add_chunks(blog)

        # Step 2: Generate script
        _jobs[job_id].update({
            "status": JobStatus.GENERATING_SCRIPT,
            "progress": 0.2,
            "blog": blog,
            "collection_name": collection_name,
        })
        result = run_pipeline(
            title=blog.title,
            content=blog.text,
            collection_name=collection_name,
        )

        final_script = result.get("final_script", result.get("raw_script", ""))
        
        # Validate script is not empty
        if not final_script or not final_script.strip():
            errors = result.get("errors", [])
            error_msg = f"Script generation produced empty content. Errors: {errors}"
            log.error(error_msg)
            raise HTTPException(status_code=500, detail=error_msg)
        
        segments = parse_dialogue(final_script)

        # Save script
        write_text(settings.scripts_path / f"{job_id}.txt", final_script)

        _jobs[job_id].update({
            "script": final_script,
            "segments": segments,
            "pipeline_result": result,
        })

        # Step 3: Synthesize audio
        _jobs[job_id].update({"status": JobStatus.SYNTHESIZING, "progress": 0.5})

        def _on_segment(done: int, total: int) -> None:
            pct = 0.5 + 0.3 * (done / total)
            _jobs[job_id]["progress"] = round(pct, 2)
            _jobs[job_id]["message"] = f"Synthesized segment {done}/{total}"

        # Synthesize into an isolated per-job directory
        audio_paths, run_dir = synthesize_all(
            segments, on_segment_done=_on_segment, run_id=job_id
        )

        # Step 4: Post-process
        _jobs[job_id].update({"status": JobStatus.POST_PROCESSING, "progress": 0.8})
        processed = postprocess_all(audio_paths)

        # Step 5: Assemble
        output_path = settings.audio_path / f"podcast_{job_id[:8]}.mp3"
        final_path = assemble_podcast(processed, segments, output_path)

        # Free temporary segment files now that assembly is complete
        cleanup_run(run_dir)

        _jobs[job_id].update({
            "status": JobStatus.COMPLETED,
            "progress": 1.0,
            "audio_file": str(final_path),
            "message": "Podcast generated successfully",
        })

    except Exception as e:
        log.error("Full pipeline failed for job %s: %s", job_id, e)
        _jobs[job_id].update({
            "status": JobStatus.FAILED,
            "errors": _jobs[job_id].get("errors", []) + [str(e)],
        })
