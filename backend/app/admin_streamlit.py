from __future__ import annotations

import os
import socket
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


def _pick_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@dataclass
class StreamlitSubprocess:
    process: subprocess.Popen
    port: int


_STATE: Optional[StreamlitSubprocess] = None


def start_streamlit_admin(*, backend_url: str, base_path: str = "admin") -> StreamlitSubprocess:
    """
    Start the Streamlit admin app as a local subprocess and return its port.

    Notes:
    - Streamlit is configured with `server.baseUrlPath` so that it can be reverse-proxied
      under `/{base_path}` by the FastAPI backend.
    - This subprocess is intended to be managed by FastAPI lifespan startup/shutdown.
    """
    global _STATE  # noqa: PLW0603
    if _STATE and _STATE.process.poll() is None:
        return _STATE

    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "streamlit_admin" / "app.py"
    if not script_path.exists():
        raise FileNotFoundError(f"Streamlit admin entrypoint not found: {script_path}")

    port = int(os.getenv("ADMIN_UI_INTERNAL_PORT") or 0) or _pick_free_port()

    env = os.environ.copy()
    # Streamlit admin makes server-side HTTP calls; point it at this backend.
    env["BACKEND_URL"] = backend_url.rstrip("/")

    # Ensure repo root is importable for `streamlit_common` imports.
    env["PYTHONPATH"] = (
        str(repo_root)
        + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    )

    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(script_path),
        "--server.headless",
        "true",
        "--server.address",
        "127.0.0.1",
        "--server.port",
        str(port),
        "--server.fileWatcherType",
        "none",
        "--server.baseUrlPath",
        base_path.lstrip("/"),
    ]

    proc = subprocess.Popen(
        cmd,
        cwd=str(repo_root),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    _STATE = StreamlitSubprocess(process=proc, port=port)
    return _STATE


def stop_streamlit_admin() -> None:
    global _STATE  # noqa: PLW0603
    if not _STATE:
        return
    proc = _STATE.process
    _STATE = None
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
