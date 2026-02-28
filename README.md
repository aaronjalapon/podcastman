# Blog-to-Podcast Conversion System (podcastman)

AI-powered system that converts blog posts into natural two-voice podcast episodes using RAG agents and Coqui XTTS v2.

## Quick Start

```bash
# Install dependencies
uv sync

# Copy env config
cp .env.example .env
# Edit .env with your API keys

# Run the API server
uv run uvicorn api.main:app --reload

# Or run the full pipeline directly
uv run python -m podcastman.cli --url "https://example.com/blog-post"
```

## Architecture

```
Blog Input → Content Ingestion → RAG Knowledge Base (ChromaDB)
  → Script Generation Agent → Accuracy Check Agent
  → Storytelling Agent → Engagement Agent
  → Coqui XTTS v2 Voice Synthesis (2 voices)
  → Audio Post-Processing → Final Podcast MP3
```

## API Endpoints

- `POST /upload-blog` — Ingest blog content (URL, text, or markdown)
- `POST /generate-script` — Generate podcast script from ingested content
- `POST /generate-audio` — Synthesize audio from script
- `POST /generate-podcast` — Full end-to-end pipeline
- `GET /job/{job_id}` — Check job status
- `GET /download/{job_id}` — Download finished podcast

## Tech Stack

- **LLM**: LiteLLM (OpenAI, Anthropic, Ollama — switchable)
- **Orchestration**: LangChain + LangGraph (multi-agent pipeline)
- **Vector DB**: ChromaDB
- **TTS**: Coqui XTTS v2 (two-voice dialogue)
- **API**: FastAPI
- **Audio**: pydub + ffmpeg + noisereduce

## Configuration

All settings via `.env` — see `.env.example` for available options.
