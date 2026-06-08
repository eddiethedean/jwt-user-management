"""Pytest fixtures for user_management_api integration tests."""

from __future__ import annotations

from typing import Any, Generator

import pytest
from fastapi.testclient import TestClient

from api_test_helpers import load_wrapped_app


@pytest.fixture
def app_client(tmp_path, monkeypatch) -> Generator[TestClient, None, None]:
    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    app = load_wrapped_app(db_url=db_url)
    with TestClient(app, base_url="http://testserver") as client:
        yield client


@pytest.fixture
def db_engine(app_client: TestClient) -> Any:
    import app.db as db

    return db.engine
