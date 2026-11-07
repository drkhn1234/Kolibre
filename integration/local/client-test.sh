#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p evidence
if [ ! -x clients/inspector/node_modules/node/bin/node ]; then
  npm ci --prefix clients/inspector --no-audit --no-fund
fi
.venv/bin/python -m pytest tests/test_inspector_client.py -v --tb=short \
  --junitxml=evidence/inspector-junit.xml 2>&1 | tee evidence/inspector.log
