"""Branding helpers (parity with ``user_management_api`` HTML ``base.html``)."""

from __future__ import annotations

import html
from typing import Any


def _ui_settings() -> Any:
    from app.core.config import settings

    return settings


def render_brand(st: Any) -> None:
    s = _ui_settings()
    title = html.escape(
        str(getattr(s, "app_title", "User Management") or "User Management")
    )
    tag = html.escape(str(getattr(s, "brand_tag", "") or "").strip())
    tag_title = html.escape(
        str(
            getattr(s, "brand_tag_title", "") or getattr(s, "brand_tag", "") or ""
        ).strip()
    )
    stack = getattr(s, "brand_stack", ()) or ()
    pills = "".join(
        f'<span class="um-stackPill">{html.escape(str(x))}</span>'
        for x in stack
        if str(x).strip()
    )
    tag_html = ""
    if tag:
        tag_html = (
            f'<span class="um-brandTag" title="{tag_title}">'
            f'<span class="um-brandTagDot" aria-hidden="true"></span>{tag}</span>'
        )
    st.markdown(
        f"""
<div class="um-topbar" aria-label="Brand">
  <div class="um-brand">
    <div class="um-brandTop">
      <span class="um-brandTitle">{title}</span>
      {tag_html}
    </div>
    <p class="um-brandSub">A minimal, browser-friendly user system with login, invites, and admin tools.</p>
    <div class="um-brandStack" aria-label="Stack">{pills}</div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )


def render_session_pill(st: Any, *, email: str) -> None:
    safe = html.escape(email or "")
    st.markdown(
        f"""
<div class="um-sessionRow" aria-label="Session">
  <div class="um-sessionPill">
    <div class="um-sessionPill__label">
      <span class="um-sessionPill__dot" aria-hidden="true"></span>
      <span>Signed in as <code>{safe}</code></span>
    </div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )


def self_registration_enabled() -> bool:
    return bool(getattr(_ui_settings(), "self_registration_enabled", True))


def configured_user_roles() -> tuple[str, ...]:
    return tuple(getattr(_ui_settings(), "user_roles", ()) or ())
