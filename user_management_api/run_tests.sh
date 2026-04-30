#!/usr/bin/env bash
set -euo pipefail

# Some environments auto-load global pytest plugins that may be incompatible with the
# installed pytest version. Disable auto-loading to keep this repo's tests stable.
export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1

pytest -q tests

