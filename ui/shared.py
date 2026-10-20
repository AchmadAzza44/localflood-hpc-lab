"""Reusable Streamlit helpers and styling."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from common.config import SAMPLES_DIR, ensure_runtime_dirs

CSS = """
<style>
    .block-container {padding-top: 2rem; padding-bottom: 3rem; max-width: 1200px;}
    .app-hero {
        background: linear-gradient(120deg, #0B3D4F 0%, #12708C 60%, #1F9BB8 100%);
        color: #F7FAFC; padding: 1.6rem 1.8rem; border-radius: 14px; margin-bottom: 1.2rem;
    }
    .app-hero h1 {color: #FFFFFF; margin: 0 0 .35rem 0; font-size: 1.9rem;}
    .app-hero p {margin: 0; opacity: .92; font-size: .98rem;}
    .metric-card {
        background: #F4F8FA; border: 1px solid #D8E4EA; border-radius: 12px;
        padding: .9rem 1rem; height: 100%;
    }
    .metric-card .label {font-size: .78rem; color: #5A6B7B; text-transform: uppercase; letter-spacing: .04em;}
    .metric-card .value {font-size: 1.5rem; font-weight: 700; color: #0B3D4F;}
    .metric-card .hint {font-size: .78rem; color: #6B7C8F;}
    .notice {
        border-left: 4px solid #D68910; background: #FFF8EC; padding: .75rem 1rem;
        border-radius: 6px; font-size: .88rem; color: #6E4A00; margin: .6rem 0;
    }
    .notice.info {border-left-color: #12708C; background: #EFF7FA; color: #0B3D4F;}
    .notice.danger {border-left-color: #C0392B; background: #FDEDEB; color: #7B241C;}
    .step-pill {
        display: inline-block; background: #E3EEF2; color: #0B3D4F; border-radius: 999px;
        padding: .18rem .7rem; font-size: .75rem; font-weight: 600; margin-bottom: .4rem;
    }
    footer {visibility: hidden;}
    #MainMenu {visibility: hidden;}
</style>
"""


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def hero(title: str, subtitle: str) -> None:
    st.markdown(
        f'<div class="app-hero"><h1>{title}</h1><p>{subtitle}</p></div>',
        unsafe_allow_html=True,
    )


def metric_card(label: str, value: str, hint: str = "") -> str:
    return (
        f'<div class="metric-card"><div class="label">{label}</div>'
        f'<div class="value">{value}</div><div class="hint">{hint}</div></div>'
    )


def notice(text: str, kind: str = "info") -> None:
    st.markdown(f'<div class="notice {kind}">{text}</div>', unsafe_allow_html=True)


def step_label(text: str) -> None:
    st.markdown(f'<span class="step-pill">{text}</span>', unsafe_allow_html=True)


def sample_files(
    extension: str | None = None,
    exclude: set[str] | None = None,
) -> list[Path]:
    ensure_runtime_dirs()
    if not SAMPLES_DIR.exists():
        return []
    files = sorted(SAMPLES_DIR.glob("*"))
    if extension:
        files = [path for path in files if path.suffix.lower() == extension]
    if exclude:
        files = [path for path in files if path.name not in exclude]
    return [path for path in files if path.is_file()]


def download_row(
    items: list[tuple[str, bytes, str, str]],
    key_prefix: str = "download",
) -> None:
    """Render a row of download buttons: (label, payload, filename, mime)."""
    columns = st.columns(len(items))
    for index, (column, (label, payload, filename, mime)) in enumerate(zip(columns, items)):
        with column:
            st.download_button(
                label,
                data=payload,
                file_name=filename,
                mime=mime,
                width="stretch",
                key=f"{key_prefix}-{index}-{filename}",
            )


def show_json(payload: dict, label: str = "Konfigurasi") -> None:
    with st.expander(label):
        st.json(payload, expanded=False)


def format_number(value: float | int | None, digits: int = 2, suffix: str = "") -> str:
    if value is None:
        return "-"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    return f"{number:,.{digits}f}{suffix}"
