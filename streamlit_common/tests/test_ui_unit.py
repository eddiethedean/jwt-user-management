"""Unit tests for streamlit_common.ui (st is mocked)."""

from __future__ import annotations

import pytest

import streamlit_common.ui as ui_mod


class _Resp:
    def __init__(self, status_code=400, json_data=None, text=""):
        self.status_code = status_code
        self.text = text
        self._json = json_data

    def json(self):
        if self._json is None:
            raise ValueError("no json")
        return self._json


def test_show_http_error_with_detail(monkeypatch):
    errors: list[str] = []

    def fake_error(msg: str):
        errors.append(msg)

    monkeypatch.setattr(ui_mod.st, "error", fake_error)
    r = _Resp(422, {"detail": "nope"})
    ui_mod.show_http_error("Failed", r)
    assert len(errors) == 1
    assert "Failed" in errors[0]
    assert "422" in errors[0]
    assert "nope" in errors[0]


def test_show_http_error_without_detail_body(monkeypatch):
    errors: list[str] = []

    def fake_error(msg: str):
        errors.append(msg)

    monkeypatch.setattr(ui_mod.st, "error", fake_error)
    r = _Resp(500, {})
    ui_mod.show_http_error("X", r)
    assert errors == ["X: 500"]
