import argparse
import os
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urljoin

import requests


def _norm_prefix(p: str) -> str:
    p = (p or "").strip()
    if not p:
        return ""
    if not p.startswith("/"):
        p = "/" + p
    if len(p) > 1 and p.endswith("/"):
        p = p[:-1]
    return p


_PATH_RE = re.compile(r"(?i)(;\s*path=)/(?=(;|$))")


def _rewrite_cookie_path(set_cookie: str, prefix: str) -> str:
    """
    Mimic nginx `proxy_cookie_path / "<prefix>/";` but only for cookies that
    explicitly have Path=/.
    """
    prefix = _norm_prefix(prefix)
    if not prefix:
        return set_cookie
    return _PATH_RE.sub(rf"\\1{prefix}/", set_cookie)


class _ProxyHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self):  # noqa: N802
        self._handle()

    def do_POST(self):  # noqa: N802
        self._handle()

    def do_PUT(self):  # noqa: N802
        self._handle()

    def do_PATCH(self):  # noqa: N802
        self._handle()

    def do_DELETE(self):  # noqa: N802
        self._handle()

    def do_OPTIONS(self):  # noqa: N802
        self._handle()

    def _handle(self) -> None:
        cfg = getattr(self.server, "cfg")
        raw_path = self.path

        upstream_path = raw_path
        if cfg["prefix"] and (
            cfg["mode"] == "strip"
            or (
                cfg["mode"] == "preserve"
                and upstream_path.startswith(cfg["prefix"] + "/static/")
            )
        ):
            if upstream_path.startswith(cfg["prefix"] + "/"):
                upstream_path = upstream_path[len(cfg["prefix"]) :]
            elif upstream_path == cfg["prefix"]:
                upstream_path = "/"

        upstream_url = urljoin(
            cfg["upstream_base"].rstrip("/") + "/", upstream_path.lstrip("/")
        )

        # Read request body if present
        body = None
        if "content-length" in self.headers:
            try:
                n = int(self.headers.get("content-length") or "0")
            except ValueError:
                n = 0
            if n > 0:
                body = self.rfile.read(n)

        headers = dict(self.headers.items())
        headers.pop("Host", None)
        headers["X-Forwarded-Proto"] = cfg["scheme"]
        headers["X-Forwarded-Host"] = cfg["host"]
        headers["X-Forwarded-Port"] = str(cfg["port"])
        if cfg["mode"] == "strip" and cfg["prefix"]:
            headers["X-Forwarded-Prefix"] = cfg["prefix"]

        resp = requests.request(
            method=self.command,
            url=upstream_url,
            headers=headers,
            data=body,
            allow_redirects=False,
            stream=True,
            timeout=30,
        )

        # Rewrite Location for strip mode so browser stays under prefix.
        location = resp.headers.get("Location")
        if location and cfg["prefix"]:
            external_base = (
                f"{cfg['scheme']}://{cfg['host']}:{cfg['port']}{cfg['prefix']}"
            )
            upstream_base = cfg["upstream_base"].rstrip("/")
            if location.startswith(upstream_base + "/"):
                location = external_base + location[len(upstream_base) :]
            if location.startswith("/") and not location.startswith(
                cfg["prefix"] + "/"
            ):
                location = cfg["prefix"] + location

        self.send_response(resp.status_code)

        # Copy headers (excluding hop-by-hop)
        hop_by_hop = {
            "connection",
            "keep-alive",
            "proxy-authenticate",
            "proxy-authorization",
            "te",
            "trailers",
            "transfer-encoding",
            "upgrade",
        }

        # requests collapses multiple Set-Cookie headers into a single value in resp.headers.
        # Preserve all Set-Cookie values by reading from the underlying raw headers.
        raw_set_cookies = []
        try:
            raw_set_cookies = resp.raw.headers.get_all("Set-Cookie")  # type: ignore[attr-defined]
        except Exception:
            raw = resp.headers.get("Set-Cookie")
            if raw:
                raw_set_cookies = [raw]

        for v in raw_set_cookies:
            if cfg["prefix"]:
                v = _rewrite_cookie_path(v, cfg["prefix"])
            self.send_header("Set-Cookie", v)

        for k, v in resp.headers.items():
            if k.lower() in hop_by_hop:
                continue
            if k.lower() == "location" and location is not None:
                self.send_header("Location", location)
                continue
            if k.lower() == "set-cookie":
                # Already handled above (preserving multi Set-Cookie).
                continue
            self.send_header(k, v)
        self.end_headers()

        for chunk in resp.iter_content(chunk_size=64 * 1024):
            if chunk:
                self.wfile.write(chunk)

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        if os.getenv("E2E_PROXY_DEBUG"):
            super().log_message(format, *args)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--listen-host", default="127.0.0.1")
    ap.add_argument("--listen-port", type=int, required=True)
    ap.add_argument("--upstream", required=True)  # e.g. http://127.0.0.1:8000
    ap.add_argument("--prefix", default="/connect/app")
    ap.add_argument("--mode", choices=["preserve", "strip"], default="preserve")
    args = ap.parse_args()

    prefix = _norm_prefix(args.prefix)
    cfg = {
        "upstream_base": args.upstream,
        "prefix": prefix,
        "mode": args.mode,
        "scheme": "http",
        "host": "localhost",
        "port": args.listen_port,
    }

    httpd = ThreadingHTTPServer((args.listen_host, args.listen_port), _ProxyHandler)
    setattr(httpd, "cfg", cfg)

    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    t.join()


if __name__ == "__main__":
    main()
