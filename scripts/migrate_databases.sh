#!/usr/bin/env bash
# Apply Alembic migrations for all SQLite-backed apps in this repo.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ -f "$ROOT/.venv/bin/activate" ]]; then
  # shellcheck source=/dev/null
  source "$ROOT/.venv/bin/activate"
fi

echo "==> user_management_api"
(cd "$ROOT/user_management_api" && alembic upgrade head)

echo "==> fluxlit_app"
(cd "$ROOT/fluxlit_app" && alembic upgrade head)

echo "Done."
echo "  API:    $ROOT/user_management_api/app.db"
echo "  FluxLit: $ROOT/fluxlit_app/app.db (if present)"
