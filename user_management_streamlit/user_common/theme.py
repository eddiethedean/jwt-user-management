"""Visual theme aligned with ``user_management_api`` archived HTML UI (``base.html``)."""

from __future__ import annotations

import streamlit as st

# Design tokens and Streamlit overrides derived from
# ``user_management_api/app/web/archive/templates/base.html``.
UM_THEME_CSS = """
<style>
  :root {
    --um-bg: #0b1020;
    --um-panel: rgba(255, 255, 255, 0.06);
    --um-panel-strong: rgba(255, 255, 255, 0.1);
    --um-fg: rgba(255, 255, 255, 0.92);
    --um-muted: rgba(255, 255, 255, 0.72);
    --um-border: rgba(255, 255, 255, 0.14);
    --um-accent: #7c7cff;
    --um-accent-2: #22c55e;
    --um-danger: #fb7185;
    --um-radius: 14px;
    --um-radius-sm: 10px;
    --um-shadow: 0 10px 30px rgba(0, 0, 0, 0.35);
  }
  @media (prefers-color-scheme: light) {
    :root {
      --um-bg: #f6f7fb;
      --um-panel: rgba(255, 255, 255, 0.9);
      --um-panel-strong: rgba(255, 255, 255, 1);
      --um-fg: rgba(9, 10, 18, 0.92);
      --um-muted: rgba(9, 10, 18, 0.64);
      --um-border: rgba(9, 10, 18, 0.12);
      --um-accent: #4f46e5;
      --um-accent-2: #16a34a;
      --um-danger: #e11d48;
      --um-shadow: 0 10px 30px rgba(16, 24, 40, 0.12);
    }
  }

  .stApp {
    color: var(--um-fg);
    background: radial-gradient(1200px 600px at 20% -10%, rgba(124, 124, 255, 0.25), transparent 60%),
                radial-gradient(800px 500px at 90% 10%, rgba(34, 197, 94, 0.18), transparent 55%),
                var(--um-bg) !important;
  }

  section.main > div {
    max-width: 860px !important;
    margin-left: auto !important;
    margin-right: auto !important;
    padding-top: 1.25rem !important;
    padding-bottom: 3rem !important;
  }

  header[data-testid="stHeader"] {
    background: transparent !important;
  }
  [data-testid="stToolbar"] { display: none !important; }

  [data-testid="stSidebar"] {
    background: color-mix(in srgb, var(--um-panel-strong) 55%, transparent) !important;
    border-right: 1px solid var(--um-border) !important;
    backdrop-filter: blur(10px);
  }
  [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
  [data-testid="stSidebar"] .stMarkdown { color: var(--um-fg); }

  [data-testid="stSidebar"] .stButton > button {
    width: 100%;
    border-radius: 999px !important;
    border: 1px solid var(--um-border) !important;
    font-weight: 650 !important;
    background: transparent !important;
    color: var(--um-fg) !important;
  }
  [data-testid="stSidebar"] .stButton > button:hover {
    border-color: color-mix(in srgb, var(--um-accent) 45%, var(--um-border)) !important;
    background: color-mix(in srgb, var(--um-accent) 12%, transparent) !important;
  }
  [data-testid="stSidebar"] .stButton > button[kind="primary"] {
    background: color-mix(in srgb, var(--um-accent) 22%, var(--um-panel-strong)) !important;
    border-color: color-mix(in srgb, var(--um-accent) 55%, var(--um-border)) !important;
  }

  /* Public nav radio: pill group */
  [data-testid="stMain"] div[data-testid="stRadio"] > label > div:first-child {
    background: color-mix(in srgb, var(--um-panel-strong) 65%, transparent) !important;
    border: 1px solid var(--um-border) !important;
    border-radius: 999px !important;
    padding: 6px !important;
    gap: 6px !important;
  }

  [data-baseweb="radio"] label {
    color: var(--um-fg) !important;
    font-weight: 650 !important;
    font-size: 0.8125rem !important;
  }

  [data-testid="stExpander"] {
    border: 1px solid var(--um-border) !important;
    border-radius: var(--um-radius-sm) !important;
    background: var(--um-panel) !important;
  }

  [data-testid="stAlert"] {
    border-radius: var(--um-radius-sm) !important;
    border: 1px solid var(--um-border) !important;
  }

  .um-topbar {
    display: flex;
    flex-direction: column;
    gap: 14px;
    margin-bottom: 18px;
  }
  .um-brandTop {
    display: flex;
    align-items: baseline;
    gap: 10px;
    flex-wrap: wrap;
  }
  .um-brandTitle {
    font-weight: 950;
    letter-spacing: -0.03em;
    font-size: 1.125rem;
    line-height: 1.1;
    color: var(--um-fg);
  }
  .um-brandTag {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 5px 10px;
    border-radius: 999px;
    border: 1px solid var(--um-border);
    background: color-mix(in srgb, var(--um-panel-strong) 65%, transparent);
    font-size: 12px;
    font-weight: 800;
    color: color-mix(in srgb, var(--um-fg) 92%, transparent);
  }
  .um-brandTagDot {
    width: 8px;
    height: 8px;
    border-radius: 999px;
    background: color-mix(in srgb, var(--um-accent) 85%, transparent);
    display: inline-block;
  }
  .um-brandSub {
    color: var(--um-muted);
    font-size: 13px;
    max-width: 54ch;
    margin: 0;
    line-height: 1.45;
  }
  .um-brandStack {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
    margin-top: 6px;
  }
  .um-stackPill {
    display: inline-flex;
    align-items: center;
    padding: 5px 9px;
    border-radius: 999px;
    border: 1px solid var(--um-border);
    background: color-mix(in srgb, var(--um-panel-strong) 55%, transparent);
    font-size: 12px;
    font-weight: 700;
    color: color-mix(in srgb, var(--um-fg) 90%, transparent);
  }

  .um-sessionRow {
    display: flex;
    justify-content: flex-end;
    margin: 4px 0 14px;
  }
  .um-sessionPill {
    display: inline-flex;
    align-items: stretch;
    border-radius: 999px;
    border: 1px solid var(--um-border);
    background: color-mix(in srgb, var(--um-panel-strong) 65%, transparent);
    overflow: hidden;
    box-shadow: 0 10px 24px rgba(0, 0, 0, 0.18);
    backdrop-filter: blur(10px);
  }
  .um-sessionPill__label {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 8px 12px;
    font-size: 13px;
    font-weight: 650;
    color: color-mix(in srgb, var(--um-fg) 92%, transparent);
  }
  .um-sessionPill__dot {
    width: 8px;
    height: 8px;
    border-radius: 999px;
    background: color-mix(in srgb, var(--um-accent) 85%, transparent);
  }
  .um-sessionPill code {
    background: color-mix(in srgb, var(--um-panel-strong) 92%, transparent);
    border: 1px solid var(--um-border);
    border-radius: 6px;
    padding: 1px 6px;
    font-size: 12px;
  }

  .um-cardHint {
    color: var(--um-muted);
    font-size: 13px;
    margin: 0 0 8px;
    line-height: 1.45;
  }
  .um-kvGrid {
    display: grid;
    grid-template-columns: 160px 1fr;
    gap: 10px 14px;
    align-items: start;
    margin-top: 10px;
  }
  @media (max-width: 700px) {
    .um-kvGrid { grid-template-columns: 1fr; }
  }
  .um-kvKey {
    color: var(--um-muted);
    font-size: 12px;
    font-weight: 750;
    text-transform: uppercase;
    letter-spacing: 0.02em;
  }
  .um-kvVal { min-width: 0; font-size: 14px; }
  .um-kvVal code {
    background: color-mix(in srgb, var(--um-panel-strong) 92%, transparent);
    border: 1px solid var(--um-border);
    border-radius: 6px;
    padding: 2px 6px;
    font-size: 13px;
  }

  .um-panel {
    border: 1px solid var(--um-border);
    background: color-mix(in srgb, var(--um-panel-strong) 65%, transparent);
    border-radius: var(--um-radius);
    padding: 14px 16px;
    margin-top: 12px;
    box-shadow: var(--um-shadow);
  }
  .um-panelHead {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    gap: 12px;
    flex-wrap: wrap;
    margin-bottom: 4px;
  }
  .um-panelHead h3 {
    margin: 0;
    font-size: 1rem;
    letter-spacing: -0.02em;
    color: var(--um-fg);
  }
  .um-muted { color: var(--um-muted); font-size: 13px; }

  div[data-testid="stVerticalBlockBorderWrapper"] {
    border: 1px solid var(--um-border) !important;
    border-radius: var(--um-radius) !important;
    background: var(--um-panel) !important;
    box-shadow: var(--um-shadow) !important;
    backdrop-filter: blur(10px);
    padding: 8px 12px 14px !important;
  }
</style>
"""


def apply_um_theme() -> None:
    st.markdown(UM_THEME_CSS, unsafe_allow_html=True)
