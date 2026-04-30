from __future__ import annotations

import os
import shlex
import socket
import subprocess
import time
from urllib.parse import urlparse

import pytest

from .workbench_env import detect_real_workbench, get_rserver_external


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return int(s.getsockname()[1])


def _strip_proxy_prefix(path: str) -> str:
    # Mirror the behavior in the runner: /proxy/<port>/... is not browser-routable.
    parts = (path or "").split("/")
    if len(parts) >= 3 and parts[1] == "proxy" and parts[2].isdigit():
        rest = "/" + "/".join(parts[3:])
        return rest.rstrip("/")
    return (path or "").rstrip("/")


def _wait_for_url(curl_bin: str, url: str, *, timeout_s: float = 15.0) -> None:
    deadline = time.time() + timeout_s
    last_err: str = ""
    while time.time() < deadline:
        try:
            subprocess.check_output(
                [curl_bin, "-skf", url],
                stderr=subprocess.STDOUT,
                text=True,
            )
            return
        except subprocess.CalledProcessError as e:
            last_err = (e.output or "").strip()
            time.sleep(0.2)
    raise AssertionError(f"Server did not become ready: {url}\nLast error:\n{last_err}")


def _curl_args(curl_bin: str) -> list[str]:
    """
    Allow passing auth/cookie headers for real Workbench runs.

    Example:
      WORKBENCH_CURL_ARGS='-H \"Cookie: <cookie>\"'
    """
    extra = (os.environ.get("WORKBENCH_CURL_ARGS") or "").strip()
    return [curl_bin, "-sk"] + (shlex.split(extra) if extra else [])


def _looks_like_workbench_sign_in(body: str) -> bool:
    b = (body or "").lower()
    return ("auth-sign-in" in b) or ("appuri=" in b)


@pytest.mark.e2e
def test_real_workbench_proxy_routing_and_root_path_normalization() -> None:
    info = detect_real_workbench()
    if not info:
        raise pytest.skip.Exception(
            "Not in a real Workbench environment (or missing rserver-url/curl)."
        )

    port = _free_port()
    raw = get_rserver_external(port, rserver_url_bin=info.rserver_url_bin)

    # Determine external base URL + root_path for uvicorn.
    if raw.startswith("http://") or raw.startswith("https://"):
        parsed = urlparse(raw.rstrip("/"))
        external_base = f"{parsed.scheme}://{parsed.netloc}"
        root_path = _strip_proxy_prefix(parsed.path)
        base_for_requests = raw.rstrip("/")
    else:
        # Some setups return only the prefix path.
        root_path = _strip_proxy_prefix(raw)
        external_base = f"http://127.0.0.1:{port}"
        base_for_requests = f"{external_base}{root_path}"

    env = os.environ.copy()
    # Ensure uvicorn uses our root_path; this is what makes swagger/redirects correct.
    cmd = [
        "python",
        "-m",
        "uvicorn",
        "tests.real_workbench_app:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--root-path",
        root_path,
        "--proxy-headers",
        "--forwarded-allow-ips",
        "*",
        "--log-level",
        "warning",
    ]

    proc = subprocess.Popen(
        cmd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        # Wait for server readiness via the *external* Workbench URL.
        ping_url = f"{base_for_requests}/ping"
        _wait_for_url(info.curl_bin, ping_url, timeout_s=25.0)

        # Validate ping response via Workbench proxy.
        out = subprocess.check_output(
            _curl_args(info.curl_bin) + [ping_url], text=True
        ).strip()
        if _looks_like_workbench_sign_in(out):
            raise pytest.skip.Exception(
                "Workbench required interactive sign-in for proxied URL. "
                "Set WORKBENCH_CURL_ARGS (e.g. Cookie/SSO headers) to enable this integration test."
            )
        assert '"ok"' in out

        # Validate that scope root_path is normalized to the browser prefix (not /proxy/<port>/...).
        scope_url = f"{base_for_requests}/scope"
        scope_out = subprocess.check_output(
            _curl_args(info.curl_bin) + [scope_url], text=True
        ).strip()
        if _looks_like_workbench_sign_in(scope_out):
            raise pytest.skip.Exception(
                "Workbench required interactive sign-in for proxied URL. "
                "Set WORKBENCH_CURL_ARGS (e.g. Cookie/SSO headers) to enable this integration test."
            )
        # The response is JSON; we just check expected substrings to avoid extra deps.
        assert f'"root_path":"{root_path}"' in scope_out.replace(" ", "")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
