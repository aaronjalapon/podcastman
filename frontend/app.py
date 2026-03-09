"""podcastman — Streamlit frontend.

Run with:
    streamlit run frontend/app.py

Requires the FastAPI backend running on http://localhost:8000
    uvicorn api.main:app --reload
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import streamlit as st

# Make the project root importable so `frontend/api.py` can be found
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(1, str(Path(__file__).resolve().parent.parent))
import api as backend  # noqa: E402  (local api.py)
from config.frontend_design import frontend_design  # noqa: E402

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
# Presentation helpers
# ---------------------------------------------------------------------------


def icon_class(name: str) -> str:
    return frontend_design.icons.get(name, "fa-solid fa-circle")


def icon_html(name: str) -> str:
    return f"<i class='{icon_class(name)}' aria-hidden='true'></i>"


def icon_text(name: str, label: str) -> str:
    return f"{icon_html(name)} <span>{label}</span>"


def inject_design_css() -> None:
    theme = frontend_design.theme
    st.markdown(
        f"""
        <style>
            @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=Space+Grotesk:wght@400;500;700&display=swap');
            @import url('https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.2/css/all.min.css');

            :root {{
                --pm-primary: {theme.primary_color};
                --pm-accent: {theme.accent_color};
                --pm-bg-a: {theme.background_start};
                --pm-bg-b: {theme.background_end};
                --pm-surface: {theme.surface_color};
                --pm-text: {theme.text_color};
                --pm-muted: {theme.muted_text_color};
                --pm-border: {theme.border_color};
                --pm-font: {theme.font_family};
                --pm-mono: {theme.mono_font_family};
            }}

            .stApp {{
                background: radial-gradient(circle at 0% 0%, var(--pm-bg-a) 0%, var(--pm-bg-b) 100%);
                color: var(--pm-text);
                font-family: var(--pm-font);
            }}

            [data-testid="stMarkdownContainer"] p,
            [data-testid="stMarkdownContainer"] li,
            [data-testid="stCaptionContainer"] {{
                color: var(--pm-text);
                font-family: var(--pm-font);
            }}

            .pm-card {{
                background: color-mix(in srgb, var(--pm-surface) 93%, white 7%);
                border: 1px solid var(--pm-border);
                border-radius: 16px;
                padding: 1rem 1.25rem;
            }}

            .pm-header {{
                border: 1px solid var(--pm-border);
                border-radius: 16px;
                padding: 1rem 1.25rem;
                background: color-mix(in srgb, var(--pm-surface) 90%, var(--pm-bg-a) 10%);
                margin-bottom: 1.5rem;
            }}

            .pm-title {{
                font-size: 1.35rem;
                font-weight: 700;
                letter-spacing: 0.01em;
                margin-left: 0.45rem;
            }}

            .pm-tagline {{
                color: var(--pm-muted);
                font-size: 0.85rem;
                margin-left: 0.5rem;
            }}

            .pm-icon-label i {{
                color: var(--pm-primary);
                margin-right: 0.45rem;
                width: 1rem;
                text-align: center;
            }}

            .pm-stage-current i {{
                color: var(--pm-primary);
            }}

            .pm-stage-done i {{
                color: var(--pm-accent);
            }}

            .pm-stage-pending i {{
                color: var(--pm-muted);
            }}

            .pm-footer {{
                border-top: 1px solid var(--pm-border);
                padding-top: 0.75rem;
                margin-top: 3rem;
                text-align: center;
                color: var(--pm-muted);
                font-size: 0.75rem;
                font-family: var(--pm-mono);
            }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def icon_heading(icon_name: str, label: str, level: int = 3) -> None:
    size = "1.35rem" if level == 2 else "1.1rem"
    st.markdown(
        (
            f"<h{level} class='pm-icon-label' style='font-size:{size};margin:0.2rem 0 0.7rem 0;'>"
            f"{icon_html(icon_name)} {label}"
            f"</h{level}>"
        ),
        unsafe_allow_html=True,
    )


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
    ui = frontend_design.ui
    st.markdown(
        f"""
        <div class="pm-header">
            <span style="font-size:1.45rem;color:var(--pm-primary)">{icon_html("brand")}</span>
            <span class="pm-title">{ui.app_name}</span>
            <span class="pm-tagline">{ui.tagline}</span>
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

    tab_url, tab_text, tab_md = st.tabs(["URL", "Text", "Markdown"])

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

    generate_label = "Generate Podcast" if not use_full else "Generate Podcast (Full Pipeline)"

    st.markdown(
        f"<div class='pm-icon-label'>{icon_text('generate', generate_label)}</div>",
        unsafe_allow_html=True,
    )
    if st.button(
        generate_label,
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

    icon_heading("processing", "Pipeline Running")
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
            css_class = "pm-stage-done"
            marker = icon_html("done")
        elif i == current_index:
            css_class = "pm-stage-current"
            marker = icon_html("current")
        else:
            css_class = "pm-stage-pending"
            marker = icon_html("pending")
        stage_lines.append(f"<div class='{css_class}'>{marker} <span>{label}</span></div>")
    st.markdown("".join(stage_lines), unsafe_allow_html=True)

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
        icon_heading("script", "Podcast Script")
    with col2:
        st.metric("Segments", segment_count)

    # Render dialogue
    lines = [l for l in script.splitlines() if l.strip()]
    for line in lines:
        if line.startswith("HOST_A:"):
            text = line[len("HOST_A:"):].strip()
            with st.chat_message("HOST A", avatar="A"):
                st.write(text)
        elif line.startswith("HOST_B:"):
            text = line[len("HOST_B:"):].strip()
            with st.chat_message("HOST B", avatar="B"):
                st.write(text)
        else:
            st.caption(line.strip())

    st.divider()

    col_audio, col_dl, col_reset = st.columns([2, 2, 1])
    with col_audio:
        st.markdown(
            f"<div class='pm-icon-label'>{icon_text('audio', 'Generate Audio')}</div>",
            unsafe_allow_html=True,
        )
        if st.button("Generate Audio", type="primary"):
            with st.spinner("Starting audio synthesis…"):
                handle_generate_audio()
            st.rerun()
    with col_dl:
        st.markdown(
            f"<div class='pm-icon-label'>{icon_text('download', 'Download Script')}</div>",
            unsafe_allow_html=True,
        )
        st.download_button(
            "Download Script (.txt)",
            data=script,
            file_name=f"script_{st.session_state['job_id'][:8]}.txt",
            mime="text/plain",
        )
    with col_reset:
        st.markdown(
            f"<div class='pm-icon-label'>{icon_text('reset', 'Start Over')}</div>",
            unsafe_allow_html=True,
        )
        if st.button("Start Over"):
            reset_state()
            st.rerun()


def render_audio_view() -> None:
    job_id: str = st.session_state["job_id"]

    st.success("Podcast Ready")
    st.markdown(
        f"<div class='pm-icon-label'>{icon_text('ready', 'Your episode is ready to listen and download.')}</div>",
        unsafe_allow_html=True,
    )

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
        st.markdown(
            f"<div class='pm-icon-label'>{icon_text('download', 'Download MP3')}</div>",
            unsafe_allow_html=True,
        )
        st.download_button(
            "Download MP3",
            data=audio_bytes,
            file_name=f"podcast_{job_id[:8]}.mp3",
            mime="audio/mpeg",
            type="primary",
        )
    with col_reset:
        st.markdown(
            f"<div class='pm-icon-label'>{icon_text('back', 'Generate Another')}</div>",
            unsafe_allow_html=True,
        )
        if st.button("Generate Another"):
            reset_state()
            st.rerun()

    st.caption(f"Job ID: `{job_id}`")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    ui = frontend_design.ui
    st.set_page_config(
        page_title=ui.page_title,
        page_icon=ui.page_icon,
        layout=ui.layout,
    )

    inject_design_css()
    init_state()
    render_header()

    # Global error banner
    if st.session_state.get("error"):
        st.error(st.session_state["error"])
        st.markdown(
            f"<div class='pm-icon-label'>{icon_text('dismiss', 'Dismiss Error')}</div>",
            unsafe_allow_html=True,
        )
        if st.button("Dismiss"):
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
        <div class="pm-footer">
            podcastman v0.1.0 — LiteLLM · LangGraph · Google Cloud TTS · ChromaDB
        </div>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
