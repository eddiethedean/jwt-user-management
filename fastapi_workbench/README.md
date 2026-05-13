# fastapi-workbench

Small utilities to make FastAPI apps behave correctly behind Posit Workbench / RStudio Server proxy prefixes, while still behaving normally in non-Workbench deployments.

**Version:** 0.3.1 · [Changelog](CHANGELOG.md)

## Install

From [PyPI](https://pypi.org/project/fastapi-workbench/) (when published):

```bash
pip install fastapi-workbench==0.3.1
```

From this monorepo (editable):

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

## Release checklist (maintainers)

```bash
cd fastapi_workbench
python -m pip install -e ".[dev]"
ruff check src tests
pytest
python -m build --sdist --wheel
twine check dist/*
```
