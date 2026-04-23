from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Optional

import httpx


def _pick_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@dataclass
class StreamlitSubprocess:
    process: subprocess.Popen
    port: int
    log_file: Optional[IO[str]] = None


_STATE: Optional[StreamlitSubprocess] = None


@dataclass(frozen=True)
class StreamlitAdminRunner:
    repo_root: Path
    base_path: str = "admin"

    def script_path(self) -> Path:
        return self.repo_root / "user_management_api" / "admin_ui" / "app.py"

    def pick_port(self) -> int:
        return int(os.getenv("ADMIN_UI_INTERNAL_PORT") or 0) or _pick_free_port()

    def build_env(self, *, backend_url: str) -> dict[str, str]:
        env = os.environ.copy()
        env["BACKEND_URL"] = backend_url.rstrip("/")
        env["PYTHONPATH"] = str(self.repo_root) + (
            os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""
        )
        return env

    def build_cmd(self, *, port: int) -> list[str]:
        script_path = self.script_path()
        return [
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
            self.base_path.lstrip("/"),
        ]

    def open_log(self) -> Optional[IO[str]]:
        log_path = os.getenv("ADMIN_UI_LOG_FILE") or str(
            self.repo_root / "admin.nohup.log"
        )
        try:
            return open(log_path, "a", encoding="utf-8")
        except OSError:
            return None

    def wait_ready(self, *, port: int, proc: subprocess.Popen) -> None:
        wait_s = float(os.getenv("ADMIN_UI_READY_WAIT_S") or 0) or 0.0
        if wait_s <= 0:
            return
        deadline = time.time() + wait_s
        url = f"http://127.0.0.1:{port}/{self.base_path.lstrip('/')}/_stcore/health"
        while time.time() < deadline and proc.poll() is None:
            try:
                r = httpx.get(url, timeout=1.0, follow_redirects=False)
                if r.status_code == 200:
                    break
            except Exception:
                pass
            time.sleep(0.1)

    def start(self, *, backend_url: str) -> StreamlitSubprocess:
        script_path = self.script_path()
        if not script_path.exists():
            raise FileNotFoundError(
                f"Streamlit admin entrypoint not found: {script_path}"
            )

        port = self.pick_port()
        env = self.build_env(backend_url=backend_url)
        cmd = self.build_cmd(port=port)

        log_fp = self.open_log()
        proc = subprocess.Popen(
            cmd,
            cwd=str(self.repo_root),
            env=env,
            stdout=log_fp or subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
            text=True if log_fp else False,
        )
        self.wait_ready(port=port, proc=proc)
        return StreamlitSubprocess(process=proc, port=port, log_file=log_fp)

    def stop(self, state: StreamlitSubprocess) -> None:
        proc = state.process
        log_fp = state.log_file

        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

        if log_fp:
            try:
                log_fp.close()
            except Exception:
                pass


def start_streamlit_admin(
    *, backend_url: str, base_path: str = "admin"
) -> StreamlitSubprocess:
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
    runner = StreamlitAdminRunner(repo_root=repo_root, base_path=base_path)
    _STATE = runner.start(backend_url=backend_url)
    return _STATE


def stop_streamlit_admin() -> None:
    global _STATE  # noqa: PLW0603
    if not _STATE:
        return
    state = _STATE
    _STATE = None
    runner = StreamlitAdminRunner(repo_root=Path(__file__).resolve().parents[2])
    runner.stop(state)
