# Blog-to-Podcast Conversion System (podcastman)

AI-powered system that converts blog posts into natural two-voice podcast episodes using RAG agents and Coqui XTTS v2.

## Quick Start

```bash
# Install dependencies
uv sync

# Copy env config
cp .env.example .env
# Edit .env with your API keys

# Run the Streamlit frontend (auto-starts the backend)
uv run streamlit run frontend/app.py

# Or run the API server directly
uv run uvicorn api.main:app --reload
```

## Streamlit Cloud Deployment

1. Push this repo to GitHub.

2. Go to [share.streamlit.io](https://share.streamlit.io) and create a new app:
   - **Repository**: your GitHub repo
   - **Main file path**: `frontend/app.py`

3. In the app **Settings → Secrets**, add your API keys (see `.streamlit/secrets.toml.example`):
   ```toml
   LLM_MODEL = "gpt-4o"
   LLM_API_KEY = "sk-..."
   EMBEDDING_MODEL = "text-embedding-3-small"
   EMBEDDING_API_KEY = "sk-..."
   ```

4. Deploy. The app auto-starts the FastAPI backend as a subprocess.

**Note:** Streamlit Community Cloud has resource limits. The Coqui XTTS v2 model
requires ~1.8 GB of memory. If you hit memory limits, consider deploying on a
VPS or cloud VM instead (`streamlit run frontend/app.py`).

### Voice Customization

Replace the reference WAV files in `voices/` to change the podcast host voices:

| Speaker | File | Description |
|---------|------|-------------|
| Host A | `voices/host_a.wav` | Main presenter |
| Host B | `voices/host_b.wav` | Co-host |

Requirements: 6–10 seconds of clear speech, WAV format, mono, 22050 Hz.

To rename the hosts, edit `tts/voice_config.py` — the names flow automatically
into script generation prompts, dialogue parsing, and the Streamlit UI.

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
