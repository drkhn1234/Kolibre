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
