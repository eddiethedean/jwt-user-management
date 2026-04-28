# E2E (browser) tests

These tests run the **real apps** (FastAPI backend + Streamlit user demo) and drive a **real browser** via Playwright.

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

- The suite starts backend + Streamlit user app on **ephemeral ports** to avoid clashing with your dev servers.
- Each run uses a **unique SQLite DB file** under `e2e/` to avoid shared state.
- Process logs are written to `e2e/artifacts/logs/` for easier debugging on failures.

