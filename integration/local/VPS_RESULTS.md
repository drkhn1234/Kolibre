# Oracle staging and ChatGPT protocol results — 2026-11-07

**Server-side preparation passed. Actual ChatGPT account connection is not
tested.** Public HTTPS and per-user authorization were exercised with the
shipped MCP Inspector 2.14.0 on Node 22.23.4, not a mocked MCP transport.
Instructions and official requirements are in [CHATGPT.md](CHATGPT.md).

## Deployed source and environment

| Component | Exact deployed Git commit | Internal listener |
|---|---|---|
| Kolibre | `c06a7cea001c853a9dfc74bd1e6e8ce627307e26` | `127.0.0.1:18081` |
| Restricted CalibreMCP | `072c06541585dc494ad137faf84603f8d6617194` | `127.0.0.1:18082` |
| Keycloak 26.8.2 | pinned image in deployment/compose.yml | `127.0.0.1:18083` → container 8080 |
| Dedicated PostgreSQL 17.11 | pinned image in deployment/compose.yml | private Docker network only |

Both source trees were verified file by file against local Git archives:
**421 backend-repository files and 978 bridge-repository files**. The previously
missing `/etc/kolibre-stage/revisions.json` now records commit IDs, release
locations and every source-file SHA256. Evidence:
`evidence/deployment/{revisions,source-verification}.json`.
The deployed provider/maintenance helpers separately match lab commit 08c50f0;
`/etc/kolibre-stage/integration-revision.json` and tracked integration-source.json
record their five checked SHA256 hashes.

Ubuntu 24.04.5 ARM64, 2 CPUs, about 8 GiB RAM; final observed 6.3 GiB available,
76 GiB disk available. Backend and bridge are separate unprivileged systemd
services with filesystem restrictions. Persistent state is in
`/var/lib/kolibre-stage` and dedicated `kolibre-stage-idp-data` Docker volume.
All public traffic uses existing validated Caddy HTTPS on books.drkhn.site.
Internal databases/backend ports remain unexposed. No paid resource was created.

## Passed against running components

| Command/check | Actual result | Local evidence |
|---|---|---|
| `.venv/bin/python deployment/chatgpt_probe.py` with the predefined client's temporary 120s TTL | PASS: exact callback and issuer, code/S256, bad secret/verifier/redirect/missing PKCE rejection, real RS256 resource tokens, two mapped users | `evidence/deployment/chatgpt-protocol.log` |
| Same probe, actual Inspector initialize/list/call | Exactly four read-only tools and OAuth scope hints; shared/own-private catalog/FTS and own notes succeed; foreign private catalog/search/notes denied; concurrent sessions and direct reading-state checks pass | `chatgpt-protocol-{founder,sister}.json` |
| Same probe, live shared permission removal | Subsequent catalog/search/notes calls fail, stale library disappears, reconnect remains denied, private library still works; restore works | same traces |
| Same probe, real elapsed OIDC expiration | API and MCP return 401; existing Inspector sessions cannot call tools | same log/traces |
| Same probe, refresh and reauthentication | Refresh succeeds after access-token expiry with same signed subject/audience/scope; refresh token rotates; old refresh token replay returns invalid_grant; new code login/reconnect preserves private notes | same log/traces |
| `.venv/bin/python deployment/native_expiry.py` | PASS: genuine HTTP-issued native tokens expire at API/MCP and existing Inspector sessions for both users; new password login/reconnect restores own notes | `native-expiry.log`, `native-expiry-{founder,sister}.json` |
| `PYTHONPATH="$PWD/repos/Kolibre/backend" .venv/bin/python -m unittest discover -s repos/Kolibre/backend/tests -p 'test_*.py' -v` | **79 tests, OK**, 9.484s | `kolibre-unit-chatgpt.log` |
| Same unittest suite on foundation PR head | **67 tests, OK**, 7.244s | `foundation-pr-tests.log` |
| Focused bridge/logging pytest | **13 passed**, 28 warnings, 2.57s | `bridge-chatgpt.log` |
| `pytest tests/test_live_oidc.py tests/test_deployment_cli.py` in lab | **5 passed**, one existing warning, 37.86s | `oidc-chatgpt.log`, matching XML |
| Backend compileall; full bridge Ruff check and format check | Exit 0; all checks pass, **317 files** already formatted | executed this milestone; focused output above |

Combined local command (before the final offline-scope follow-up):
`.venv/bin/python -m pytest tests -q --tb=short --junitxml=evidence/deployment/chatgpt-local-all.xml`
completed **21 passed, 1 warning, 495.64s**. It includes all prior native,
OIDC, move/crash recovery, Inspector and local persistent-Keycloak scenarios,
plus the two expiry-command regressions. Evidence: `chatgpt-local-all.log`/XML.

Final `.venv/bin/python deployment/validate.py verify-oidc` also passed against
the deployed sources after the source-IP update: actual Inspector discovery,
DCR/code/S256, concurrent privacy, reading state, revocation and reconnection.
Evidence: `public-oidc-final.log`. This is separate from the predefined-client
probe and still does not establish registration from ChatGPT's infrastructure.

After the offline follow-up, the focused real local Keycloak regression was
repeated: **1 passed, 177.01s**, including discovery/DCR/PKCE/resource validation,
MCP privacy/revocation, restart and expiry. Evidence: keycloak-mapper-final.log/XML.
No backend/bridge application code changed after the 21-test run.

Additional deployed commands, after the final audience-mapper correction:
`deployment/offline_probe.py` and `deployment/offline_probe.py --scope basic`
both **PASS**. Each performs two real code/refresh flows and actual concurrent
Inspector private-content isolation. Offline refresh rotation and explicit
revocation pass; provider refresh_expires_in is <=28800s. The configured maximum
is eight hours with 30-minute idle timeout; those full wall-clock limits were
not waited out. Only the predefined ChatGPT client and the two synthetic reader
roles were enabled for optional offline access. Anonymous DCR scope policy was
not broadened. Evidence: offline-scope-fix.log, basic-refresh-mapper-final.log,
final-auth-settings.json.

The ChatGPT client has been restored to **300s** access tokens. Realm TTL is
also 300s. Native TTL has been restored to **15 minutes**. Refresh rotation is
enabled with max reuse zero. Native Kolibre has no refresh-token grant; native
clients must log in again. Inspector was given freshly refreshed tokens by the
protocol harness; this does not establish ChatGPT's automatic-refresh behavior.

## Expiry exit code 2: resolved command defect

`deployment/validate.py` previously accepted only `seed`, `verify-native` and
`verify-oidc`. Invoking `verify-expiry` was rejected by argparse before any
authentication request. `deployment/expiry.py` was the separate working runner;
its historical `public-expiry.log` contains a pass. The documented command now
dispatches to that runner and propagates failures. Two new CLI regressions pass.
The new predefined-client and native probes above independently verify deployed
expiration; no need to repeat the older two-minute runner solely for its alias.

## Full CalibreMCP suite: executed, not green

Command, from `repos/calibremcp`:

```sh
../../isolated-check.sh ../../.venv/bin/python -m pytest tests --no-cov -q \
  --tb=short --junitxml=../../evidence/deployment/calibre-full-final.xml
```

Final application head `072c06541585dc494ad137faf84603f8d6617194`:
**285 passed, 42 failed, 23 errors, 10 skipped, 1931 warnings, 19.46s; exit 1**.
355 items were collected; JUnit includes additional setup/teardown reports and
a module skip. Do not interpret 360 JUnit entries as 360 collected tests.

Baseline `131a29f562365e62f66165e3ad56ec49dbde350d`, same isolated environment,
same synthetic metadata fixture and **only the identical three-script collection
adapter from f01692e**: **283 passed, 42 failed, 23 errors, 10 skipped, 17.79s**.
The adapter wraps old import-time manual Windows-library scripts and skips those
three checks when their external library is absent; these skips are disclosed,
not counted as passes. The unadapted baseline still fails collection with three
SQLAlchemy path/URL errors. No application fixes were applied to the baseline.

All **61 distinct unsuccessful IDs** match between current and baseline; the
development branch adds two passing cases. Existing failures include legacy
FastMCP `.fn`/tool-name expectations, obsolete fixtures or patch targets,
Windows path-as-URL use, absent calibre_plugins, old API/error wording, external
legacy server assumptions and logging assertions. No restricted bridge failure
was observed. These remain legacy-suite failures in this environment, not a
claim that upstream CI is green. New GitHub CI runs are separate evidence.

Observed GitHub checks at bridge 072c065: [restricted isolation workflow passed](https://github.com/drkhn1234/calibremcp/actions/runs/42380193748),
while [general CI failed](https://github.com/drkhn1234/calibremcp/actions/runs/42380193647).
Its Windows job reported 207 passed / 31 failed / 108 errors / 10 skipped;
many errors explicitly cite the missing synthetic metadata fixture. Kolibre's
[multi-user checks passed](https://github.com/drkhn1234/Kolibre/actions/runs/42380192741)
at the tested OIDC PR head d2eeba9. These are observed run results, not a
promise that later documentation commits have already completed CI.

Raw logs/JUnit/comparison: `evidence/deployment/calibre-full-{current,baseline,final}.*`
and `calibre-full-comparison.json`. A compact credential-free result record is
tracked under `verification/2026-11-07/` so conclusions survive a fresh clone.

## Corrected failures and operational findings

- Signed tokens without the required read scope were accepted by Kolibre.
  Regression reproduced **five acceptances** before the fix. Required
  `books:read` is now checked after cryptographic verification, including
  malformed/missing/prefix-only scope variants. Native authentication is separate.
- The first new negative PKCE probe used an invalid-length verifier and expected
  a narrower OAuth error set. It was corrected to a valid-length wrong verifier;
  bad-secret rejection also permits Keycloak's unauthorized_client error.
  No access token may be returned. Attempt preserved in
  `chatgpt-protocol-attempt1.log`; successful run is clearly separate.
- A request including advertised offline_access returned invalid_scope. Keycloak
  requires explicit client-scope association updates; updating the client
  representation alone does not attach it. The minimal imported users also
  lacked the offline_access role. Both were configured only for the predefined
  client/two synthetic readers, with bounded offline sessions.
- Offline refresh then returned only the logical client audience, correctly
  rejected by Kolibre. Inspection of Keycloak 26.8.2 AudienceProtocolMapper
  [confirmed](https://github.com/keycloak/keycloak/blob/26.8.2/services/src/main/java/org/keycloak/protocol/oidc/mappers/AudienceProtocolMapper.java) that client audience takes precedence over custom audience in one
  mapper. Separate standard mappers now include both, preserving exact URL
  validation. Normal and offline refresh/privacy and the local Keycloak
  regression pass. Earlier attempts are retained in offline-scope-*-before.log
  and advertised-scope-probe.log. This was fixed in lab commit
  `08c50f0b922711955b5a0ddb28a82d36c5590887`; application source commits stay
  c06a7ce/072c065. No audience fallback or unchecked JWT identity was added.
- The lab's egress IP changed from the previously approved address. The DCR
  check correctly returned HTTP 403 at Caddy. Both Caddy and Keycloak's trusted
  source list were updated to the measured new **single** address using
  `deployment/update_test_ip.py`; no broad registration exception was added.
- Five obsolete fixed-loopback probe registrations were removed with the narrow
  `prune_probe_clients.py` filter to avoid exhausting the existing 24-client
  registration limit. No reader, OIDC link, predefined ChatGPT client, or
  Inspector client was deleted. Hash-only deletion evidence is retained.

## Persistent deployment evidence preserved

The earlier authorized VM reboot changed boot ID; before/after audit shows the
same user bindings, EPUB hashes, database counts, signing-key fingerprints and
registrations (only boot/PID fields differ). There are four highlights, two
reading positions, two device-book associations and zero active private moves.
These historic evidence files were inspected, not recreated by another reboot.

Encrypted stage backups have 7 daily / 4 weekly / 3 monthly retention, a private
age recipient on the VPS and offline private identity only on the workstation.
Timer is enabled; existing snapshot `20261107T121104Z.tar.gz.age` is present.
The previous document claims a restore drill, but this milestone found no
separate durable restore transcript; do **not** treat that as a newly verified
full disaster-recovery rehearsal. Reboot/data persistence is directly supported
by the retained audits. Updated credentials/configuration will enter the next
scheduled encrypted snapshot; the earlier snapshot predates this milestone.

Existing BookOrbit and Siyuan remain healthy on their original ports and mounts.
Only staging services were restarted for this milestone; a graceful Caddy reload
updated the source-IP gate. No production book import, unrelated data deletion,
VM rebuild, new paid resource or PR merge occurred.

## Not tested / unresolved

- Actual ChatGPT account creation/linking, workspace policies, automatic refresh,
  model-selected tool calls and cached ChatGPT transcripts after revocation.
- CIMD and ChatGPT-origin DCR; predefined registration is the prepared path.
- Semantic/vector RAG, load testing, full security audit, real-user onboarding,
  verified-email workspace restrictions and production data import.
- A full restore into a clean replacement host and off-host automated backup
  replication. The private recovery identity must be backed up separately.
- Staging shares a web origin with BookOrbit. Paths/storage/services are isolated,
  but this is not browser-origin isolation; separate production origins remain
  advisable. The experimental Keycloak resource-indicators feature is still used.
- `books:read` gates external JWT authentication; there is no new fine-grained
  write-scope design for all Kolibre HTTP APIs. Only the MCP tool surface is
  asserted read-only. Review direct API delegation boundaries before production.
- Access tokens are locally verified JWTs, not introspected for immediate IdP
  logout. Library ACL/link changes are checked live; other JWT revocation can
  remain bounded by its short lifetime. Returned content cannot be recalled
  from a client's already-received transcript.

Bootstrap patch reconstruction was checked without reinstalling dependencies:
102 tracked Kolibre backend/test files and 335 bridge source/test files matched
the tested repositories exactly after all patches applied with zero fuzz. The
pinned local-provider bootstrap verified cached artifact checksums; all three
upstream immutable download URLs returned HTTP 200. This was not a second full
fresh dependency-install replay.
