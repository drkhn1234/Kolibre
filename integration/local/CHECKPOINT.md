# Kolibre–CalibreMCP checkpoint — 2026-11-07

## 1. Current objective and status

The server-side ChatGPT MCP interoperability milestone is verified and ready
for an account-side connection attempt. **ChatGPT itself has not been connected
or observed.** The actual MCP client used was shipped Inspector 2.14.0, over
public HTTPS, with native and persistent Keycloak authentication.

Read [VPS_RESULTS.md](VPS_RESULTS.md) for exact results and security limits,
[CHATGPT.md](CHATGPT.md) for the minimal account-side action, and
[TASK_PLAN.md](TASK_PLAN.md) for milestone completion. Earlier local milestones
in RESULTS.md / INTEROPERABILITY.md are historical, explicitly labelled.
No PR was merged, production books imported, or paid resource provisioned.
The latest user authorized Oracle administration; earlier no-VPS/paused/checkpoint-only
instructions were superseded. This checkpoint does not authorize a new milestone.

## 2. Repositories and Git state

Workspace: `/home/drkhn/Projects/kolibre-integration`.
Source anchors below are exact inspected/tested commits **before subsequent
checkpoint/documentation publication commits**. Resolve those publication-only
HEADs with the Git commands in section 9; they do not alter deployed code.

| Repository | Active branch | Tested implementation anchor |
|---|---|---|
| Workspace Git root | dev/local-integration-lab | `08c50f0b922711955b5a0ddb28a82d36c5590887` |
| repos/Kolibre | dev/local-multiuser-integration | `c06a7cea001c853a9dfc74bd1e6e8ce627307e26` |
| repos/calibremcp | dev/local-multiuser-integration | `072c06541585dc494ad137faf84603f8d6617194` |

Both application development anchors were pushed and verified on GitHub.
The root lab has no remote. Its reviewed source/docs are published as an
`integration/local/` snapshot in the Kolibre development/OIDC PR branches.
Checkpoint publication commits are recorded in the final publication note.
Generated runtime state, keys, credentials, databases and raw evidence remain
ignored and are not included in that snapshot.

Relevant commits:

- Kolibre `c06a7ce`: require books:read after JWT signature verification;
  regression first reproduced five invalid-scope acceptances.
- Kolibre `b70c168`: bounded native token TTL; stage uses 15 minutes.
- Kolibre `0481db1`, `50e8a1b`, `de70f7f`, `337fc71`: durable permission
  revocations, isolated upload staging, required aud/iss/scoped JWKS trust,
  recovery that preserves valid copies. See historical reports for rationale.
- Calibre `072c065`: four read-only tool annotations and OAuth scope hints.
- Calibre `f01692e`: collect legacy Windows manual scripts safely (three
  unavailable-library skips, not passes); `bc1e932`: isolated logging path;
  `12ecf36`: advertise OAuth scopes.
- Lab `08c50f0`: optional bounded offline access, explicit scope/role associations,
  separate standard client/URL audience mappers and real two-user offline/basic
  refresh/privacy/revocation probes. Prior `ede9bf4`: real predefined-client/refresh/native-expiry probes, expiry CLI
  dispatch, narrow registration maintenance and reproducible provider bootstrap.

Draft stack is preserved without force pushes or main/master merges:
Kolibre #1 `feature/multiuser-ingest-boundary` → main, tested head
`1e12ea76f516a19882d41e5c3ee9686beba11e85` (67 tests); Kolibre #2
`feature/mcp-oidc-identities` → that foundation branch, tested application tree
at `d2eeba9b978a1e5878c2fd15d719013df2cb4a83` (same tree as c06a7ce).
Foundation safety fixes were cherry-picked, then merged into the OIDC feature
branch while retaining history. Later lab publication is docs/harness only.
Calibre #1 feature bridge branch fast-forwarded to 072c065 and remains draft
against master. All three descriptions were updated with actual tests/limits.

Additional worktrees, not deployment sources:
`runtime/pr-kolibre-foundation`, `runtime/pr-kolibre-oidc`, `runtime/pr-calibremcp`;
original detached Calibre baseline `runtime/calibremcp-baseline` at 131a29f;
`runtime/calibre-full-baseline` is an ignored Git-archive extraction with only
collection adapters/synthetic fixture for comparison. `runtime/replay-clean/`
contains the older independently reproduced checkouts; do not push their branches.

## 3. Running environment and configuration

`ssh oracle` uses existing authenticated Tailscale SSH as ubuntu; sudo works.
Do not read/copy private SSH keys. Ubuntu 24.04.5 ARM64, 2 CPUs, ~8 GiB RAM,
~76 GiB free disk; measured headroom remains sufficient. Existing Caddy provides
valid public HTTPS; no broad TLS bypass or system trust change is used.

| Service | Status | Endpoint / storage |
|---|---|---|
| kolibre-stage systemd | active/enabled | 127.0.0.1:18081; /var/lib/kolibre-stage |
| kolibre-mcp-stage systemd | active/enabled | 127.0.0.1:18082; separate unprivileged user; /var/log/kolibre-mcp-stage |
| kolibre-stage-idp systemd/Compose | active/enabled | Keycloak 26.8.2 on 127.0.0.1:18083; dedicated PostgreSQL 17.11/network/volume |
| Caddy | active | public books.drkhn.site HTTPS paths; /etc/caddy/kolibre-stage.routes |
| BookOrbit app/db + bookorbit-mcp | healthy/active | existing 3000/3001 and original mounts |
| Siyuan and siyuan-ladin | running | existing 6806/6807 and original workspaces |
| kolibre-stage-backup.timer | enabled | next scheduled daily snapshot; encrypted 7 daily/4 weekly/3 monthly retention |

Public MCP is `https://books.drkhn.site/kolibre-mcp-stage/mcp`.
API prefix is `/kolibre-api-stage/`. Issuer is
`https://books.drkhn.site/kolibre-auth-stage/realms/kolibre-stage`.
Exact discovery URLs are in CHATGPT.md. Normal native TTL is 15 minutes;
OIDC realm and predefined ChatGPT-client access-token TTLs are 300 seconds.
Temporary expiry-test settings were restored. Refresh rotation is enabled,
max reuse zero. Optional offline access for the predefined client/two synthetic
readers is configured for an eight-hour max and 30-minute idle timeout; provider
refresh expiry bounds and explicit revocation are verified, not the full
wall-clock lifetime. No migration or deployment process should remain running.

Current releases:
`/opt/kolibre-stage/releases/c06a7cea001c853a9dfc74bd1e6e8ce627307e26` and
`/opt/kolibre-mcp-stage/releases/072c06541585dc494ad137faf84603f8d6617194`.
Current symlinks point there. `/etc/kolibre-stage/revisions.json` now exists;
421 and 978 source files respectively match local Git archives by SHA256.
/etc/kolibre-stage/integration-revision.json separately records the deployed
helper source at lab commit 08c50f0 with five matching script SHA256 hashes.
Deployment helper scripts are separately under /opt/kolibre-stage/deployment.

Credentials/settings: root-only `/etc/kolibre-stage/` (0700, secret env/JSON
files 0600); local ignored `runtime/staging-credentials.json` and
`runtime/chatgpt-client.json` are 0600. Never print or commit them. Native and
OIDC synthetic passwords differ. Founder/sister are explicitly linked by
verified issuer/subject, never email. The provider bootstrap admin was removed.

Persistent stage SQLite, three synthetic EPUB libraries and indexes are under
`/var/lib/kolibre-stage`; Keycloak uses dedicated Docker volume
`kolibre-stage-idp-data` on its private network. No BookOrbit/Siyuan storage is
mounted into staging. Existing BookOrbit/Siyuan data mounts were compared with
the original inventory and remain unchanged. All internal stage ports are
loopback or private Docker only; public IdP admin/master routes are blocked.

Anonymous DCR still has trusted-source/URI checks, consent, scope/mapper guards
and max 24 clients. The workstation egress changed; the single approved address
is now 151.250.102.94 in both Caddy and Keycloak. Five obsolete fixed-loopback
probe registrations were removed, without deleting users/links/Inspector or
ChatGPT clients. Use update_test_ip.py only after measuring a changed address.
ChatGPT uses a predefined client; its source IPs are not granted anonymous DCR.

## 4. Completed and verified work

- Combined live lab: **21 passed, 1 warning, 495.64s**, before the offline follow-up. Includes native/OIDC privacy,
  real MCP clients, private transfer/crash recovery and persistent local Keycloak.
- Focused real Keycloak regression after the audience-mapper follow-up: **1 passed,
  177.01s**. Deployed basic and optional-offline scope refresh probes both pass:
  two users, concurrent MCP privacy and explicit refresh revocation. No app code
  changed after the combined 21-test run.
- Backend: **79 tests OK**, 9.484s; foundation PR: **67 OK**, 7.244s;
  compileall succeeds. Bridge/logging: **13 passed**, 2.57s. Full Ruff lint and
  format checks pass, 317 files. Frontend was unchanged; historical build result
  was inspected, not represented as newly rerun.
- Deployed predefined client: real code/S256 + exact callback/issuer; bad
  signature/issuer/audience/expiry coverage from live regressions; deployed bad
  secret/verifier/redirect/missing PKCE rejected. Two signed resource identities
  map correctly. Actual Inspector initialize/list/call exposes exactly four
  read-only tools, with concurrent shared/own-private access and foreign denial.
- Deployed genuine OIDC token expiry, existing-session rejection, refresh
  rotation/replay rejection, password reauthentication and reconnect pass.
  The harness passes refreshed tokens to Inspector; ChatGPT automatic refresh
  has not been observed.
- Deployed genuine native /token expiry passes for both users; password
  reauthentication restores own notes. No native refresh grant exists.
- Live shared permission removal affects successive calls and reconnects;
  private libraries remain isolated; reading state and annotations stay own-only.
- Final deployed actual Inspector DCR/code/PKCE flow also passes from the
  approved lab source, after the egress correction.
- BookOrbit's original OAuth and OIDC discovery documents compare equal;
  existing loopback health remains 3000=200, 3001 root=404, Siyuan roots=401
  expected. Existing containers and mounts are preserved.
- Earlier real VPS reboot evidence was inspected: changed boot ID, identical
  durable users/bindings/book hashes/counts/signing keys/client registrations.
  No extra reboot was needed. Current audit has zero active book moves.

Commands, output and evidence paths are in COMMANDS.md / VPS_RESULTS.md.
`verification/2026-11-07/` is a tracked credential-free compact record; raw logs,
JUnit and sanitized Inspector traces remain in ignored evidence/deployment.
Do not rerun eight-minute suites merely to reconstruct this checkpoint.

## 5. Work currently in progress

Server-side implementation/testing is complete. Documentation publication is
recorded below. The remaining functional action is the user's account-side
ChatGPT custom MCP connection and its actual model/tool/refresh acceptance test.
No implementation/deployment process or migration should be left in progress.

Unpreserved-by-Git material remains at exact ignored locations: .venv and
clients/inspector/node_modules; runtime/keycloak-download (local JDK/Keycloak/Caddy
artifacts); runtime/vps-validation/synthetic-state.json; private runtime JSONs;
runtime/staging-backup-identity.txt (offline recovery identity, 0600); evidence/;
repos/calibremcp/tests/fixtures/test_library/metadata.db (synthetic legacy-test
fixture); data/secret_key and data/server.log generated by local test imports.
These are not production user data. Do not commit them or overwrite existing
VPS credentials by rerunning initialize_host.py/seed.

## 6. Architectural decisions and rationale

- Kolibre remains the identity/ACL authority. The bridge resolves the bearer
  through /api/users/me and forwards that same token on every scoped API call;
  no user ID/email/JWT payload is trusted as proof of identity.
- Four restricted read-only tools only; no legacy global library selection,
  filesystem or unfiltered vector RAG. Full text is lexical FTS.
- Explicit owner-password-confirmed linking, RS256 iss/aud/exp/sub checks and
  books:read scope; admin status never grants another reader's private library.
- Persistent Keycloak/PostgreSQL replaces the disposable test provider on VPS.
  Native credentials stay separate. Scoped local CA is for disposable tests;
  public traffic uses normal validated certificates.
- Separate standard audience mappers are required: Keycloak chooses client OR
  custom audience in a single mapper. Offline refresh exposed the missing URL;
  configuration was corrected without relaxing the verifier.
- Predefined confidential ChatGPT client with exact OpenAI callback, consent,
  required S256 and refresh rotation avoids opening anonymous DCR to the internet.
  A client secret identifies the application; it does not replace per-reader login.
  CIMD was not enabled merely to bypass safeguards.
- Existing validated books.drkhn.site paths were reused because new DNS was not
  available; no Cloudflare zone migration. Separate storage/users/network/proxy
  routes preserve existing applications. This is not browser-origin isolation.
- Move journals/checksums preserve a valid copy and fail safely for damaged or
  ambiguous states. Own progress/notes follow; foreign device/notes do not.

## 7. Known defects, blockers, and security risks

- Actual ChatGPT UI/account/workspace OAuth behavior and automatic refresh remain
  **not tested**. Follow CHATGPT.md; do not claim an existing ChatGPT connection.
- Full Calibre suite is **not green**: final 285 passed / 42 failed / 23 errors /
  10 skipped. Original baseline with identical collection adapter has 283 passes
  and exactly the same 61 distinct unsuccessful IDs. Three unavailable external
  Windows-library manual checks are disclosed skips. See durable comparison.
- GitHub bridge-isolation workflow passed, general Calibre CI failed (Windows
  missing metadata fixture and legacy failures). Kolibre multi-user checks passed
  at d2eeba9; later documentation checks may still be pending.
- DCR availability depends on the lab's approved egress and bounded registration
  count. Predefined ChatGPT registration does not depend on that gate.
- Existing encrypted snapshot/timer is observable, but no separate durable full
  replacement-host restore transcript was found. Previous restore assertions are
  not upgraded to verified disaster recovery. Off-host replication remains open.
- Shared browser origin, experimental resource-indicators, complete security/load
  review and fine-grained direct-HTTP write-scope delegation require review before
  production. books:read is an authentication gate, not a new write-scope system
  across every Kolibre endpoint; the MCP surface itself is read-only.
- JWTs are not introspected for immediate provider logout. Live library ACL/link
  changes apply immediately; other revocation can be bounded by token lifetime.
  Previously returned client content cannot be recalled by permission removal.
- Semantic RAG and production content/user onboarding remain separate milestones.

## 8. Exact next action and acceptance criteria

Use CHATGPT.md to add the HTTPS MCP endpoint as a custom server with predefined
client kolibre-chatgpt-stage, privately supplied client secret and each reader's
own Keycloak login. Do not send credentials through a chat. If account policy
hides this option, record the exact account-side limitation; do not weaken DCR.

Accept when actual ChatGPT discovers exactly four tools, successfully invokes
shared/own-private content and own annotations for two separately authenticated
users, denies guessed foreign private identifiers, observes live shared grant
revocation across reconnect, and successfully refreshes or reauthenticates after
expiry without identity crossover. Record model tool choices and outcomes.
No PR merge or real-content import is part of that action.

Then prioritize a security/delegation review, separate-origin plan and a full
restore/off-host backup drill before production use. Do not jump directly to
semantic RAG or production migration from unit-test success.

## 9. Recovery instructions for a fresh agent session

1. Start in /home/drkhn/Projects/kolibre-integration. Read this checkpoint,
   VPS_RESULTS.md, CHATGPT.md, TASK_PLAN.md, COMMANDS.md and DEPLOYMENT.md.
2. Run `git status --short --branch`, `git rev-parse HEAD`, and `git log -5 --oneline`
   in the workspace and both repos; inspect `git worktree list`. Resolve any later
   docs-only publication HEADs and compare application paths to c06a7ce/072c065.
   Do not reset, overwrite checkouts or repush replay branches.
3. `ssh oracle` then read-only systemctl/Docker/listener/source-manifest checks
   reconnect to an existing deployment. Do not initialize, seed, rebuild or reboot
   merely to resume. Credentials stay in private local/root files.
4. Use existing logs, JUnit and verification/ compact records. .venv Python is
   3.12; actual Inspector uses its private pinned Node binary. Local provider
   setup is checksum-pinned via bash deployment/setup_local_keycloak.sh; H2 is
   local-test-only. setup.sh is a bootstrap, not a read-only inspection command.
5. Validate expiry probes sequentially; they temporarily adjust only staging
   TTLs and restore them. Never interrupt before their finally/trap cleanup.
   Check realm/client=300s and native=15min afterwards. Native expiry briefly
   restarts only the staging backend.
6. If changing code, preserve source revisions and privacy regressions. No
   unauthorized PR merges, real-user/library import or paid provisioning. Keep
   BookOrbit/Siyuan mount and discovery checks in the final audit.

## Publication note

This checkpoint captures tested implementation anchors. Its own commit and
subsequent packaging commits necessarily follow those anchors; their exact
hashes can be obtained from Git without rerunning completed tests. No credentials,
JWTs, signing keys, databases or private book contents belong in Git.

Final publication audit (captured before the final documentation-only record):
workspace HEAD `c7d145312565321cbd759e29b95209617245b2d6`;
Kolibre development HEAD `f16521209f029229feb7dbf3697c662336daa319`;
OIDC PR HEAD `646f6f546d8bdce903852c7bc8ce5fba15603eb3`;
foundation PR HEAD `1e12ea76f516a19882d41e5c3ee9686beba11e85`;
Calibre development/PR HEAD `072c06541585dc494ad137faf84603f8d6617194`.
These were clean and pushed; OIDC/development trees matched. The final docs-only
publication commit necessarily follows this captured state. Its SNAPSHOT.md
records the exported lab revision. Deployed application/helpers remain the exact
implementation anchors above. See verification/2026-11-07/publication.json.
No local lab provider, Inspector daemon, test/probe runner or migration remained
at final inspection. Existing VPS services remain active/healthy. A final
client_secret_basic code/refresh/revocation probe also passed; POST was verified
separately. Both client authentication methods retain per-reader identity.
