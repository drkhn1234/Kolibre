> New knowledge-retrieval milestone: see [KNOWLEDGE.md](KNOWLEDGE.md) for current sources, fifth-tool staging tests and limitations; [CHATGPT_ACCEPTANCE.md](CHATGPT_ACCEPTANCE.md) records the actual four-tool ChatGPT acceptance. Earlier results below remain historical.

# Local integration results — 2026-11-07

Current status: persistent Oracle staging and server-side ChatGPT OAuth
preparation are verified. See [VPS_RESULTS.md](VPS_RESULTS.md),
[CHATGPT.md](CHATGPT.md) and [CHECKPOINT.md](CHECKPOINT.md). Final current live
suite: **21 passed**, one warning, **495.64s**. Backend: **79 tests OK**;
restricted bridge: **13 passed**. Full CalibreMCP: **285 passed, 42 failed,
23 errors, 10 skipped**; identical unsuccessful IDs on the original baseline.
Actual ChatGPT account connection remains untested. Statements below describe
historical milestones and their limitations at that time.


## Historical local milestone: independent MCP client interoperability

**Passed:** the final combined local suite completed **18 passed, 1 existing warning in 312.40 seconds**. This includes all 15 prior live integration scenarios plus three new scenarios using the shipped **MCP Inspector 2.14.0 `mcpdo` terminal client**, run with private Node 22.23.4. Command: `.venv/bin/python -m pytest tests -v --tb=short --junitxml=evidence/client-milestone-junit.xml`; output: `evidence/client-milestone-full.log` and the matching JUnit XML.

Inspector negotiated MCP **2025-11-25**, discovered exactly the four allowed tools, and made actual tool calls in simultaneous native and OIDC sessions. Both users accessed shared/own private books, lexical full text and their own notes; foreign private identifiers returned tool errors. Live revocation, stale-list requests, reconnect while revoked, genuine token expiry within existing sessions, and fresh authentication/reconnection passed. Inspector independently performed OIDC discovery, DCR, S256 PKCE, state checking, loopback callback, exchange and token persistence. Only the synthetic provider login/consent interaction was automated.

Final sanitized transcripts record **94 Inspector commands**, **36 successful tool calls**, **20 expected library-authorization errors**, **3 expected expired-auth call failures**, and four completed OAuth callbacks (two users, initial sign-in and reauthentication). All five disposable client profiles stopped their daemons. Evidence: `evidence/inspector/*.json`, `evidence/inspector-summary.json`. Separate unchanged-provider regression: **3 passed**, 1 existing warning, 36.85 seconds (`evidence/oidc-regression.log`). Static checks passed (`evidence/client-static-checks.log`).

**Failed, diagnosed and corrected:** the first harness supplied mutually exclusive Inspector catalog options; a later 45-second test JWT was immediately stale to Inspector's 60-second expiry margin. The harness now uses only its explicit private config and genuine 120-second provider tokens for the expiry scenario. No client security check or authorization assertion was weakened. No Kolibre/CalibreMCP application defect was confirmed and no application-code change was needed. The bounded optional TTL setting is in the disposable provider only; its default remains 300 seconds.

**Not tested:** desktop chat applications and browser rendering, refresh-token renewal (disabled in the expiry client), external/persistent IdPs, deployed HTTPS proxy behavior, ARM artifacts, load/security review, and semantic/vector RAG. Existing wider CalibreMCP failures below remain unresolved; those suites, backend unit tests, and React build were not rerun during this milestone because application code was unchanged.

Read [INTEROPERABILITY.md](INTEROPERABILITY.md) for exact coverage, setup failures and limits. [ORACLE_STAGING_PLAN.md](ORACLE_STAGING_PLAN.md) specifies the proposed capacity, ports, HTTPS, IdP gate, storage, backups and isolation. **No Oracle access or deployment occurred.** The new milestone changes are local, uncommitted and unpushed. Prior application fixes and the earlier harness snapshot were already pushed to both `dev/local-multiuser-integration` branches; no merge has occurred. [CHECKPOINT.md](CHECKPOINT.md) records current state; the historical evidence below is preserved.

## Original local integration milestone

The requested local two-user integration is demonstrated on running components and reproduced from a clean checkout. This report makes no production-readiness claim. No Oracle VPS, public deployment, production BookOrbit/Siyuan, or existing Calibre library was accessed.

## Passed

| Verification | Actual output | Evidence |
|---|---|---|
| Clean bootstrap and full live suite | **15 passed** in 83.36s | `evidence/replay-setup.log`, `evidence/replay-integration.log` |
| Original and replay source trees | Both repositories identical | `evidence/replay-source-trees.json` |
| Backend compilation and full backend suite | **76 tests, OK**, compileall exit 0 | `evidence/replay-backend.log`, `evidence/kolibre-after.log` |
| Restricted bridge suite | **12 passed** | `evidence/replay-bridge.log` |
| Full CalibreMCP Ruff lint and formatting (`src tests`) | All checks passed; 316 files formatted | `evidence/replay-ruff.log`, `evidence/replay-format.log` |
| React dependency install, TypeScript and Vite build | Build successful | `evidence/frontend-install.log`, `evidence/frontend-build.log` |
| Exact account roles and library ownership | Founder admin; sister ordinary; shared owned by founder; one private library per owner | `evidence/ownership-audit.json` |

The live suite uses real HTTP processes, real SQLite/Calibre-format databases, actual native password logins, an HTTPS OIDC provider, and real FastMCP HTTP/OAuth clients. It does not override authorization dependencies. All listeners use loopback. Docker was unavailable; isolated local processes and Python environments provide the reproducible equivalent.

### Two independent users

| Operation | Founder | Sister |
|---|---|---|
| Shared catalog and full-text search | Allowed | Allowed |
| Founder's private catalog/search | Allowed | Denied |
| Sister's private catalog/search | Denied | Allowed |
| Own annotations | Allowed | Allowed |
| Other reader's annotations | Absent; foreign update denied | Absent; foreign update denied |

Six concurrent native sessions, four concurrent OIDC sessions and two independent OAuth clients exercise separate identities. Exact MCP tool discovery exposes only `kolibre_list_libraries`, `kolibre_list_books`, `kolibre_search_fulltext`, and `kolibre_my_annotations`. No unrestricted legacy tools, path selection, global library switching, or vector operations are mounted.

Tests cover guessed foreign-library identifiers, own-only annotations, direct Kolibre HTTP, separate OPDS Basic credentials, live permission revocation within existing sessions, revoked access after backend restart, and stale shared full-text results after a book becomes private. No foreign content appears in the concurrent responses.

### Authentication

Pinned node-oidc-provider **9.13.3** performs actual DCR, authorization code + required S256 PKCE and RS256 JWT access-token issuance for the MCP resource audience. An incorrect PKCE verifier is rejected. Each external subject is rejected before explicit native-login/password-confirmed linking; linked access resolves the correct Kolibre account. Cross-account binding returns 409; wrong native password returns 401.

Missing/malformed tokens, invalid signatures, expired tokens, wrong issuer/audience, missing issuer/audience/expiration/subject, and unlinked identities return 401 through running HTTP and MCP endpoints. Both genuine native `/token` issuance with a test-only short TTL and a short-lived signed OIDC token are accepted at session start and rejected after expiration during the same MCP session. Negative JWT variants use the disposable provider's key; ordinary login tokens come from its actual code flow.

The real FastMCP OAuth client performs protected-resource/issuer discovery, DCR, state/PKCE handling, exchange and storage. Only user interaction is automated: isolated HTTP cookie jars submit the separate synthetic passwords and consent. GUI browser and third-party desktop compatibility are not claimed.

Generated TLS/signing keys use mode-0600 temporary files. Default TLS trust rejects the generated certificate; explicit SSL contexts and `KOLIBRE_OIDC_CA_BUNDLE` provide scoped trust. TLS verification stays enabled. No global trust store changes occur. Both native and OIDC tokens work on the same restricted server.

### Uploads, moves and failure recovery

Synthetic EPUBs are uploaded/imported shared and privately through the application. Private staging cannot be redirected into shared. Tests inspect actual EPUB placement and real `metadata.db` files.

Both founder and sister move a shared book to their own private library. The EPUB bytes survive unchanged. Only the mover's reading progress, annotation IDs and device-book association follow it; the other user's state remains attached to shared. HTTP reads, MCP notes and SQLite association checks verify this behavior.

A test launcher wraps only the real durable journal checkpoint and calls `os._exit(89)` after its commit, preventing exception compensation. Tests confirm process exit, age the stopped journal by three minutes to exercise the recovery endpoint without sleeping through its concurrency guard, restart normally and recover using the owner's token. Crash at `ready` rolls back; crash at `source_deleted` finishes the owner's state. Repeated recovery is idempotent and founder cannot read/recover sister's journal. No destructive retry remains queued.

Missing, truncated and same-size-corrupted source files preserve the valid private EPUB and produce `needs_review`. A review state from an incomplete copy cannot become completed merely by retrying recovery. Shared full-text no longer returns moved private content.

## Failed, fixed and retested

All fixes below are commits on the pushed `dev/local-multiuser-integration` branches; reproducible patch files are included. The earlier claim that they were not pushed predates the user's completed GitHub-sync request. Nothing was merged or deployed.

| Defect | Exact fix commit | Regression evidence |
|---|---|---|
| Restart restored revoked library access | Kolibre `0481db182f5c935bcd3bf463d1bf9abee94027b4` | `evidence/revocation-before.log`; live restart + migration tests |
| Repeated filename reused an imported staging row and its old visibility | Kolibre `50e8a1b9ffdc5d1b38ada4d263d4a7f0b78ff704` | Repeated-upload unit regression; actual shared/private ingest |
| Signed OIDC token without audience was accepted | Kolibre `de70f7fe3e9444f5598383aa1d16d4468fc941e1` | `evidence/oidc-audience-before.log`; mandatory-claim live matrix; also adds scoped JWKS CA support |
| Empty advertised scopes broke MCP OAuth client registration | CalibreMCP `12ecf368644609156d4f16ba9e43663284b79153` | HTTP metadata regression; actual client DCR/code/PKCE test |
| Recovery deleted the only valid copy when source files were missing; retry promoted incomplete review to completion | Kolibre `337fc711e87c3682047e4d8bfe0d2ce3dcd5a407` | `evidence/recovery-before.log`, `evidence/review-before.log`; real-file integrity regressions and live crashes |

Recovery rollback now checks actual source files and full SHA-256 equality against registered target copies. Catalog sizes alone are unreliable after EPUB metadata rewrites. Ambiguity preserves copies for review rather than authorizing deletion. This is failure-safety evidence for the tested boundaries, not a complete storage/crash-consistency proof under arbitrary filesystem mutation or hardware failure.

## Failed: pre-existing wider-suite failures

Full CalibreMCP pytest collection still fails in `test_author_stats.py`, `test_db_init.py`, and `test_path_fix.py`: they pass filesystem paths where SQLAlchemy expects URL strings. The same three failures occur on the original branch and in [the existing Windows CI run](https://github.com/drkhn1234/calibremcp/actions/runs/42293201059). Raw logs: `evidence/calibremcp-wide-{current,baseline}.log`, `evidence/calibremcp-ci-failure.log`.

After generating the repository's synthetic fixture, all unit tests plus its MCP compliance, STDIO, server integration and MCP-server test modules were also executed:

| Source | Passed | Failed | Errors | Existing skips |
|---|---:|---:|---:|---:|
| Current | 217 | 32 | 11 | 6 |
| Original baseline | 216 | 32 | 11 | 6 |

Failed-test IDs match exactly; the extra current pass is the new OAuth metadata regression. Failures include outdated legacy method/tool expectations, fixture/schema assumptions and STDIO process setup. No failing assertions were weakened and no skips were added. Logs: `evidence/calibremcp-fixtures-tests-{current,baseline}.log`; comparison: `evidence/baseline-comparison.json`.

These legacy checks ran inside Bubblewrap with personal files/mounts hidden and networking isolated. Both source revisions pass full Ruff lint/format. Existing bridge-only CI is green; Kolibre PR #2 backend and React CI are green (`evidence/*-pr-ci.json`). The broader repository is not represented as green.

## Not tested / future deployment requirements

- Third-party GUI OAuth clients, real browser UI, refresh-token renewal, external/production IdPs and their registration/resource policies.
- Semantic/vector RAG and permission-scoped embedding indexes. The verified tool is lexical full-text search.
- Formal security review/threat modeling, broader endpoint audit, rate limiting/load tests, production TLS/proxy configuration, hardware/device synchronization and arbitrary disk/power-failure behavior.
- Oracle staging, public deployment, and real user libraries. These need a separately authorized future phase and remain untouched.

## Sources and reproduction

Kolibre baseline: `345419c29dccf1557b892ae61676e02f1dc37a06`, branch `feature/mcp-oidc-identities`, verified to contain `feature/multiuser-ingest-boundary`. CalibreMCP baseline: `131a29f562365e62f66165e3ad56ec49dbde350d`, branch `feature/kolibre-authenticated-mcp-bridge`.

Environment: Ubuntu 26.10 x86_64, Python 3.12.14, Node 22.23.2, FastMCP 3.4.11, MCP SDK 1.30.0. Dependencies are pinned in `requirements.lock` and `oidc/package-lock.json`. Original/replay Git trees are identical: Kolibre `9be2f844fd55a597ecdc1ae426273fee336cd655`, CalibreMCP `a04e917a6c39fe6a1c617f93a79ef01481c60d43`.

Run `./setup.sh` then `./test.sh`. See [README.md](README.md), [COMMANDS.md](COMMANDS.md) for executed commands, and [AUDIT.md](AUDIT.md) for requirement-by-requirement evidence. The fresh clone/venv replay is retained under `runtime/replay-clean` for inspection; raw logs are under `evidence/`.

## Import-page crash fix — 2026-11-07

User screenshot: ImportPage-oJfs3mIn.js:1:19508 `Cannot read properties of
undefined (reading 'length')`. Deployed API for both users returns
`{"running":false}` when no job is owned by that reader. Frontend's unchecked
IngestImportJob cast caused lavoro?.failed.length to dereference undefined.
The job query now normalizes an idle shape, preserving real progress/errors.
Backend privacy response is unchanged. Two Node regression tests pass and
TypeScript/Vite build passes. Corrected web bundle deployed without backend,
bridge or KOReader restart; served chunk matches build SHA256. Browser rendered
page not observed through automation. User should reload the crashed page.
This fixes the Import crash, not an independently demonstrated EPUB reader bug.
See verification/import-ui-fix-2026-11-07.json and frontend-react/tests/ingestImportJob.test.mjs.

## Import drag-overlay flicker — 2026-11-07

User's six-second local screencast shows Import's drop overlay repeatedly appearing
and disappearing as a file is dragged inside it. Source had an event-targetable
overlay plus an unconditional bubbling dragleave reset. Fix: pointer-events-none
on the visual overlay; count nested file dragenter/dragleave transitions; clear
state on drop and advertise a copy operation. Non-file drags do not trigger the
overlay. File upload, visibility selection and backend behavior unchanged.
TypeScript/Vite build and diff whitespace checks pass. Updated immutable web
bundle deployed and served content matches local build. Post-fix interactive
browser reproduction remains for ordinary user retry; no claim of observed GUI
success. Raw recording/extracted frames stay local and untracked. Compact proof:
verification/import-drag-fix-2026-11-07.json.
