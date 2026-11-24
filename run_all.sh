#!/usr/bin/env bash
# Rebuild everything from IRA's files. Usage: ./run_all.sh [--offline]
set -euo pipefail
cd "$(dirname "$0")"
export PYTHONPATH=src
if [[ "${1:-}" != "--offline" ]]; then python -m kli.download; fi
python -m kli.extract
python -m kli.panel
python -m kli.validate
python -m kli.views
python -m kli.dashboard
