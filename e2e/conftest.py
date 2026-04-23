import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest
import requests


REPO_ROOT = Path(__file__).resolve().parents[1]


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _wait_http_ok(url: str, *, timeout_s: float = 30.0) -> None:
    deadline = time.time() + timeout_s
    last_err = None
    while time.time() < deadline:
        try:
            r = requests.get(url, timeout=2)
            if r.status_code < 500:
                return
        except Exception as e:  # noqa: BLE001
            last_err = e
        time.sleep(0.25)
    raise RuntimeError(f"Timed out waiting for {url} (last_err={last_err})")


def _tail(proc: subprocess.Popen, *, max_lines: int = 200) -> str:
    try:
        if proc.stdout is None:
            return ""
        # Read whatever is available without blocking too long.
        proc.stdout.flush()
        data = proc.stdout.read()  # type: ignore[arg-type]
        if not data:
            return ""
        lines = str(data).splitlines()
        return "\n".join(lines[-max_lines:])
    except Exception:
        return ""


@pytest.fixture(scope="session")
def ports():
    return {
        "backend": _free_port(),
        "admin": _free_port(),
        "user": _free_port(),
    }


@pytest.fixture(scope="session")
def admin_credentials():
    # E2E creates a backend admin user with these credentials.
    return {"email": "admin@example.com", "password": "admin123"}


@pytest.fixture(scope="session")
def backend_admin_api_key():
    # Matches the env we pass to backend and Streamlit admin.
    return "e2e-admin-key-please-change"


@pytest.fixture(scope="session")
def app_urls(ports):
    return {
        "backend": f"http://127.0.0.1:{ports['backend']}",
        "admin": f"http://127.0.0.1:{ports['admin']}",
        "user": f"http://127.0.0.1:{ports['user']}",
    }


@pytest.fixture(scope="session", autouse=True)
def run_apps(ports, admin_credentials, backend_admin_api_key):
    """
    Start backend + two Streamlit apps once per test session.
    """
    backend_port = str(ports["backend"])
    admin_port = str(ports["admin"])
    user_port = str(ports["user"])

    env_backend = os.environ.copy()
    env_backend.update(
        {
            "ENVIRONMENT": "dev",
            "DATABASE_URL": f"sqlite:///{(REPO_ROOT / 'e2e' / 'e2e.db').as_posix()}",
            "PUBLIC_BASE_URL": f"http://127.0.0.1:{backend_port}",
            "JWT_SECRET": "e2e-secret-e2e-secret-e2e-secret-1234",
            "JWT_ALGORITHM": "HS256",
            "JWT_EXPIRES_MINUTES": "60",
            "ADMIN_API_KEY": backend_admin_api_key,
            "RATE_LIMIT_ENABLED": "false",
        }
    )

    # Apply migrations.
    subprocess.check_call(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=str(REPO_ROOT / "user_management_api"),
        env=env_backend,
    )

    backend = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--port",
            backend_port,
        ],
        cwd=str(REPO_ROOT / "user_management_api"),
        env=env_backend,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    # Wait for backend, then seed an admin user for the admin Streamlit app to login with.
    _wait_http_ok(f"http://127.0.0.1:{backend_port}/docs", timeout_s=45)
    admin_email = admin_credentials["email"]
    admin_password = admin_credentials["password"]
    r_seed = requests.post(
        f"http://127.0.0.1:{backend_port}/users",
        headers={"X-Admin-Api-Key": backend_admin_api_key},
        json={
            "email": admin_email,
            "full_name": "E2E Admin",
            "password": admin_password,
            "is_admin": True,
            "permissions": ["admin"],
        },
        timeout=10,
    )
    if r_seed.status_code not in (200, 409):
        raise RuntimeError(f"seed admin failed: {r_seed.status_code} {r_seed.text}")

    env_admin = os.environ.copy()
    env_admin.update(
        {
            "BACKEND_URL": f"http://127.0.0.1:{backend_port}",
            "BACKEND_ADMIN_API_KEY": backend_admin_api_key,
            "STREAMLIT_TEST_MODE": "",
            "DEBUG": "false",
        }
    )

    admin = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            "app.py",
            "--server.port",
            admin_port,
            "--server.headless",
            "true",
            "--server.fileWatcherType",
            "none",
        ],
        cwd=str(REPO_ROOT / "user_management_api" / "admin_ui"),
        env=env_admin,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    env_user = os.environ.copy()
    env_user.update(
        {
            "BACKEND_URL": f"http://127.0.0.1:{backend_port}",
            "STREAMLIT_TEST_MODE": "",
            "DEBUG": "false",
        }
    )

    user = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            "app.py",
            "--server.port",
            user_port,
            "--server.headless",
            "true",
            "--server.fileWatcherType",
            "none",
        ],
        cwd=str(REPO_ROOT / "streamlit_user"),
        env=env_user,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    try:
        _wait_http_ok(f"http://127.0.0.1:{admin_port}/", timeout_s=45)
        _wait_http_ok(f"http://127.0.0.1:{user_port}/", timeout_s=45)

        for name, proc in [("backend", backend), ("admin", admin), ("user", user)]:
            if proc.poll() is not None:
                raise RuntimeError(f"{name} process exited early.\n{_tail(proc)}")
        yield
    finally:
        for p in (user, admin, backend):
            if p.poll() is None:
                p.terminate()
        # Best-effort drain and kill.
        time.sleep(0.5)
        for p in (user, admin, backend):
            if p.poll() is None:
                p.kill()


@pytest.fixture
def create_backend_user(app_urls, backend_admin_api_key):
    """
    Helper to create a backend user via admin API key.
    """

    def _create(email: str, password: str):
        r = requests.post(
            f"{app_urls['backend']}/users",
            headers={"X-Admin-Api-Key": backend_admin_api_key},
            json={
                "email": email,
                "full_name": "E2E User",
                "password": password,
                "is_admin": False,
                "permissions": ["demo"],
            },
            timeout=10,
        )
        if r.status_code not in (200, 409):
            raise RuntimeError(f"create user failed: {r.status_code} {r.text}")
        return r

    return _create


@pytest.fixture
def backend_admin_headers(backend_admin_api_key):
    return {"X-Admin-Api-Key": backend_admin_api_key}


@pytest.fixture
def list_backend_users(app_urls, backend_admin_headers):
    def _list():
        r = requests.get(f"{app_urls['backend']}/users", headers=backend_admin_headers, timeout=10)
        if not r.ok:
            raise RuntimeError(f"list users failed: {r.status_code} {r.text}")
        return r.json()

    return _list

