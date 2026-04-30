# fastapi-workbench

Small utilities to make FastAPI apps behave correctly behind Posit Workbench / RStudio Server proxy prefixes, while still behaving normally in non-Workbench deployments.

## Install (dev)

From the repo root:

```bash
pip install -e ./fastapi_workbench
```

## Quickstart

Wrap your app once:

```python
from fastapi import FastAPI
from fastapi_workbench import workbenchify

app = FastAPI()
app = workbenchify(app)
```

Generate external links that respect `root_path` and `PUBLIC_BASE_URL`:

```python
from fastapi_workbench import external_url

url = external_url(request, "/invites/accept?token=...")
```

Use Workbench-safe redirects:

```python
from fastapi_workbench import safe_redirect

return safe_redirect(request, "/admin/login")
```

