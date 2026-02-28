"""podcastman — Streamlit frontend.

Run with:
    streamlit run frontend/app.py

The FastAPI backend is auto-started on http://localhost:8000 if not
already running. No need to launch uvicorn manually.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from pathlib import Path

import requests
import streamlit as st

# Make the project root importable so `frontend/api.py` can be found
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(_PROJECT_ROOT))


# ---------------------------------------------------------------------------
# Bridge st.secrets → os.environ (for Streamlit Cloud deployment)
# ---------------------------------------------------------------------------
def _bridge_secrets_to_env() -> None:
    """Copy Streamlit secrets into os.environ so pydantic-settings picks them up."""
    try:
        for key, value in st.secrets.items():
            if isinstance(value, str) and key not in os.environ:
                os.environ[key] = value
    except Exception:
        pass  # No secrets configured — running locally with .env


_bridge_secrets_to_env()


# ---------------------------------------------------------------------------
# Auto-start FastAPI backend
# ---------------------------------------------------------------------------
_BACKEND_URL = os.environ.get("API_BASE_URL", "http://localhost:8000/api/v1")
_HEALTH_URL = _BACKEND_URL.rsplit("/api/v1", 1)[0] + "/health"


def _backend_is_running() -> bool:
    """Check if the FastAPI backend responds at /health."""
    try:
        resp = requests.get(_HEALTH_URL, timeout=2)
        return resp.status_code == 200
    except Exception:
        return False


def _ensure_backend() -> None:
    """Launch uvicorn as a subprocess if the backend isn't already running."""
    if _backend_is_running():
        return

    # Launch backend from the project root
    subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "api.main:app",
         "--host", "0.0.0.0", "--port", "8000"],
        cwd=str(_PROJECT_ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Wait for it to become healthy (up to 30 seconds)
    for _ in range(30):
        if _backend_is_running():
            return
        time.sleep(1)


_ensure_backend()

import api as backend  # noqa: E402  (local api.py)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PIPELINE_STAGES: list[tuple[str, str]] = [
    ("ingesting", "Ingesting Content"),
    ("generating_script", "Generating Script"),
    ("enhancing_script", "Enhancing Script"),
    ("synthesizing", "Synthesizing Audio"),
    ("post_processing", "Post-Processing"),
    ("completed", "Completed"),
]

STAGE_KEYS = [s[0] for s in PIPELINE_STAGES]
POLL_INTERVAL = 3  # seconds between status polls


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def format_duration(seconds: float) -> str:
    m = int(seconds // 60)
    s = round(seconds % 60)
    return f"{m}:{s:02d}"


def reset_state() -> None:
    for key in ("job_id", "script", "segment_count", "audio_duration", "error", "audio_bytes", "pipeline_mode"):
        st.session_state.pop(key, None)
    st.session_state["step"] = "input"


def init_state() -> None:
    defaults = {
        "step": "input",
        "job_id": "",
        "script": "",
        "segment_count": 0,
        "audio_duration": 0.0,
        "audio_bytes": None,
        "error": None,
        "use_full_pipeline": True,
        "pipeline_mode": "full",  # "full" or "step"
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


# ---------------------------------------------------------------------------
# Pipeline actions
# ---------------------------------------------------------------------------

def handle_full_pipeline(input_data: dict) -> None:
    try:
        res = backend.generate_podcast(input_data)
        st.session_state["job_id"] = res["job_id"]
        st.session_state["pipeline_mode"] = "full"
        st.session_state["step"] = "processing"
        st.session_state["error"] = None
    except Exception as exc:
        st.session_state["error"] = f"Failed to start pipeline: {exc}"


def handle_step_by_step(input_data: dict) -> None:
    try:
        upload_res = backend.upload_blog(input_data)
        job_id = upload_res["job_id"]
        st.session_state["job_id"] = job_id

        # Kick off script generation (returns immediately)
        backend.generate_script(job_id)
        st.session_state["pipeline_mode"] = "step"
        st.session_state["step"] = "processing"
        st.session_state["error"] = None
    except Exception as exc:
        st.session_state["error"] = f"Pipeline step failed: {exc}"


def handle_generate_audio() -> None:
    job_id = st.session_state["job_id"]
    if not job_id:
        return
    try:
        backend.generate_audio(job_id)
        st.session_state["pipeline_mode"] = "full"  # audio stage polls to completion
        st.session_state["step"] = "processing"
        st.session_state["error"] = None
    except Exception as exc:
        st.session_state["error"] = f"Audio generation failed: {exc}"


# ---------------------------------------------------------------------------
# UI sections
# ---------------------------------------------------------------------------

def render_header() -> None:
    st.markdown(
        """
        <div style="border-bottom:1px solid #333;padding-bottom:1rem;margin-bottom:1.5rem">
            <span style="font-size:2rem">🎙️</span>
            <span style="font-size:1.4rem;font-weight:700;margin-left:.5rem">podcastman</span>
            <span style="color:#888;font-size:.85rem;margin-left:.5rem">Blog → Podcast with AI</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_input_view() -> None:
    st.subheader("Turn any blog post into a podcast")
    st.caption(
        "Paste a URL, raw text, or Markdown — AI agents generate a two-voice dialogue."
    )

    use_full = st.checkbox(
        "Full pipeline (auto-run all steps)",
        value=st.session_state["use_full_pipeline"],
        key="use_full_pipeline",
    )

    tab_url, tab_text, tab_md = st.tabs(["🔗 URL", "📝 Text", "📄 Markdown"])

    mode = None
    content_value = ""

    with tab_url:
        url_val = st.text_input(
            "Blog post URL",
            placeholder="https://example.com/blog-post",
            key="input_url",
        )
        if url_val.strip():
            mode = "url"
            content_value = url_val.strip()

    with tab_text:
        text_val = st.text_area(
            "Blog post content",
            placeholder="Paste your blog post content here…",
            height=250,
            key="input_text",
        )
        char_count = len(text_val.strip())
        if text_val.strip():
            mode = "text"
            content_value = text_val.strip()
            suffix = " (minimum 50 required)" if char_count < 50 else ""
            st.caption(f"{char_count} characters{suffix}")

    with tab_md:
        md_val = st.text_area(
            "Blog post Markdown",
            placeholder="# Blog Title\n\nYour markdown content here…",
            height=250,
            key="input_md",
        )
        if md_val.strip():
            mode = "markdown"
            content_value = md_val.strip()
            st.caption(f"{len(md_val.strip())} characters")

    title_val = st.text_input(
        "Episode title (optional)",
        placeholder="Custom podcast episode title",
        key="input_title",
    )

    # Validation
    is_valid = False
    if mode == "url" and content_value:
        is_valid = True
    elif mode in ("text", "markdown") and len(content_value) >= 50:
        is_valid = True

    if st.button(
        "🎙️ Generate Podcast" if not use_full else "🎙️ Generate Podcast (Full Pipeline)",
        disabled=not is_valid,
        type="primary",
    ):
        input_data: dict = {}
        if title_val.strip():
            input_data["title"] = title_val.strip()
        input_data[mode] = content_value

        with st.spinner("Starting pipeline…"):
            if use_full:
                handle_full_pipeline(input_data)
            else:
                handle_step_by_step(input_data)
        st.rerun()


def render_processing_view() -> None:
    job_id: str = st.session_state["job_id"]

    st.subheader("⚙️ Pipeline Running…")
    if job_id:
        st.caption(f"Job ID: `{job_id[:8]}…`")

    try:
        status_data = backend.get_job_status(job_id)
    except Exception as exc:
        st.session_state["error"] = f"Status polling failed: {exc}"
        st.session_state["step"] = "input"
        st.rerun()
        return

    current_status: str = status_data.get("status", "pending")
    progress: float = float(status_data.get("progress", 0.0))
    message: str = status_data.get("message", "")
    errors: list[str] = status_data.get("errors", [])

    # Progress bar
    st.progress(min(max(progress, 0.02), 1.0))

    if current_status == "failed":
        error_msg = "; ".join(errors) if errors else "Pipeline failed"
        st.session_state["error"] = error_msg
        st.session_state["step"] = "input"
        st.rerun()
        return

    if current_status == "completed":
        st.session_state["step"] = "audio"
        st.rerun()
        return

    # In step-by-step mode, stop polling once the script is ready
    # (status moves to "enhancing_script" after the script background task finishes)
    pipeline_mode = st.session_state.get("pipeline_mode", "full")
    if pipeline_mode == "step" and current_status == "enhancing_script":
        try:
            script_data = backend.get_script(job_id)
            st.session_state["script"] = script_data["script"]
            st.session_state["segment_count"] = script_data["segment_count"]
            st.session_state["step"] = "script"
            st.rerun()
            return
        except Exception:
            pass  # script not ready yet; keep polling

    # Stage list
    current_index = STAGE_KEYS.index(current_status) if current_status in STAGE_KEYS else -1
    stage_lines = []
    for i, (key, label) in enumerate(PIPELINE_STAGES):
        if i < current_index or current_status == "completed":
            marker = "✅"
        elif i == current_index:
            marker = "🔵"
        else:
            marker = "⚪"
        stage_lines.append(f"{marker} {label}")
    st.markdown("\n\n".join(stage_lines))

    if message:
        st.caption(message)
    if errors:
        for e in errors:
            st.warning(e)

    st.caption(f"{round(progress * 100)}% complete — polling every {POLL_INTERVAL}s…")

    # Poll again after a short delay
    time.sleep(POLL_INTERVAL)
    st.rerun()


def render_script_view() -> None:
    script: str = st.session_state["script"]
    segment_count: int = st.session_state["segment_count"]

    col1, col2 = st.columns([3, 1])
    with col1:
        st.subheader("📝 Podcast Script")
    with col2:
        st.metric("Segments", segment_count)

    # Build a regex that matches HOST_A/HOST_B or the persona names (Mike/Sarah)
    try:
        from tts.voice_config import HOST_A as VOICE_A, HOST_B as VOICE_B
        host_a_name, host_b_name = VOICE_A.name, VOICE_B.name
    except Exception:
        host_a_name, host_b_name = "Mike", "Sarah"

    # Match "HOST_A:", "Mike:", "**Mike:**" etc. at the start of a line
    _speaker_re = re.compile(
        rf"^\*{{0,2}}({re.escape(host_a_name)}|HOST_A)\*{{0,2}}\s*:\s*(.*)",
        re.IGNORECASE,
    )
    _speaker_b_re = re.compile(
        rf"^\*{{0,2}}({re.escape(host_b_name)}|HOST_B)\*{{0,2}}\s*:\s*(.*)",
        re.IGNORECASE,
    )

    # Render dialogue
    lines = [l for l in script.splitlines() if l.strip()]
    for line in lines:
        m_a = _speaker_re.match(line.strip())
        m_b = _speaker_b_re.match(line.strip())
        if m_a:
            text = m_a.group(2).strip()
            with st.chat_message(host_a_name, avatar="🌤"):
                st.write(text)
        elif m_b:
            text = m_b.group(2).strip()
            with st.chat_message(host_b_name, avatar="🎧"):
                st.write(text)
        else:
            st.caption(line.strip())

    st.divider()

    col_audio, col_dl, col_reset = st.columns([2, 2, 1])
    with col_audio:
        if st.button("🔊 Generate Audio", type="primary"):
            with st.spinner("Starting audio synthesis…"):
                handle_generate_audio()
            st.rerun()
    with col_dl:
        st.download_button(
            "⬇️ Download Script (.txt)",
            data=script,
            file_name=f"script_{st.session_state['job_id'][:8]}.txt",
            mime="text/plain",
        )
    with col_reset:
        if st.button("↩ Start Over"):
            reset_state()
            st.rerun()


def render_audio_view() -> None:
    job_id: str = st.session_state["job_id"]

    st.success("🎉 Podcast Ready!")

    # Fetch audio bytes once and cache in session state
    if st.session_state.get("audio_bytes") is None:
        with st.spinner("Loading audio…"):
            try:
                st.session_state["audio_bytes"] = backend.get_audio_bytes(job_id)
            except Exception as exc:
                st.error(f"Could not load audio: {exc}")
                return

    audio_bytes: bytes = st.session_state["audio_bytes"]
    duration: float = st.session_state.get("audio_duration", 0.0)

    st.audio(audio_bytes, format="audio/mp3")

    if duration > 0:
        st.caption(f"Duration: {format_duration(duration)}")

    col_dl, col_reset = st.columns([2, 1])
    with col_dl:
        st.download_button(
            "⬇️ Download MP3",
            data=audio_bytes,
            file_name=f"podcast_{job_id[:8]}.mp3",
            mime="audio/mpeg",
            type="primary",
        )
    with col_reset:
        if st.button("← Generate Another"):
            reset_state()
            st.rerun()

    st.caption(f"Job ID: `{job_id}`")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    st.set_page_config(
        page_title="podcastman — Blog to Podcast",
        page_icon="🎙️",
        layout="centered",
    )

    init_state()
    render_header()

    # Global error banner
    if st.session_state.get("error"):
        st.error(st.session_state["error"])
        if st.button("✕ Dismiss"):
            st.session_state["error"] = None
            st.rerun()

    step: str = st.session_state["step"]

    if step == "input":
        render_input_view()
    elif step == "processing":
        render_processing_view()
    elif step == "script":
        render_script_view()
    elif step == "audio":
        render_audio_view()

    # Footer
    st.markdown(
        """
        <div style="border-top:1px solid #333;padding-top:.75rem;margin-top:3rem;
                    text-align:center;color:#666;font-size:.75rem">
            podcastman v0.1.0 — LiteLLM · LangGraph · Coqui XTTS v2 · ChromaDB
        </div>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
