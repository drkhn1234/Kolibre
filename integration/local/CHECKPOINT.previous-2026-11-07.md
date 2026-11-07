# Kolibre–CalibreMCP checkpoint

Inspected **2026-11-07, approximately 11:45–11:50 Europe/Istanbul (UTC+03:00)**. This is a checkpoint-only operation. No application code, branches, configuration, services, databases, or deployment state were changed; no test suites were rerun. Only this file was written. No credentials or sensitive environment values are recorded here.

## 1. Current objective and status

The completed milestone was to establish a reproducible **local** Kolibre–CalibreMCP environment and demonstrate simultaneous independent users with authentication, library authorization, annotations/reading state, and crash recovery. The Codex session marked that goal complete after the clean replay and completion audit. It did **not** establish production or Oracle staging readiness.

The subsequent user request to sync changes to GitHub was also completed: both forks have the development branches described below, and the integration harness/reports were additionally packaged in Kolibre under `integration/local/`.

The current instruction is **checkpoint only; stop after saving this file**. No next milestone or deployment target has been selected. There is no unfinished implementation or deployment job to resume automatically.

Read [README.md](README.md) for usage, [RESULTS.md](RESULTS.md) for detailed results and limits, [AUDIT.md](AUDIT.md) for requirement coverage, and [COMMANDS.md](COMMANDS.md) for executed checks. No previous checkpoint was found in the top-level lab during this inspection.

**Documentation correction:** README.md/RESULTS.md say nothing was pushed. That statement predates the explicit GitHub-sync request and is now stale. The pushes in section 2 are authoritative. Nothing was merged or deployed. The historical replay tree equality in RESULTS.md refers to the tested code before the two later Kolibre harness/documentation packaging commits, not to the whole current Kolibre HEAD.

## 2. Repositories and Git state

All six Git checkouts/worktrees below were inspected. Before writing this checkpoint, every one had **no staged changes, no unstaged tracked changes, and no non-ignored untracked files**. Ignored local data is listed separately below. After this operation the only intended new file is the top-level `CHECKPOINT.md`; it is deliberately uncommitted and unpushed.

Paths below are relative to `/home/drkhn/Projects/kolibre-integration` unless absolute.

| Repository/check out | Active branch | Exact HEAD | Push status |
|---|---|---|---|
| `/home/drkhn/Projects/kolibre-integration` | `dev/local-integration-lab` | `b0165ba3150513fd3e0d399b38a8582d695ce27a` | No remote or upstream. Its original commits are local; the tracked lab content was copied into the pushed Kolibre checkout. This new checkpoint is not part of that copy. |
| `repos/Kolibre` | `dev/local-multiuser-integration` | `d4155e553b442d7dcb321f0a491f9066b9a51968` | Tracks `origin/dev/local-multiuser-integration`; `git ls-remote` during checkpoint matched HEAD exactly. |
| `repos/calibremcp` | `dev/local-multiuser-integration` | `12ecf368644609156d4f16ba9e43663284b79153` | Tracks `origin/dev/local-multiuser-integration`; `git ls-remote` during checkpoint matched HEAD exactly. |
| `runtime/calibremcp-baseline` | Detached HEAD | `131a29f562365e62f66165e3ad56ec49dbde350d` | Comparison worktree of `repos/calibremcp`, not an independent integration branch; no new commits to push. |
| `runtime/replay-clean/repos/Kolibre` | `dev/local-multiuser-integration` | `2f7dc276c116c5bdbe4e512df40a13b62e8a91b9` | Clean-replay clone, no upstream. Patch-reconstructed commits were not pushed. Do not push this branch over the primary checkout's branch. |
| `runtime/replay-clean/repos/calibremcp` | `dev/local-multiuser-integration` | `32956fd97061f39d083e007c487adfeea2f82727` | Clean-replay clone, no upstream. Patch-reconstructed commit was not pushed. |

`runtime/replay-clean/` itself is an archive of the lab, **not** a separate Git repository; it has no `.git`. The baseline worktree shares Git administration with the primary CalibreMCP checkout. No merge, cherry-pick, revert, rebase/apply-in-progress marker or index lock was found in any of the six Git directories.

Primary remotes:

- Kolibre: `https://github.com/drkhn1234/Kolibre.git`.
- CalibreMCP: `https://github.com/drkhn1234/calibremcp.git`.

Recent relevant primary commits:

| Repository | Commit | Purpose |
|---|---|---|
| Kolibre | `0481db182f5c935bcd3bf463d1bf9abee94027b4` | Preserve revoked library access across restarts; migrate only genuinely legacy unowned/shared libraries. |
| Kolibre | `50e8a1b9ffdc5d1b38ada4d263d4a7f0b78ff704` | Give each upload request a fresh staging path so reusing a filename cannot select an imported row/old visibility. |
| Kolibre | `de70f7fe3e9444f5598383aa1d16d4468fc941e1` | Require OIDC audience/issuer claims; support scoped JWKS CA-bundle trust. |
| Kolibre | `337fc711e87c3682047e4d8bfe0d2ce3dcd5a407` | Preserve valid copies when source files are damaged; prevent repeated review from completing an incomplete move; add regressions. Last tested backend code commit. |
| Kolibre | `b5dded98ee1159cb5509beb6445c4770e025b0b3` | Package reproducible lab under `integration/local/`. |
| Kolibre | `d4155e553b442d7dcb321f0a491f9066b9a51968` | Add packaged README, RESULTS, AUDIT and COMMANDS documents. |
| CalibreMCP | `12ecf368644609156d4f16ba9e43663284b79153` | Advertise configured OIDC scopes for MCP client registration; metadata regression and documentation. |

All primary commits above are on the verified pushed development branches. Kolibre changes after `337fc7…` only add `integration/local/`; the backend subtree hash at both that commit and current HEAD is `b15fa67f8b85968464873b50d14cee3a7dfd46a4` (checked now).

Lab history (local, no remote):

- `fb50f7f02e3c1de155effbe7216b23cf95099b7b`: native live integration lab.
- `ca0d28956f3204a8404612159f50105e1482de08`: real local provider and MCP OAuth isolation.
- `9fab2863dd51bc0793996f30f1fe3742b5050543`: move crashes, preservation and native expiry.
- `b0165ba3150513fd3e0d399b38a8582d695ce27a`: final results, commands and audit.

Pinned source baselines: Kolibre OIDC `345419c29dccf1557b892ae61676e02f1dc37a06`, which includes the multi-user foundation; CalibreMCP bridge `131a29f562365e62f66165e3ad56ec49dbde350d`. Replay commits have different IDs because `git am` recreated them, but saved evidence proves the tested trees matched: Kolibre `9be2f844fd55a597ecdc1ae426273fee336cd655`, CalibreMCP `a04e917a6c39fe6a1c617f93a79ef01481c60d43`.

GitHub PR state was checked read-only now:

- [Kolibre #1](https://github.com/drkhn1234/Kolibre/pull/1): open draft, `feature/multiuser-ingest-boundary` → `main`.
- [Kolibre #2](https://github.com/drkhn1234/Kolibre/pull/2): open draft, `feature/mcp-oidc-identities` → `feature/multiuser-ingest-boundary`.
- [CalibreMCP #1](https://github.com/drkhn1234/calibremcp/pull/1): open draft, `feature/kolibre-authenticated-mcp-bridge` → `master`.
- None uses `dev/local-multiuser-integration` as its head. No PR for the newly pushed development branches exists in the returned PR lists. Pushing fixes did not update those older draft PR heads.

## 3. Running environment and configuration

**Observed runtime:** no Kolibre backend, restricted bridge, local provider, pytest runner, migration, push, or deployment process was found running for this lab. Process inspection was limited to metadata/known task markers; it did not dump process environments or credentials. The inspection's own short-lived Python process was the only process with a cwd under the lab. Socket inspection showed other unrelated system/Codex/browser listeners, left untouched; none was identified as a lab component. Default Kolibre/bridge ports `8081`/`10721` were not listening.

Docker and Podman executables were absent, and no standard local Docker/Podman socket was found. There was no visible local container-engine process. Consequently no Docker/Compose API inventory could be obtained; this is not a claim about remote engines or infrastructure. This task previously used subprocesses, not Compose. No Oracle/VPS state was inspected.

Historical tested toolchain: Ubuntu 26.10 x86_64; Python 3.12.14, Node 22.23.2, FastMCP 3.4.11, MCP SDK 1.30.0, node-oidc-provider 9.13.3. Locks: `requirements.lock` and `oidc/package-lock.json`.

There is **no persistent configured lab endpoint to reconnect to**. Fixtures choose ephemeral loopback ports and tear down their servers. Native tests run Uvicorn `backend.app.main:app` plus `python -m calibre_mcp.kolibre_bridge`. OIDC tests run the same restricted bridge through Uvicorn TLS plus `oidc/provider.mjs` over HTTPS. The provider and OAuth-client caches are in memory.

Nonsecret configuration shape (see `environment.example` and fixture code):

- `DATA_DIR=<pytest test directory>/data`; `DATABASE_URL=sqlite:///<pytest test directory>/app.db`.
- `KOLIBRE_BACKEND_URL=http://127.0.0.1:<backend-port>`; bridge bind `127.0.0.1`, separate selected bridge port.
- `KOLIBRE_OIDC_ISSUER=https://127.0.0.1:<provider-port>`; JWKS URI at its `/jwks` endpoint.
- OIDC audience is the bridge HTTPS resource URL **including `/mcp`**.
- `KOLIBRE_MCP_PUBLIC_URL` is the bridge HTTPS origin **without `/mcp`**, which FastMCP appends.
- Advertised scopes are configured consistently (`openid books:read` in the lab); default bridge advertised scope is `openid`.
- `KOLIBRE_OIDC_CA_BUNDLE` references the generated test CA PEM for JWKS trust. Clients pass explicit SSL contexts. System CA trust was not altered; TLS verification remains enabled.
- Passwords, native signing material, provider signing material and TLS keys are generated for disposable tests; their values are intentionally omitted. No active `.env` was present at the lab root, the two primary repository roots, or the replay root; only repository `.env.example` files were found there. This does not assert that no configuration files exist elsewhere.

Kolibre's existing `docker-compose.yml` is not the verified lab launcher. Its port mappings do not explicitly bind loopback and it does not provide this disposable OIDC setup. Do not mistake the existence of that file for a tested safe deployment configuration.

**Retained local storage not preserved by Git:**

- `evidence/`: raw test/build/CI output and JSON comparisons. Ignored by the lab repo, not uploaded with the packaged lab. Preserve it; published reports refer to these local files.
- `.venv/`, `oidc/node_modules/`: ignored installed dependencies. Replay has separate equivalents under `runtime/replay-clean/`.
- `runtime/replay-clean/`: ignored clean-bootstrap archive, two reconstructed clones, its own evidence and environments. It is a verification artifact, not the primary development checkout.
- `runtime/baseline/` and `runtime/replay-clean/runtime/baseline/`: retained unit-test scratch directories. The `app.db` paths in old commands are configured scratch targets, not evidence of running databases; no `.db` file was found in these two directories in the current file inventory.
- `repos/calibremcp/tests/fixtures/test_library/metadata.db` and `runtime/calibremcp-baseline/tests/fixtures/test_library/metadata.db`: untracked/ignored synthetic fixture databases generated for wider legacy tests, each 106496 bytes. They are not user libraries.
- `/tmp/pytest-of-drkhn/pytest-23/`: retained final replay test directories. `/tmp/pytest-of-drkhn/pytest-current` pointed here at inspection but is mutable and will change on a future pytest run. Individual directories contain `app.db`, `data/libraries/<library>/metadata.db`, `fulltext.db`, synthetic EPUBs and logs.
- Concrete inspected example: `/tmp/pytest-of-drkhn/pytest-23/test_oidc_real_provider_and_is0/`. Its application DB and shared/private metadata/full-text databases still exist. It also retains generated test CA/signing/TLS files; do not copy their contents into Git, checkpoints or messages. Test accounts/keys are disposable, not a live provider to resume.
- This `CHECKPOINT.md` is local-only and uncommitted. It is not inside the pushed Kolibre `integration/local/` snapshot.

No artifact was deleted or moved for checkpointing. Retained fixture mutations and review journals are synthetic test outcomes, not live migration jobs or outstanding user-data moves.

## 4. Completed and verified work

Evidence summaries were read from existing files during this checkpoint; the suites were **not rerun**. Full commands and setup context are in COMMANDS.md.

| Important command/check | Recorded result | Available evidence |
|---|---|---|
| `./setup.sh`, then `./test.sh` in `runtime/replay-clean/` | Fresh dependency installation/patch application succeeded; **15 passed**, 1 warning, **83.36s** | `evidence/replay-setup.log`, `evidence/replay-integration.log`, replay's `evidence/integration.log` |
| `.venv/bin/python -m unittest discover -s repos/Kolibre/backend/tests -p 'test_*.py' -v` with isolated DATA_DIR/DATABASE_URL/PYTHONPATH as documented | **76 tests, OK**, 7.493s in replay | `evidence/replay-backend.log`, `evidence/kolibre-after.log` |
| `.venv/bin/python -m compileall -q repos/Kolibre/backend/app repos/Kolibre/backend/tests` | Exit 0 recorded in session; not independently rerun here | COMMANDS.md/session execution; no standalone compilation-output log |
| In CalibreMCP: `../../.venv/bin/python -m pytest tests/unit/test_kolibre_bridge.py --no-cov -q` | **12 passed**, 28 warnings, 0.69s in replay | `evidence/replay-bridge.log` |
| In CalibreMCP: `../../.venv/bin/ruff check src tests`; `../../.venv/bin/ruff format --check src tests` | All checks passed; **316 files already formatted** | `evidence/replay-ruff.log`, `evidence/replay-format.log` |
| In Kolibre `frontend-react`: `npm ci`, `npm run build` | TypeScript/Vite build successful, 1.12s | `evidence/frontend-install.log`, `evidence/frontend-build.log` |
| Git tree comparison of original and fresh reconstructed sources | Identical at the tested code revisions | `evidence/replay-source-trees.json`; current backend subtree equality rechecked in section 2 |
| GitHub remote-head check for both development branches | Exact primary local HEADs match remote branches | Read-only `git ls-remote origin refs/heads/dev/local-multiuser-integration` executed during this checkpoint |

Demonstrated behavior:

- Correct founder/admin and sister/ordinary account roles; founder-owned shared library and separate owner-private libraries (`evidence/ownership-audit.json`).
- Genuine native login and actual provider code-flow access tokens; correct identity mapping before/after explicit linking.
- Real provider discovery, DCR, authorization code with S256 PKCE, incorrect verifier rejection, signed JWT validation and scoped HTTPS trust.
- Real FastMCP OAuth clients start without bearer tokens and complete discovery/registration/exchange before accessing their own content. Browser-interaction callbacks use separate HTTP cookie jars; authorization and token exchange are not mocked.
- Six simultaneous native MCP sessions, four OIDC sessions and two independently authenticating OAuth clients; exactly four tools exposed. Private catalogs, full text and annotations remain isolated, including against the founder.
- Missing/invalid/expired tokens, incorrect signatures/issuer/audience, absent required claims and unlinked subjects are rejected. Cross-account binding and wrong-password link attempts fail. Native and OIDC expiry within existing MCP sessions are tested.
- Current grants are checked on successive calls; revocation affects an existing session and survives backend restart. Direct HTTP and separate OPDS credentials respect private libraries. Stale shared FTS no longer finds a book after it becomes private.
- Actual shared/private uploads, same-filename restaging, physical Calibre-format placement and real lexical indexing.
- Both users can make a shared book private; only the mover's reading position, annotation IDs and device-book association migrate. The other reader's state remains scoped to shared.
- Confirmed process crashes after durable `ready`/`source_deleted` checkpoints; ordinary restart and owner-only journal recovery; safe rollback/completion and idempotence. A test-only timestamp aging step exercises the two-minute anti-concurrency guard without sleeping through it.
- Missing/truncated/same-size-corrupted source files preserve the valid target and produce `needs_review`; repeating an incomplete review cannot certify completion; no destructive delayed retry remains queued.

## 5. Work currently in progress

**Application/integration work:** none observed. The local milestone and requested GitHub synchronization are finished. There are no live test handles, active app services, rebase/apply operations or deployment/migration jobs to continue.

**This checkpoint:** the sole new local artifact. Do not commit or push it under the present instruction.

**Implemented/configured but not functionally verified:** the repository's existing Compose launcher; provider refresh-token capability/configuration (no renewal-flow test); existing GUI runtime behavior beyond the React build; external IdP and production TLS/reverse-proxy compatibility. These are not running workstreams and must not be reported as passed.

## 6. Architectural decisions and rationale

1. **Kolibre is the identity/ACL authority.** The separate CalibreMCP bridge validates each bearer through live `/api/users/me`, then forwards the same caller bearer to Kolibre APIs. Tokens, user/library selection and cached results are not process-global. Backend HTTP clients do not follow redirects or inherit ambient proxy settings.
2. **Use a separate restricted MCP surface.** Only `kolibre_list_libraries`, `kolibre_list_books`, `kolibre_search_fulltext`, and `kolibre_my_annotations` are registered. Mounting unrestricted legacy filesystem, library-switching or vector-RAG tools was excluded because those paths do not provide the demonstrated per-user boundary.
3. **OIDC maps verified `(issuer, subject)` to an explicitly linked local account.** RS256 signature, issuer, resource audience and expiration must validate before account resolution. No email matching, unverified-subject trust or automatic provisioning. Linking requires the owner's native login and password confirmation; founder cannot replace another user's binding.
4. **RemoteAuthProvider advertises the external issuer; the provider owns browser login and code+PKCE/DCR.** The lab uses actual provider/client implementations to avoid treating mocked unit success as OAuth interoperability. Only browser interaction is automated. Incorrect public URL path and empty/inconsistent advertised scopes caused integration failures and were corrected in configuration/code as documented.
5. **Local subprocesses were chosen because Docker was unavailable.** Environments, ports, data and synthetic files are isolated. A clean bootstrap replay demonstrated reproducibility. Scoped CA trust was chosen over globally disabling verification or modifying system trust. No public/Oracle deployment was attempted.
6. **Private content belongs only to its owner, even against founder/admin.** Shared-library visibility is separate from personal annotations, progress and device ownership. Device associations and personal data migrate only for the mover; foreign notes/devices do not follow a shared-to-private move.
7. **A durable journal precedes cross-database move operations.** The target insertion includes a recovery token atomically. The source deletion boundary determines rollback versus completion. Do not guess target identity by title or queue destructive retries. A surviving source DB row is insufficient evidence that its files are valid: recovery compares actual files/full SHA-256 digests. Ambiguity preserves copies for review. Catalog byte sizes can be stale after metadata rewriting, so they are not used alone as integrity proof.
8. **Real interfaces and fault injection are required evidence.** Unit and in-process tests were supplemented by live HTTP/MCP, real SQLite/Calibre files, independent identities, crashes via `os._exit` after actual durable checkpoints, and a fresh dependency/clone replay.
9. **Semantic RAG remains a separate milestone.** The verified tool uses lexical FTS. The local result does not establish permission-scoped embedding/index safety, server-operator privacy, arbitrary power-failure resilience, or production readiness.

These rationales come from source/session evidence and the existing reports. No deployment architecture or preferred future IdP beyond this disposable lab was selected.

## 7. Known defects, blockers, and security risks

**Discovered integration defects fixed and regression-tested:** restart restored revoked grants; repeated filenames reused old staging identities/visibility; missing JWT audience was accepted; empty metadata scopes broke MCP registration; recovery deleted the only valid copy; and a second recovery call could complete an incomplete review. Exact fix commits are in section 2 and RESULTS.md. Before-fix evidence remains in `evidence/revocation-before.log`, `oidc-audience-before.log`, `recovery-before.log`, and `review-before.log`. There is no separate retained before-log for every defect; do not invent one.

**Known failed wider checks, not resolved:** full CalibreMCP collection fails in `test_author_stats.py`, `test_db_init.py`, and `test_path_fix.py` due to passing filesystem paths into an SQLAlchemy URL parameter. The baseline reproduces these three errors. The saved [Windows CI failure](https://github.com/drkhn1234/calibremcp/actions/runs/42293201059) has the same collection errors (`evidence/calibremcp-ci-failure.log`).

After generating the repository's synthetic fixture, a wider selection (all unit tests plus MCP compliance, STDIO, server-integration and MCP-server modules) recorded:

| Source | Passed | Failed | Errors | Existing skips |
|---|---:|---:|---:|---:|
| Current | 217 | 32 | 11 | 6 |
| Original baseline | 216 | 32 | 11 | 6 |

Failure IDs match exactly (`evidence/baseline-comparison.json`). The additional pass is the OAuth metadata test. Broader problems include outdated legacy API/tool expectations, fixture/schema assumptions and STDIO setup. No failures were hidden or new skips added. Do not describe the whole repository as green. Legacy tests can scan libraries and must stay inside the documented Bubblewrap isolation if run in a future authorized session.

Saved branch-PR CI snapshots show green bridge-only checks and green Kolibre backend/React checks at the older feature-branch heads. **CI for the subsequently pushed development heads was not queried in this checkpoint**; those old CI snapshots do not prove current development-branch CI success.

Unverified requirements before any production/staging claim: third-party desktop/GUI/browser OAuth interoperability; refresh renewal; production/external IdPs and their registration/resource policies; production TLS/proxy configuration; threat model/security audit; rate/load behavior; permission-scoped semantic/vector indexes; real hardware/device sync; and arbitrary filesystem/power-failure behavior.

Native `/token` issuance currently defaults to **seven days** (`ACCESS_TOKEN_EXPIRE_MINUTES` in Kolibre auth.py). Expiry tests use a test-only shorter TTL; they do not change or endorse a production TTL policy. Generated provider certificates/keys and retained test databases are disposable and not deployment credentials. Root/server-operator access to stored book bytes is not prevented by application ACLs.

No external blocker prevents preserving this checkpoint. Remaining legacy failures and deployment uncertainties constrain future readiness, not completion of the demonstrated local milestone.

## 8. Exact next action and acceptance criteria

**Next action under the current request: stop after writing and checking this file. Await a new user instruction.** Do not start a next milestone, fix legacy failures, rerun the suites, create a PR, merge, or deploy automatically.

Checkpoint acceptance criteria: this file exists next to README.md/RESULTS.md; all six Git states and the two remote development HEADs are recorded; preserved local-only evidence/data locations and the test-versus-current-HEAD distinction are explicit; services and unresolved limitations are not invented; application/configuration/Git/deployment state is unchanged.

If the user later chooses review/integration, the first concrete action should be read-only comparison of each primary development branch with its originating feature branch and confirmation of the intended stacked PR target. There is currently no approved plan to move the new commits into the existing draft PR heads. Do not use the replay clones as push sources. If the user instead chooses deployment or OAuth/RAG work, obtain the actual target/scope from that new instruction; the completed local goal alone does not select or authorize an Oracle deployment.

## 9. Recovery instructions for a fresh agent session

1. Start at `/home/drkhn/Projects/kolibre-integration`. Read this checkpoint, README.md, RESULTS.md, AUDIT.md and COMMANDS.md. Respect the current checkpoint-only stop instruction until the user requests further work. The original local goal was marked complete; do not resume it merely because old reports mention future requirements.
2. Recheck primary Git HEAD/status and remote heads read-only; do not fetch/reset/switch/rebase or overwrite anything based solely on this snapshot. Primary application checkouts are `repos/Kolibre` and `repos/calibremcp`. The top-level lab is a separate local-only Git repo.
3. Preserve `evidence/` and the replay/baseline/temp directories. Existing log summaries prove the completed checks; do not rerun expensive suites just to regain context. `/tmp/.../pytest-current` is a mutable alias; this checkpoint's retained replay is specifically `pytest-23`.
4. For source inspection, start with `tests/test_live_native.py`, `tests/test_live_oidc.py`, `tests/test_live_move_recovery.py`; Kolibre `backend/app/services/{oidc_identity,legacy_permissions,private_book_move,private_move_recovery}.py` and related users/library-transfer APIs; CalibreMCP `src/calibre_mcp/kolibre_bridge/{server,client}.py`.
5. If the machine/workspace is lost, the source and lab snapshot are on the two pushed `dev/local-multiuser-integration` branches. Kolibre `integration/local/` contains setup/test scripts, lockfiles, patches and reports, but **not this checkpoint or the ignored raw evidence**. Reconstructing the local environment would require a future authorized setup execution. Do not assume the local top-level lab commits have their own GitHub remote.
6. Only after a new authorization requiring execution: follow README.md/COMMANDS.md in a fresh disposable lab. `setup.sh` can install/recreate a virtual environment and `test.sh` creates real processes and may overwrite summary logs; neither is a read-only context command. Review before use. Do not launch the repository's Compose configuration blindly or point any test at an existing library/production DB.
7. Preserve safety constraints: loopback-only disposable services/data, no production BookOrbit/Siyuan or existing Calibre libraries, no Oracle/VPS access or public deployment under the existing local task, no commits/pushes/merges under the current checkpoint instruction. If future authorized work involves Cloudflare, use `cf` CLI unless the project has a Wrangler configuration file.

This checkpoint intentionally remains an uncommitted local document. No implementation/deployment operation is pending when handing off.
