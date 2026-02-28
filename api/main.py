"""FastAPI application entry point."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.routes import router
from config.settings import settings
from tts.engine import cleanup_stale_runs
from utils.helpers import get_logger

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup/shutdown lifecycle."""
    log.info("podcastman starting up")
    log.info("LLM model: %s", settings.llm_model)
    log.info("TTS model: %s", settings.coqui_model_name)
    log.info("Output dir: %s", settings.output_dir)

    # Ensure output directories exist
    settings.output_path
    settings.scripts_path
    settings.audio_path
    settings.segments_path

    # Remove orphaned segment directories from crashed/abandoned previous runs
    cleanup_stale_runs()
    log.info("Stale run cleanup complete")

    yield

    log.info("podcastman shutting down")


app = FastAPI(
    title="podcastman",
    description="Blog-to-Podcast Conversion System with AI Voice Generation",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for audio downloads
try:
    app.mount("/static", StaticFiles(directory=settings.output_dir), name="static")
except Exception:
    log.warning("Could not mount static files directory: %s", settings.output_dir)

# Include API routes
app.include_router(router, prefix="/api/v1", tags=["pipeline"])


# Health check
@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
    )
