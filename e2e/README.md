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

### Run through a Connect-like reverse proxy (path prefix)

To mimic Posit Connect-style deployments where your app is served under an external prefix
and accessed through a reverse proxy, you can run the e2e suite with a local nginx proxy
in front of the backend:

```bash
source .venv/bin/activate
python -m playwright install chromium
E2E_USE_PROXY=1 pytest -q e2e
```

Defaults:
- Proxy prefix: `/connect/app` (override with `E2E_PROXY_PREFIX=/your/prefix`)
- Proxy listens on an ephemeral port (managed by the test harness)
- Proxy mode: `preserve` (backend sees the prefix). To test a proxy that strips the prefix, use `E2E_PROXY_MODE=strip`.

## Notes

- The suite starts backend + Streamlit user app on **ephemeral ports** to avoid clashing with your dev servers.
- Each run uses a **unique SQLite DB file** under `e2e/` to avoid shared state.
- Process logs are written to `e2e/artifacts/logs/` for easier debugging on failures.

