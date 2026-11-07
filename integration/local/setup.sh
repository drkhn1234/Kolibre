#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p repos evidence runtime
if [ ! -d repos/Kolibre/.git ]; then
  git clone --branch feature/mcp-oidc-identities https://github.com/drkhn1234/Kolibre.git repos/Kolibre
  git -C repos/Kolibre switch -c dev/local-multiuser-integration 345419c29dccf1557b892ae61676e02f1dc37a06
  git -C repos/Kolibre -c user.name=Codex -c user.email=codex@openai.com am "$PWD"/patches/*.patch
fi
if [ ! -d repos/calibremcp/.git ]; then
  git clone --branch feature/kolibre-authenticated-mcp-bridge https://github.com/drkhn1234/calibremcp.git repos/calibremcp
  git -C repos/calibremcp switch -c dev/local-multiuser-integration 131a29f562365e62f66165e3ad56ec49dbde350d
  git -C repos/calibremcp -c user.name=Codex -c user.email=codex@openai.com am "$PWD"/patches/calibremcp/*.patch
fi
uv venv --python 3.12 .venv
uv pip sync --python .venv/bin/python requirements.lock
uv pip install --python .venv/bin/python --no-deps -e repos/calibremcp
npm ci --prefix oidc
npm ci --prefix clients/inspector --no-audit --no-fund
bash deployment/setup_local_keycloak.sh
