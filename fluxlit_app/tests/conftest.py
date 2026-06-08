"""Pytest fixtures for fluxlit_app integration tests."""

from __future__ import annotations

import os
from typing import Any

import pytest

from fluxlit_test_helpers import (
    _FLUX_ROOT,
    _REPO_ROOT,
    purge_other_repo_app_packages,
)

os.environ.setdefault("FLUXLIT_TESTS", "1")


@pytest.fixture(autouse=True)
def _fluxlit_tests_restore_sys_path() -> Any:
    """Other repo trees also ship a top-level ``app``; prefer ours only for these tests."""
    import sys

    saved = list(sys.path)
    purge_other_repo_app_packages(repo_root=_REPO_ROOT, fluxlit_app_root=_FLUX_ROOT)
    flux = str(_FLUX_ROOT)
    if flux not in sys.path:
        sys.path.insert(0, flux)
    yield
    sys.path[:] = saved
