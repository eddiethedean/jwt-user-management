"""Shared helpers for Streamlit AppTest suites."""

from __future__ import annotations

from streamlit.testing.v1 import AppTest

from app_paths import USER_APP_PY


class FakeHttpxResponse:
    def __init__(self, ok=True, status_code=200, json_data=None, text=""):
        self.ok = ok
        self.is_success = bool(ok)
        self.status_code = status_code
        self._json_data = json_data if json_data is not None else {}
        self.text = text

    def json(self):
        return self._json_data


def text_input_by_key(at: AppTest, key: str):
    matches = [t for t in at.text_input if getattr(t, "key", None) == key]
    if not matches:
        raise AssertionError(f"Text input not found for key={key!r}")
    return matches[0]


def click_button(at: AppTest, label: str) -> None:
    for b in at.button:
        if getattr(b, "label", None) == label or getattr(b, "value", None) == label:
            b.click()
            return
    raise AssertionError(f"Button not found: {label!r}")


def set_public_page(at: AppTest, page: str) -> None:
    matches = [r for r in at.radio if getattr(r, "label", None) == "Go to"]
    if not matches:
        raise AssertionError("Public navigation radio not found")
    matches[0].set_value(page)


def new_app_test() -> AppTest:
    return AppTest.from_file(USER_APP_PY, default_timeout=30)
