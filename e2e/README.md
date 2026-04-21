# E2E (browser) tests

These tests run the **real apps** (FastAPI backend + Streamlit apps) and drive a **real browser** via Playwright.

## Prereqs

- Python 3.10+
- A working virtualenv (you can use the repo root `.venv`)

## Install

From repo root:

```bash
source .venv/bin/activate
pip install -r e2e/requirements.txt
python -m playwright install chromium
```

## Run

```bash
source .venv/bin/activate
pytest -q e2e
```

## Notes

- The suite starts backend + Streamlit on **ephemeral ports** to avoid clashing with your dev servers.
- The admin Streamlit app reads its auth config from `STREAMLIT_AUTH_CONFIG_PATH` (the tests generate a temporary one).

