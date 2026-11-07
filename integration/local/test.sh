#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p evidence runtime
.venv/bin/python -m pytest tests -v 2>&1 | tee evidence/integration.log
