# Changelog

## 0.3.1 (2026-05-13)

Packaging and metadata polish for PyPI.

- Ship `LICENSE` in the sdist/wheel and declare it via PEP 639 `license-files`.
- Use SPDX `license = "MIT"` and setuptools 77+ for builds.
- Expose `fastapi_workbench.__version__` (from installed distribution metadata).

Behavior since **0.2.0** (still included in this release line): `workbench_browser_base` prefers `FLUXLIT_PUBLIC_BASE_URL`, then app-provided `public_base_url`, then `PUBLIC_BASE_URL`, then `Request.base_url`; `external_workbench_url`, `merge_public_base_with_mount`, `browser_app_mount_path`, and `external_ui_url` for FluxLit / gateway-aligned links and duplicate-mount avoidance.

## 0.2.0

- Posit Connect `rstudio-connect-app-base-url` header support in `base_path`.

## 0.1.0

Initial published helpers: `workbenchify`, Workbench path middleware, safe redirects, and external URL helpers.
