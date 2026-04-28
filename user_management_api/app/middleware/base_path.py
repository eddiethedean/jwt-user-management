from __future__ import annotations

from dataclasses import dataclass

from starlette.types import ASGIApp, Receive, Scope, Send
from urllib.parse import unquote, urlparse
import logging
import os
from typing import Optional
import re


# Use uvicorn's logger so messages reliably appear in uvicorn output.
log = logging.getLogger("uvicorn.error")


def _debug_enabled() -> bool:
    return os.getenv("BASE_PATH_DEBUG", "").lower() in ("1", "true", "yes")


_SAFE_PREFIX_RE = re.compile(r"^(/[A-Za-z0-9._~-]+)*$")


def _sanitize_root_path(root_path: str) -> str:
    rp = (root_path or "").strip()
    if not rp:
        return ""
    # root_path must be a path prefix, never an absolute URL.
    lowered = rp.lower()
    if "://" in lowered or lowered.startswith("http") or lowered.startswith("https"):
        return ""
    if not rp.startswith("/"):
        return ""
    # Collapse any accidental double slashes.
    while "//" in rp:
        rp = rp.replace("//", "/")
    # No trailing slash (except root) so it matches our safe-prefix regex.
    if len(rp) > 1 and rp.endswith("/"):
        rp = rp[:-1]
    # Ensure it still matches our safe prefix rules.
    return rp if _SAFE_PREFIX_RE.fullmatch(rp) else ""


def _normalize_prefix(prefix: str) -> str:
    p = (prefix or "").strip()
    if not p:
        return ""
    if not p.startswith("/"):
        p = "/" + p
    # Reject dangerous prefixes like '//' (scheme-relative) or invalid characters.
    if p.startswith("//") or not _SAFE_PREFIX_RE.fullmatch(p):
        return ""
    # no trailing slash (except root)
    if len(p) > 1 and p.endswith("/"):
        p = p[:-1]
    return p


def _header(scope: Scope, name: bytes) -> Optional[str]:
    headers = dict(scope.get("headers") or [])
    raw = headers.get(name)
    if raw is None:
        return None
    try:
        return raw.decode(errors="replace")
    except Exception:
        return None


def _maybe_decode_workbench_absolute_url(scope: Scope) -> Scope:
    """
    Workbench-style proxies may pass an absolute URL as the request path, either:

    - percent-encoded, e.g. https%3A//workbench.example/s/<service>/p/<project>/admin
    - already decoded, e.g. https://workbench.example/s/<service>/p/<project>/admin

    This normalizes scope["path"] to the real URL path so downstream routing works.
    """
    raw_path = scope.get("path") or ""
    candidate = raw_path.lstrip("/")
    lowered = candidate.lower()
    is_encoded = ("http%3a" in lowered) or ("https%3a" in lowered)
    is_decoded = lowered.startswith("http://") or lowered.startswith("https://")
    if not is_encoded and not is_decoded:
        return scope

    decoded = unquote(candidate) if is_encoded else candidate
    if not (decoded.startswith("http://") or decoded.startswith("https://")):
        return scope

    parsed = urlparse(decoded)
    decoded_path = parsed.path or "/"
    # Some proxies produce paths with double slashes (e.g. "...//admin").
    while "//" in decoded_path:
        decoded_path = decoded_path.replace("//", "/")

    # If the decoded path includes an unknown Workbench prefix, try to auto-detect it by
    # locating the first "real" app route and converting everything before it to root_path.
    # This handles cases where the Workbench proxy prefix changes per session/project.
    # Prefer mounted-app prefixes (we mount backend under /api) so we don't
    # accidentally fold "/api" into root_path_override (which would bypass the mount
    # and cause 404s like path="/admin" on the root app).
    known_route_prefixes = (
        "/api/admin",
        "/api/docs",
        "/api/auth",
        "/api/users",
        "/api/invites",
        "/api/password",
        "/api/static",
        "/admin",
        "/docs",
        "/openapi.json",
        "/redoc",
        "/auth",
        "/users",
        "/invites",
        "/password",
    )
    root_path_override = ""
    for rp in known_route_prefixes:
        idx = decoded_path.find(rp)
        if idx > 0:
            root_path_override = decoded_path[:idx]
            decoded_path = decoded_path[idx:]
            break

    new_scope = dict(scope)
    if root_path_override:
        base_rp = _sanitize_root_path(str(scope.get("root_path") or ""))
        override_rp = _sanitize_root_path(root_path_override)
        if override_rp and not base_rp.endswith(override_rp):
            new_scope["root_path"] = base_rp + override_rp
    new_scope["path"] = decoded_path or "/"
    # Keep raw_path consistent with path for downstream routing/tools.
    new_scope["raw_path"] = (new_scope["path"] or "/").encode()
    new_scope["query_string"] = (parsed.query or "").encode()

    if _debug_enabled():
        log.warning(
            "Decoded absolute URL path from Workbench proxy: raw_path=%r decoded_url=%r parsed_path=%r parsed_query=%r root_path_override=%r final_root_path=%r final_path=%r",
            raw_path,
            decoded,
            parsed.path,
            parsed.query,
            root_path_override,
            new_scope.get("root_path") or "",
            new_scope.get("path") or "",
        )
    return new_scope


@dataclass(frozen=True)
class BasePathMiddleware:
    """
    Support deployments where the app is served under an external base path prefix.

    Example external URL:
      https://host/s/<service>/p/<project>/admin

    Configure BASE_PATH=/s/<service>/p/<project>
    so incoming scope["path"] is stripped before routing while scope["root_path"]
    is set for correct redirect/url generation.
    """

    app: ASGIApp
    base_path: str

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        debug = _debug_enabled()
        if debug and scope["type"] in {"http", "websocket"}:
            # Workbench deployments sometimes filter WARNING logs; emit at INFO when debugging.
            log.info(
                "Incoming scope: type=%s method=%r scheme=%r root_path=%r path=%r raw_path=%r query_string=%r headers_host=%r headers_x_forwarded_proto=%r",
                scope["type"],
                scope.get("method"),
                scope.get("scheme"),
                scope.get("root_path"),
                scope.get("path"),
                scope.get("raw_path"),
                (scope.get("query_string") or b"").decode(errors="replace"),
                dict(scope.get("headers") or [])
                .get(b"host", b"")
                .decode(errors="replace"),
                dict(scope.get("headers") or [])
                .get(b"x-forwarded-proto", b"")
                .decode(errors="replace"),
            )

        scope = _maybe_decode_workbench_absolute_url(scope)
        prefix = _normalize_prefix(self.base_path)

        # Workbench/proxies should only provide a path-like root_path. If it looks like a URL,
        # strip it so redirects don't become malformed.
        root_path_sane = _sanitize_root_path(str(scope.get("root_path") or ""))
        if root_path_sane != (scope.get("root_path") or ""):
            scope = dict(scope)
            scope["root_path"] = root_path_sane

        # Some proxies strip the prefix before proxying but communicate it via
        # X-Forwarded-Prefix. If present, we treat it as an external root_path
        # for URL generation and template base-path injection.
        forwarded_prefix = _normalize_prefix(
            _header(scope, b"x-forwarded-prefix") or ""
        )
        # Avoid applying root_path for static assets; they don't need URL generation
        # and some frameworks behave differently when root_path is non-empty.
        path_for_prefix = scope.get("path") or ""
        should_apply_forwarded_prefix = bool(
            forwarded_prefix
            and path_for_prefix
            and not path_for_prefix.startswith("/static")
        )
        if should_apply_forwarded_prefix and not (
            scope.get("root_path") or ""
        ).endswith(forwarded_prefix):
            scope = dict(scope)
            scope["root_path"] = (scope.get("root_path") or "") + forwarded_prefix
            if debug:
                log.info(
                    "Applied X-Forwarded-Prefix to root_path: forwarded_prefix=%r new_root_path=%r path=%r",
                    forwarded_prefix,
                    scope.get("root_path") or "",
                    scope.get("path") or "",
                )
        if not prefix or scope["type"] not in {"http", "websocket"}:
            await self.app(scope, receive, send)
            return

        path = scope.get("path") or ""
        if path == prefix:
            new_path = "/"
        elif path.startswith(prefix + "/"):
            new_path = path[len(prefix) :]
        elif (scope.get("root_path") or "").endswith(prefix):
            # We may have already moved an external prefix into root_path (auto-detected
            # from an encoded absolute URL). In that case, routing should proceed without
            # additional stripping.
            await self.app(scope, receive, send)
            return
        else:
            await self.app(scope, receive, send)
            return

        new_scope = dict(scope)
        # Avoid duplicating the prefix if Workbench already injected it into root_path.
        current_rp = _sanitize_root_path(str(scope.get("root_path") or ""))
        if current_rp.endswith(prefix):
            new_root_path = current_rp
        else:
            new_root_path = current_rp + prefix
        new_scope["root_path"] = new_root_path
        new_scope["path"] = new_path or "/"
        # Keep raw_path consistent for downstream apps (e.g., StaticFiles).
        new_scope["raw_path"] = (new_scope["path"] or "/").encode()
        if debug:
            log.info(
                "BASE_PATH applied: prefix=%r old_root_path=%r old_path=%r new_root_path=%r new_path=%r",
                prefix,
                scope.get("root_path") or "",
                path,
                new_scope.get("root_path") or "",
                new_scope.get("path") or "",
            )
        await self.app(new_scope, receive, send)
