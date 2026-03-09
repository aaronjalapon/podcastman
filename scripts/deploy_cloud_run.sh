#!/usr/bin/env bash
set -euo pipefail

# MVP deploy script for podcastman on Google Cloud Run.
# Required environment variables:
#   PROJECT_ID, REGION
# Optional:
#   REPO_NAME (default: podcastman)
#   BACKEND_SERVICE (default: podcastman-backend)
#   FRONTEND_SERVICE (default: podcastman-frontend)
#   IMAGE_TAG (default: current timestamp)
#   LLM_MODEL (default: groq/llama-3.3-70b-versatile)
#   EMBEDDING_MODEL (default: jina_ai/jina-embeddings-v3)
#   GOOGLE_TTS_VOICE_A (default: en-US-Standard-J)
#   GOOGLE_TTS_VOICE_B (default: en-US-Standard-H)
#   GOOGLE_TTS_LANGUAGE_CODE (default: en-US)

if [[ -z "${PROJECT_ID:-}" ]]; then
  echo "PROJECT_ID is required"
  exit 1
fi

if [[ -z "${REGION:-}" ]]; then
  echo "REGION is required"
  exit 1
fi

REPO_NAME="${REPO_NAME:-podcastman}"
BACKEND_SERVICE="${BACKEND_SERVICE:-podcastman-backend}"
FRONTEND_SERVICE="${FRONTEND_SERVICE:-podcastman-frontend}"
IMAGE_TAG="${IMAGE_TAG:-$(date +%Y%m%d-%H%M%S)}"

LLM_MODEL="${LLM_MODEL:-groq/llama-3.3-70b-versatile}"
EMBEDDING_MODEL="${EMBEDDING_MODEL:-jina_ai/jina-embeddings-v3}"
GOOGLE_TTS_VOICE_A="${GOOGLE_TTS_VOICE_A:-en-US-Standard-J}"
GOOGLE_TTS_VOICE_B="${GOOGLE_TTS_VOICE_B:-en-US-Standard-H}"
GOOGLE_TTS_LANGUAGE_CODE="${GOOGLE_TTS_LANGUAGE_CODE:-en-US}"

AR_HOST="${REGION}-docker.pkg.dev"
BACKEND_IMAGE="${AR_HOST}/${PROJECT_ID}/${REPO_NAME}/backend:${IMAGE_TAG}"
FRONTEND_IMAGE="${AR_HOST}/${PROJECT_ID}/${REPO_NAME}/frontend:${IMAGE_TAG}"

echo "Using project: ${PROJECT_ID}"
echo "Using region:  ${REGION}"

gcloud config set project "${PROJECT_ID}" >/dev/null

gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  secretmanager.googleapis.com \
  texttospeech.googleapis.com

if ! gcloud artifacts repositories describe "${REPO_NAME}" --location="${REGION}" >/dev/null 2>&1; then
  gcloud artifacts repositories create "${REPO_NAME}" \
    --repository-format=docker \
    --location="${REGION}" \
    --description="podcastman container images"
fi

echo "Building backend image: ${BACKEND_IMAGE}"
gcloud builds submit --tag "${BACKEND_IMAGE}" -f Dockerfile.backend .

echo "Deploying backend service: ${BACKEND_SERVICE}"
gcloud run deploy "${BACKEND_SERVICE}" \
  --image "${BACKEND_IMAGE}" \
  --region "${REGION}" \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 1 \
  --timeout 900 \
  --set-env-vars "LLM_MODEL=${LLM_MODEL},EMBEDDING_MODEL=${EMBEDDING_MODEL},GOOGLE_TTS_VOICE_A=${GOOGLE_TTS_VOICE_A},GOOGLE_TTS_VOICE_B=${GOOGLE_TTS_VOICE_B},GOOGLE_TTS_LANGUAGE_CODE=${GOOGLE_TTS_LANGUAGE_CODE},OUTPUT_DIR=/tmp/output,CHROMA_PERSIST_DIR=/tmp/chromadb" \
  --set-secrets "LLM_API_KEY=LLM_API_KEY:latest,EMBEDDING_API_KEY=EMBEDDING_API_KEY:latest"

BACKEND_URL="$(gcloud run services describe "${BACKEND_SERVICE}" --region "${REGION}" --format='value(status.url)')"
echo "Backend URL: ${BACKEND_URL}"

echo "Building frontend image: ${FRONTEND_IMAGE}"
gcloud builds submit --tag "${FRONTEND_IMAGE}" -f Dockerfile.frontend .

echo "Deploying frontend service: ${FRONTEND_SERVICE}"
gcloud run deploy "${FRONTEND_SERVICE}" \
  --image "${FRONTEND_IMAGE}" \
  --region "${REGION}" \
  --allow-unauthenticated \
  --memory 1Gi \
  --cpu 1 \
  --timeout 900 \
  --set-env-vars "PODCASTMAN_API_BASE=${BACKEND_URL}"

FRONTEND_URL="$(gcloud run services describe "${FRONTEND_SERVICE}" --region "${REGION}" --format='value(status.url)')"

echo ""
echo "Deployment complete"
echo "Backend:  ${BACKEND_URL}"
echo "Frontend: ${FRONTEND_URL}"
