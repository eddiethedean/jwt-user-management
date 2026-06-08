"""Pytest fixtures for Streamlit AppTest suites."""

from __future__ import annotations

import os

import pytest


@pytest.fixture(autouse=True)
def _streamlit_test_env():
    os.environ["STREAMLIT_TEST_MODE"] = "true"
    yield
