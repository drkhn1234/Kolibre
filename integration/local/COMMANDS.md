# Executed verification commands

Run from `/home/drkhn/Projects/kolibre-integration` unless a different working directory is given. Routine inspection commands are omitted; relevant raw output is under `evidence/`.

## Launch and integration

```sh
./setup.sh
./test.sh
.venv/bin/python -m pytest tests/test_live_move_recovery.py -v
.venv/bin/python -m pytest tests/test_live_native.py::test_native_login_token_expiration_during_mcp_session -v
.venv/bin/python -m pytest tests/test_live_oidc.py -v
```

The fresh replay used `git archive HEAD | tar -x -C runtime/replay-clean`, then ran `./setup.sh` and `./test.sh` from `runtime/replay-clean`. Outputs: `evidence/replay-setup.log`, `runtime/replay-clean/evidence/integration.log` (also copied to `evidence/replay-integration.log`). Both repository Git tree hashes were compared: `evidence/replay-source-trees.json`.

## Backend, frontend and bridge

```sh
mkdir -p runtime/baseline
DATA_DIR="$PWD/runtime/baseline/data" DATABASE_URL="sqlite:///$PWD/runtime/baseline/app.db" \
 PYTHONPATH="$PWD/repos/Kolibre/backend" .venv/bin/python -m unittest discover \
 -s repos/Kolibre/backend/tests -p 'test_*.py' -v
.venv/bin/python -m compileall -q repos/Kolibre/backend/app repos/Kolibre/backend/tests
(cd repos/Kolibre/frontend-react && npm ci && npm run build)
(cd repos/calibremcp && ../../.venv/bin/python -m pytest tests/unit/test_kolibre_bridge.py --no-cov -q)
(cd repos/calibremcp && ../../.venv/bin/ruff check src tests)
(cd repos/calibremcp && ../../.venv/bin/ruff format --check src tests)
```

The backend, bridge, compilation and full Ruff checks were also repeated in the fresh replay. `--no-cov` matches the repository's CI test command and avoids representing a focused test selection as repository-wide coverage.

## Wider legacy suite and attribution

```sh
(cd repos/calibremcp && ../../isolated-check.sh ../../.venv/bin/python -m pytest tests --no-cov -q)
(cd repos/calibremcp && ../../isolated-check.sh ../../.venv/bin/python scripts/create_test_db.py)
(cd repos/calibremcp && ../../isolated-check.sh ../../.venv/bin/python -m pytest \
 tests/unit tests/test_mcp_compliance.py tests/test_stdio_integration.py \
 tests/test_server_integration.py tests/test_mcp_server.py --no-cov -q)
```

The same commands and Ruff checks ran against a detached baseline worktree at `runtime/calibremcp-baseline`, commit `131a29f562365e62f66165e3ad56ec49dbde350d`. Failure IDs were compared in `evidence/baseline-comparison.json`. No tests or assertions were deleted or skipped by the lab to obtain a passing result.

```sh
gh pr view 1 --repo drkhn1234/calibremcp --json headRefOid,statusCheckRollup
gh pr view 2 --repo drkhn1234/Kolibre --json headRefOid,statusCheckRollup
gh pr view 1 --repo drkhn1234/Kolibre --json headRefOid,statusCheckRollup
gh run view 42293201059 --repo drkhn1234/calibremcp --log-failed
```

These were read-only GitHub operations. Results are saved in `evidence/*-pr-ci.json` and `evidence/calibremcp-ci-failure.log`. Git ancestry confirms the Kolibre OIDC branch includes `origin/feature/multiuser-ingest-boundary`.

## Independent MCP Inspector milestone — 2026-11-07

These commands used the existing local disposable lab; no Oracle commands were executed.

```sh
npm view @modelcontextprotocol/inspector version engines dist.integrity --json
npm install --prefix clients/inspector --no-audit --no-fund
npm ci --prefix clients/inspector --no-audit --no-fund
clients/inspector/node_modules/node/bin/node --version
clients/inspector/node_modules/node/bin/node clients/inspector/node_modules/@modelcontextprotocol/inspector/clients/mcpdo/build/mcp-bin.js --version
bash client-test.sh
.venv/bin/python -m pytest tests/test_live_oidc.py -v --tb=short --junitxml=evidence/oidc-regression-junit.xml
.venv/bin/python -m pytest tests -v --tb=short --junitxml=evidence/client-milestone-junit.xml
.venv/bin/ruff check tests/test_inspector_client.py
.venv/bin/ruff format --check tests/test_inspector_client.py
bash -n client-test.sh setup.sh test.sh
node --check oidc/provider.mjs
git diff --check
git -C repos/Kolibre ls-remote origin refs/heads/dev/local-multiuser-integration
git -C repos/calibremcp ls-remote origin refs/heads/dev/local-multiuser-integration
```

Final combined stdout/stderr is in `evidence/client-milestone-full.log`. The focused test was repeated while diagnosing mutually exclusive Inspector config options and its 60-second JWT expiry margin; see INTEROPERABILITY.md for those failed attempts and their evidence. No failed security assertion was removed. The initial focused pass was 3 tests / 195.44 seconds; the final combined run validates the tightened denial assertions and sanitized trace archiving too. Historical original-milestone commands above remain unchanged.

## ChatGPT preparation and final deployed verification (2026-11-07)

Executed from /home/drkhn/Projects/kolibre-integration unless noted:

```sh
PYTHONPATH="$PWD/repos/Kolibre/backend" .venv/bin/python -m unittest discover -s repos/Kolibre/backend/tests -p 'test_*.py' -v
.venv/bin/python -m compileall -q repos/Kolibre/backend/app repos/Kolibre/backend/tests
(cd repos/calibremcp && ../../.venv/bin/python -m pytest tests/unit/test_kolibre_bridge.py tests/unit/test_kolibre_bridge_logging.py --no-cov -q)
(cd repos/calibremcp && ../../.venv/bin/ruff check src tests && ../../.venv/bin/ruff format --check src tests)
.venv/bin/python -m pytest tests/test_live_oidc.py tests/test_deployment_cli.py -q --tb=short --junitxml=evidence/deployment/oidc-chatgpt.xml
.venv/bin/python -m pytest tests -q --tb=short --junitxml=evidence/deployment/chatgpt-local-all.xml
(cd repos/calibremcp && ../../isolated-check.sh ../../.venv/bin/python -m pytest tests --no-cov -q --tb=short --junitxml=../../evidence/deployment/calibre-full-final.xml)
.venv/bin/python deployment/native_expiry.py
.venv/bin/python deployment/validate.py verify-oidc
```

Results: 79 backend OK; 13 bridge passed; Ruff/format clean (317 files);
5 focused OIDC/CLI passed; 21 full live lab passed. Full CalibreMCP remains
285 passed / 42 failed / 23 errors / 10 skipped. See VPS_RESULTS.md for times,
baseline comparison and distinct failure IDs. Full legacy tests are sandboxed
away from personal storage and networking, with a synthetic metadata fixture.

Baseline execution used `git archive 131a29f562365e62f66165e3ad56ec49dbde350d`
into `runtime/calibre-full-baseline`, `patch -p1` with only f01692e's three
manual-script collection wrappers, and a copy of the synthetic test-library
metadata.db. Command there:

```sh
../../isolated-check.sh env PYTHONPATH=src ../../.venv/bin/python -m pytest tests --no-cov -q --tb=short --junitxml=../../evidence/deployment/calibre-full-baseline.xml
```

The baseline's source import location was checked explicitly. It had exactly
the same unsuccessful IDs, 283 passes and the same failures/errors/skips.

Predefined ChatGPT-client probe (temporarily changes only its token lifetime):

```sh
scp deployment/configure_chatgpt.py oracle:/tmp/configure_chatgpt.py
ssh oracle sudo install -m 0644 /tmp/configure_chatgpt.py /opt/kolibre-stage/deployment/configure_chatgpt.py
ssh oracle sudo /opt/kolibre-stage/current/.venv/bin/python /opt/kolibre-stage/deployment/configure_chatgpt.py --token-seconds 120
umask 077
ssh oracle sudo cat /etc/kolibre-stage/chatgpt-client.json > runtime/chatgpt-client.json
chmod 600 runtime/chatgpt-client.json
trap 'ssh oracle sudo /opt/kolibre-stage/current/.venv/bin/python /opt/kolibre-stage/deployment/configure_chatgpt.py --token-seconds 300' EXIT
.venv/bin/python deployment/chatgpt_probe.py
```

Never print the private client or credential JSON into an agent transcript.
This probe's successful output is retained in verification/2026-11-07/;
ChatGPT UI interaction is explicitly not included. Native expiry has its own
try/finally restoration and restarts only the staging backend. Do not run it
concurrently with other VPS tests.

`validate.py verify-expiry` is now a supported alias for the existing expiry.py
runner (previously argparse exit 2). The dispatch and failure propagation were
unit tested; deployed expiration was independently rerun with both new probes.

Source deployment used `git archive HEAD` for c06a7ce and 072c065 into
`/tmp/kolibre-source-<full SHA>.tar`, uploaded with scp, followed by:

```sh
ssh oracle sudo /opt/kolibre-stage/current/.venv/bin/python /opt/kolibre-stage/deployment/upgrade_sources.py --backend c06a7cea001c853a9dfc74bd1e6e8ce627307e26 --bridge 072c06541585dc494ad137faf84603f8d6617194
```

Do not rerun that upgrade at the same revision: it refuses existing release
directories. Both archives and the persisted manifest were compared by every
file SHA256; current release paths were inspected. See source-verification.json.

When the workstation's public egress changes, inspect it before changing the
single-address DCR gate. The measured address was updated with
`deployment/update_test_ip.py --client-ip 151.250.102.94` on the VPS (root).
The earlier stale-IP failure is preserved as public-oidc-stale-ip.log. Five
obsolete fixed-loopback helper clients were pruned with prune_probe_clients.py;
no anonymous registration policy was relaxed.

Read-only final checks used `ssh oracle sudo python3 - < deployment/inventory.py`,
state_audit.py, systemctl is-active, Docker ps, GitHub gh run/pr queries, normal
HTTPS requests and comparison with BookOrbit's original discovery documents.
No new VM reboot, production import, or PR merge occurred in this milestone.

Final advertised-scope follow-up:

```sh
# After uploading the final configure_chatgpt.py AND keycloak_config.py:
ssh oracle sudo /opt/kolibre-stage/current/.venv/bin/python /opt/kolibre-stage/deployment/configure_chatgpt.py
.venv/bin/python deployment/offline_probe.py
.venv/bin/python deployment/offline_probe.py --scope basic
.venv/bin/python -m pytest tests/test_keycloak_local.py -q --tb=short --junitxml=evidence/deployment/keycloak-mapper-final.xml
```

Both public refresh/privacy/revocation probes pass; the focused provider test
passes in 177.01s. This follow-up corrected explicit optional-scope association,
per-reader offline role assignment and separate client/custom audience mappers.
See VPS_RESULTS.md for failed attempts and bounds (8h max, 30m idle configured;
full wall-clock limits not waited out). No audience check was relaxed.

The patch-chain smoke reconstruction used git archive at each pinned baseline,
patch --batch --fuzz=0 -p1 for every shipped patch, then byte-compared all tracked
backend files (102) and bridge source/tests (335) with the tested checkouts.
Cached userspace-provider artifacts passed setup_local_keycloak.sh checksums.

A final one-off .venv Python/httpx probe repeated the predefined-client
code/S256 exchange and refresh/revocation using httpx.BasicAuth(client_id,
client_secret), without client_secret in the form. The resulting bearer was
verified at /api/users/me as founder. Output: basic-client-auth.log; PASS.
All authentication material stayed in memory or mode-0600 runtime files.

## Knowledge retrieval vertical slice — 2026-11-07

- `ssh oracle 'sudo /usr/local/sbin/kolibre-stage-backup'`: new encrypted baseline.
- Copy encrypted snapshot via root read-only SSH stream to ignored runtime;
  age decrypt into isolated runtime/baseline-restore; SQLite integrity ok,
  two users/three EPUBs/nonempty IdP dump/root settings. No live restore/migration.
- `PYTHONPATH="$PWD/repos/Kolibre/backend" .venv/bin/python -m unittest discover -s repos/Kolibre/backend/tests -p 'test_*.py'`: 81 OK.
- `.venv/bin/python -m pytest tests/test_knowledge.py -q --tb=short`: 1 passed,
  9.55s (real embeddings, MCP/HTTP, ACL/lifecycle/private move).
- `.venv/bin/python -m pytest tests/test_live_native.py::test_native_mcp_sessions_and_live_revocation -q`: 1 passed.
- Existing bridge/logging pytest: 13 passed; bridge Ruff lint/format clean.
- Git archive upload; deployment/upgrade_sources.py with exact 40-char bbb24204…
  and 6877e761… hashes. An initial abbreviated-hash invocation correctly refused
  without changes. Enable script initially lacked isolated HF_HOME; fixed
  configuration without weakening ProtectHome, then deployed successfully.
- `PYTHONPATH=. .venv/bin/python deployment/knowledge_probe.py`: actual public
  HTTPS real FastMCP client, both native/Keycloak S256 identities, five tools,
  concurrent retrieval, foreign denial, revoke/reconnect/restore PASS.
- Two representative synthetic shared EPUBs imported through actual ingestion;
  worker indexed automatically. Public semantic-only top-1 query smoke passes.
- No old full Calibre suite repetition, paid compute, PR merges or unrelated
  container restarts. Sources/helpers and recovery instructions: KNOWLEDGE.md.

## LanceDB and first-use web deployment

Focused tests: tests/test_knowledge.py1pass23.02s; backend test_knowledge_index2OK;
Calibre test_lance_authorized_storage1pass1.04s; existing bridge13pass2.72s.
Public knowledge_probe.py native/OIDC PASS after deployment (lance-public-final.log).
Frontend TypeScript/Vite build with API/base paths passes; deploy_web.py publishes
hash-manifested bundle and Caddy route with validation and rollback. HTTPS UI,
assets, SPA deep route and reader HTML200; BookOrbit root200. No browser-rendered
login observation: computer-use tab creation failed (timeoutMs tool error).
Initial Lance merge used target.metadata prefix unsupported by actual installed
version: corrected to metadata.book_id and regression passed. Backend Calibre
module import required isolated CALIBRE_MCP_LOG_FILE, now explicitly configured.
No TLS/home isolation weakened. Full source revisions and use: FIRST_USE.md.
