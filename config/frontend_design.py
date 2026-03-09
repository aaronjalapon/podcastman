"""Frontend design configuration loaded from root config.toml."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tomllib


@dataclass(frozen=True)
class UIConfig:
    page_title: str
    page_icon: str
    app_name: str
    tagline: str
    layout: str


@dataclass(frozen=True)
class ThemeConfig:
    primary_color: str
    accent_color: str
    background_start: str
    background_end: str
    surface_color: str
    text_color: str
    muted_text_color: str
    border_color: str
    font_family: str
    mono_font_family: str


@dataclass(frozen=True)
class FrontendDesign:
    ui: UIConfig
    theme: ThemeConfig
    icons: dict[str, str]


_DEFAULTS = {
    "ui": {
        "page_title": "podcastman - Blog to Podcast",
        "page_icon": "PM",
        "app_name": "podcastman",
        "tagline": "Blog to Podcast with AI",
        "layout": "centered",
    },
    "theme": {
        "primary_color": "#0b5fff",
        "accent_color": "#12b886",
        "background_start": "#f4f8ff",
        "background_end": "#eefaf4",
        "surface_color": "#ffffff",
        "text_color": "#0f172a",
        "muted_text_color": "#5b6472",
        "border_color": "#d6deea",
        "font_family": "'Space Grotesk', 'Segoe UI', sans-serif",
        "mono_font_family": "'IBM Plex Mono', ui-monospace, SFMono-Regular, Menlo, monospace",
    },
    "icons": {
        "brand": "fa-solid fa-microphone-lines",
        "url_tab": "fa-solid fa-link",
        "text_tab": "fa-solid fa-file-lines",
        "markdown_tab": "fa-solid fa-file",
        "generate": "fa-solid fa-wand-magic-sparkles",
        "processing": "fa-solid fa-gears",
        "done": "fa-solid fa-circle-check",
        "current": "fa-solid fa-circle-dot",
        "pending": "fa-regular fa-circle",
        "script": "fa-solid fa-scroll",
        "audio": "fa-solid fa-volume-high",
        "download": "fa-solid fa-download",
        "reset": "fa-solid fa-rotate-left",
        "back": "fa-solid fa-arrow-left",
        "dismiss": "fa-solid fa-xmark",
        "host_a": "fa-solid fa-user",
        "host_b": "fa-solid fa-headphones",
        "ready": "fa-solid fa-party-horn",
    },
}


def _merge_section(defaults: dict[str, str], values: dict[str, object]) -> dict[str, str]:
    merged = dict(defaults)
    for key, value in values.items():
        if isinstance(value, str) and value.strip():
            merged[key] = value
    return merged


def _load_config_toml() -> dict[str, object]:
    root_path = Path(__file__).resolve().parent.parent
    config_path = root_path / "config.toml"
    if not config_path.exists():
        return {}

    try:
        with config_path.open("rb") as file_handle:
            data = tomllib.load(file_handle)
        return data if isinstance(data, dict) else {}
    except tomllib.TOMLDecodeError:
        # Fall back to defaults if the file is malformed.
        return {}


def _section_dict(raw: dict[str, object], section_name: str) -> dict[str, object]:
    section = raw.get(section_name, {})
    if isinstance(section, dict):
        return {str(key): value for key, value in section.items()}
    return {}


def load_frontend_design() -> FrontendDesign:
    raw = _load_config_toml()

    ui_raw = _section_dict(raw, "ui")
    theme_raw = _section_dict(raw, "theme")
    icons_raw = _section_dict(raw, "icons")

    ui_data = _merge_section(_DEFAULTS["ui"], ui_raw)
    theme_data = _merge_section(_DEFAULTS["theme"], theme_raw)
    icons_data = _merge_section(_DEFAULTS["icons"], icons_raw)

    return FrontendDesign(
        ui=UIConfig(**ui_data),
        theme=ThemeConfig(**theme_data),
        icons=icons_data,
    )


frontend_design = load_frontend_design()
