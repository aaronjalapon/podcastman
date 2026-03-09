# Blog-to-Podcast Conversion System (podcastman)

AI-powered system that converts blog posts into natural two-voice podcast episodes using RAG agents and Google Cloud TTS.

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

## Deploy To Google Cloud Run (MVP)

This repository includes an MVP Cloud Run deployment path that deploys:
- Backend API service (FastAPI)
- Frontend service (Streamlit)

### 1. Prerequisites

- `gcloud` CLI installed and authenticated
- Billing-enabled GCP project
- Roles to deploy Cloud Run, build images, and create Artifact Registry/Secret Manager resources

### 2. Create Secrets (once)

```bash
export PROJECT_ID="your-project-id"
gcloud config set project "$PROJECT_ID"

printf '%s' 'your-llm-api-key' | gcloud secrets create LLM_API_KEY --data-file=-
printf '%s' 'your-embedding-api-key' | gcloud secrets create EMBEDDING_API_KEY --data-file=-
```

If the secrets already exist, add new versions instead:

```bash
printf '%s' 'your-llm-api-key' | gcloud secrets versions add LLM_API_KEY --data-file=-
printf '%s' 'your-embedding-api-key' | gcloud secrets versions add EMBEDDING_API_KEY --data-file=-
```

### 3. Deploy Backend + Frontend

```bash
chmod +x scripts/deploy_cloud_run.sh

export PROJECT_ID="your-project-id"
export REGION="us-central1"

scripts/deploy_cloud_run.sh
```

### 4. Grant Google TTS permissions to backend service account

Cloud Run defaults to the Compute Engine default service account unless you set a custom one. Grant TTS access to whichever service account your backend uses:

```bash
export PROJECT_ID="your-project-id"
export REGION="us-central1"
export BACKEND_SERVICE="podcastman-backend"
export PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"

BACKEND_SA="$(gcloud run services describe "$BACKEND_SERVICE" --region "$REGION" --format='value(spec.template.spec.serviceAccountName)')"
if [ -z "$BACKEND_SA" ]; then
  BACKEND_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
fi

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${BACKEND_SA}" \
  --role="roles/cloudtts.user"
```

Notes:
- In Cloud Run, the app uses Application Default Credentials (ADC). You do not need to set `GOOGLE_APPLICATION_CREDENTIALS` there.
- MVP deployment stores generated files and Chroma data under `/tmp`, which is ephemeral.
- For production durability, migrate scripts/audio to Cloud Storage and job state to Firestore/Redis/SQL.

## Architecture

```
Blog Input → Content Ingestion → RAG Knowledge Base (ChromaDB)
  → Script Generation Agent → Accuracy Check Agent
  → Storytelling Agent → Engagement Agent
  → Google Cloud TTS Voice Synthesis (2 voices)
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
- **TTS**: Google Cloud TTS (two-voice dialogue)
- **API**: FastAPI
- **Audio**: pydub + ffmpeg + noisereduce

## Configuration

Most runtime settings are configured via `.env` (see `.env.example`).

Frontend design settings are configured in root `config.toml`:

```toml
[ui]
page_title = "podcastman - Blog to Podcast"
page_icon = "PM"
app_name = "podcastman"
tagline = "Blog to Podcast with AI"
layout = "centered"

[theme]
primary_color = "#0b5fff"
accent_color = "#12b886"
background_start = "#f4f8ff"
background_end = "#eefaf4"
surface_color = "#ffffff"
text_color = "#0f172a"
muted_text_color = "#5b6472"
border_color = "#d6deea"
font_family = "'Space Grotesk', 'Segoe UI', sans-serif"
mono_font_family = "'IBM Plex Mono', ui-monospace, SFMono-Regular, Menlo, monospace"

[icons]
generate = "fa-solid fa-wand-magic-sparkles"
download = "fa-solid fa-download"
```

Notes:
- Emoji-based UI labels were removed from the frontend.
- Font Awesome class names are mapped by semantic key in `[icons]`.
- If `config.toml` is missing or invalid, safe defaults are applied.
