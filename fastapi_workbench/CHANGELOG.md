# Changelog

## 0.3.3 (2026-06-09)

Workbench login redirect fixes for apps mounted under `/s/<session>/p/<project>`.

- **Detection:** Treat `RS_SERVER_URL` plus a non-empty `root_path` as a Workbench request after path normalization (when `scope["path"]` is app-relative, e.g. `/login`).
- **Redirects:** Prefer mount-prefixed `Location` headers (`/s/.../p/.../admin`) instead of depth-based `../` relatives when `root_path` is set, so partially stripped paths do not drop the project segment.
- **Tests:** Regression coverage for post-normalization redirects and mount URL building.

## 0.3.2 (2026-06-08)

Security and correctness fixes from a full package audit (16 defects).

- **Redirects:** Fix empty `Location` for `/` in Workbench mode; depth-aware relative redirects; reject `..` unless `allow_parent_segments=True`; wire `public_base_url` to absolute redirects.
- **Detection:** `is_workbench_request` uses scope signals / `WORKBENCH_FORCE` only (not `RS_SERVER_URL` or bare `root_path`).
- **URLs:** Gate `rstudio-connect-app-base-url` on Workbench scope; segment-based mount dedup; sanitize `..` in external paths; case-insensitive `/api` strip.
- **Middleware:** Remove greedy partial `root_path` suffix stripping; percent-encode `raw_path`; expand debug log redaction.
- **Runner:** `RUN_MIGRATIONS` is opt-in; validate `PORT`; reload requires explicit `RELOAD=true`.

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
