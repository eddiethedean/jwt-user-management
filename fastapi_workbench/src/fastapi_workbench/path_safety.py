from __future__ import annotations

import posixpath
import re
from typing import Any, Mapping
from urllib.parse import quote, urlparse


_SENSITIVE_QUERY_KEYS = frozenset(
    {"token", "code", "session", "password", "secret", "access_token", "refresh_token"}
)
_TOKENISH_PATH = re.compile(
    r"(^|/)([a-f0-9]{16,}|[A-Za-z0-9_-]{20,})(/|$)", re.IGNORECASE
)


def path_has_parent_segments(path: str) -> bool:
    """True when ``path`` contains ``.`` or ``..`` path segments."""
    raw = (path or "").strip()
    if not raw:
        return False
    for part in raw.split("/"):
        if part in {".", ".."}:
            return True
    normalized = posixpath.normpath(raw.split("?", 1)[0])
    return normalized.startswith("..") or "/../" in f"/{normalized}"


def normalize_safe_path(
    dest: str, *, allow_parent_segments: bool = False
) -> str | None:
    """
    Return a safe app-absolute path (leading ``/``) or None if unsafe.

    Rejects protocol-relative and off-site URLs. Rejects ``..`` unless opted in.
    """
    raw = (dest or "").strip()
    if not raw:
        return "/"
    if raw.startswith("//"):
        return None
    if "://" in raw.split("/", 1)[0]:
        return None

    if raw.startswith("../") or raw == "..":
        if not allow_parent_segments:
            return None
        return raw

    if not raw.startswith("/"):
        if allow_parent_segments and raw.startswith("../"):
            return raw
        return None

    if path_has_parent_segments(raw) and not allow_parent_segments:
        return None

    path_only = raw.split("?", 1)[0]
    normalized = posixpath.normpath(path_only)
    if normalized == ".":
        normalized = "/"
    elif not normalized.startswith("/"):
        normalized = "/" + normalized

    if path_has_parent_segments(normalized) and not allow_parent_segments:
        return None

    if "?" in raw:
        return normalized + "?" + raw.split("?", 1)[1]
    return normalized


def safe_url_path(path: str) -> str:
    """Normalize a URL path for external link builders; drop ``..`` traversal."""
    raw = (path or "").strip()
    if not raw:
        return "/"
    query = ""
    if "?" in raw:
        path_part, _, q = raw.partition("?")
        query = "?" + q
    else:
        path_part = raw
    if path_has_parent_segments(path_part):
        return "/" + query
    if not path_part.startswith("/"):
        path_part = "/" + path_part
    normalized = posixpath.normpath(path_part)
    if normalized == ".":
        normalized = "/"
    elif not normalized.startswith("/"):
        normalized = "/" + normalized
    return normalized + query


def path_segments(path: str) -> list[str]:
    return [p for p in (path or "").rstrip("/").split("/") if p]


def public_base_includes_mount(wb: str, bp: str) -> bool:
    """True when the public base URL path already ends with mount ``bp`` segments."""
    bp_norm = (bp or "").strip().rstrip("/")
    if not bp_norm:
        return True
    try:
        wb_path = urlparse(wb).path.rstrip("/")
    except Exception:
        return False
    wb_segs = path_segments(wb_path)
    bp_segs = path_segments(bp_norm)
    if len(wb_segs) < len(bp_segs):
        return False
    return wb_segs[-len(bp_segs) :] == bp_segs


def join_public_base_and_mount(base: str, mount: str) -> str:
    b = base.rstrip("/")
    m = (mount or "").strip().rstrip("/")
    if not m:
        return b
    if public_base_includes_mount(b, m):
        return b
    return f"{b}{m}" if m.startswith("/") else f"{b}/{m}"


def encode_raw_path(path: str) -> bytes:
    return quote(path, safe="/:@!$&'()*+,;=").encode("utf-8")


def workbench_mount_redirect_url(root_path: str, safe_path: str) -> str:
    """
    Host-absolute redirect under the Workbench mount (``root_path``).

    Prefer this over depth-based ``../`` relatives when ``root_path`` is known:
    partial path normalization can leave ``scope['path']`` shorter than the browser
    URL, which drops path segments (e.g. ``/p/<project>``) from ``../`` redirects.
    """
    mount = (root_path or "").rstrip("/")
    if safe_path == "/":
        return mount or "/"
    if not mount:
        return safe_path
    return f"{mount}{safe_path}"


def workbench_relative_redirect_url(request_path: str, safe_path: str) -> str:
    """
    Build a proxy-relative redirect target rooted at the app mount, not the
    current URL depth.
    """
    if safe_path == "/":
        return "."
    if safe_path.startswith("../"):
        return safe_path.lstrip("/")

    current = str(request_path or "/")
    segments = path_segments(current)
    ups = "../" * len(segments)
    target = safe_path.lstrip("/")
    if not ups:
        return target or "."
    return f"{ups}{target}"


def redact_scope_for_log(scope: Mapping[str, Any]) -> dict[str, Any]:
    path = str(scope.get("path") or "")
    if _TOKENISH_PATH.search(path):
        path = _TOKENISH_PATH.sub(r"\1<redacted>\3", path)

    raw = scope.get("raw_path")
    raw_display: str | bytes = raw if raw is not None else b""
    if isinstance(raw_display, bytes):
        raw_text = raw_display.decode(errors="replace")
        if _TOKENISH_PATH.search(raw_text):
            raw_display = _TOKENISH_PATH.sub(r"\1<redacted>\3", raw_text).encode()

    qs = (scope.get("query_string") or b"").decode(errors="replace")
    if qs:
        parts = []
        for piece in qs.split("&"):
            key = piece.split("=", 1)[0].lower()
            if key in _SENSITIVE_QUERY_KEYS or "token" in key:
                parts.append(f"{piece.split('=', 1)[0]}=<redacted>")
            else:
                parts.append(piece)
        qs = "&".join(parts)

    return {
        "method": scope.get("method"),
        "root_path": scope.get("root_path"),
        "path": path,
        "raw_path": raw_display,
        "query_string": qs,
    }
