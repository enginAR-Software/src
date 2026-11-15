#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
if [[ -x .venv/bin/python ]]; then
    exec .venv/bin/python -m fieldshift_data run --offline "$@"
fi
exec python3 -m fieldshift_data run --offline "$@"
