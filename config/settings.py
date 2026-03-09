"""Application settings loaded from environment variables / .env file."""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── LLM ──────────────────────────────────────────────────────────────
    llm_model: str = "gpt-4o"
    llm_api_key: str = ""

    # ── Embeddings ───────────────────────────────────────────────────────
    embedding_model: str = "text-embedding-3-small"
    embedding_api_key: str = ""

    # ── ChromaDB ─────────────────────────────────────────────────────────
    chroma_persist_dir: str = "./data/chromadb"

    # ── Google Cloud TTS ─────────────────────────────────────────────────
    google_tts_voice_a: str = "en-US-Standard-J"
    google_tts_voice_b: str = "en-US-Standard-H"
    google_tts_language_code: str = "en-US"
    google_application_credentials: str = ""

    # ── Audio ────────────────────────────────────────────────────────────
    output_dir: str = "./output"
    intro_audio: str = ""
    outro_audio: str = ""
    pause_between_speakers_ms: int = 400

    # ── API ──────────────────────────────────────────────────────────────
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # ── Logging ──────────────────────────────────────────────────────────
    log_level: str = "INFO"

    # ── Derived paths ────────────────────────────────────────────────────
    @property
    def output_path(self) -> Path:
        p = Path(self.output_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def scripts_path(self) -> Path:
        p = self.output_path / "scripts"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def audio_path(self) -> Path:
        p = self.output_path / "audio"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def segments_path(self) -> Path:
        p = self.audio_path / "segments"
        p.mkdir(parents=True, exist_ok=True)
        return p


settings = Settings()
