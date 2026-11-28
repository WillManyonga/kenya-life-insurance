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
# Claims settlement and the register of insurers are separate IRA series: a problem in either is
# reported in validation/ and does not stop the accounts from being refreshed.
python -m kli.claims || echo "::warning::claims settlement step failed; see the log"
python -m kli.registry || echo "::warning::registry step failed; see the log"
python -m kli.sitedata || echo "::warning::site data for claims/registry failed"
