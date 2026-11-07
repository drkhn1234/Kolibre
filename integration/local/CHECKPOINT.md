> Regular KOReader profile now provisioned: device4 **KOReader Flatpak — drkhn**,
> owner founder, plugin in ~/.var/app/rocks.koreader.KOReader/config/koreader/plugins/kolibre.koplugin,
> dedicated books ~/Documents/Kolibre. Existing active settings contents left intact;
> gconfig activates on next KOReader launch. User should exit/reopen, then Kolibre →
> Sync everything and accept queued disposable book. Normal-profile first sync is
> not yet observed. Private setup backup/receipt: runtime/koreader-normal-setup/.
> No synthetic sidecar patches installed in normal profile. See KOREADER_RESULTS.md.

> KOReader follow-up: actual installed Flatpak core sync passed in an isolated profile: EPUB download/load, synthetic highlight/note upload,37% push,62% web-to-KOReader pull and sister-note isolation. See KOREADER_RESULTS.md. Normal KOReader profile unchanged/unconfigured; no app redeployment. New dedicated test device3/shared book4 remain.

> Latest deployment: use FIRST_USE.md. Vectors migrated to CalibreMCP's LanceDB
> store; web interface live https://books.drkhn.site/kolibre-stage/ . Backend
> d03ec0416fa6cd93ea8f2dda09f45e263c1e712f, bridge
> 60d0b39997a921b4fcc91cade97037e64edb3da2, web
> a5a9b43eec5b9c92796cdbf69ac04896267218d8. Original services/user state retained.
> Scoped local/public tests pass; no KOReader sync or new broad campaign.
> User's next action is ordinary first use, not another acceptance checklist.
> Earlier SQLite-vector sections below are historical, superseded by FIRST_USE.md.

# Kolibre–CalibreMCP checkpoint — 2026-11-07, knowledge retrieval

## 1. Current objective and status

Initial permission-aware hybrid retrieval vertical slice is implemented, tested
and deployed to Oracle staging. Next functional acceptance is actual ChatGPT
use of the optional fifth tool. Read KNOWLEDGE.md first for decisions, commands,
limits and rollback; CHATGPT_ACCEPTANCE.md records USER-EXECUTED successful
four-tool account-side tests separately from automated MCP tests.
No PR merged, paid resource bought or production library imported.

## 2. Repositories and Git state

Workspace /home/drkhn/Projects/kolibre-integration, branch dev/local-integration-lab,
no remote. Implementation/harness commit b1604941b540ec1edd9025f98164d29aa6726ece;
subsequent checkpoint publication commits change documentation only. Resolve
final HEADs with git log -1 / git status; commits cannot contain their own hash.

Kolibre repos/Kolibre, dev/local-multiuser-integration:
application/deployed bbb24204e6ebb2b104cac3da5c9075ba65831dad; initial docs
publication 376854a (subsequent docs commits do not change backend).
CalibreMCP repos/calibremcp, dev/local-multiuser-integration:
application/deployed/pushed 6877e76160dafc25b236ba2200855a3f7576442c.
Both development branches pushed. Root tracked files mirrored in Kolibre
integration/local with source lab revision in SNAPSHOT.md; secrets/raw logs excluded.

Remote tags staging-chatgpt-validated-20261107 preserve Kolibre 468af5dd…
(application c06a7cea…) and bridge 072c0654… before retrieval changes.
Draft PR branches remain at their previous milestone: Kolibre #1 foundation
1e12ea76…, #2 OIDC 83f43e69…, Calibre #1 072c0654…. New retrieval stays on
development branches; it was not folded into or merged through those drafts.
Auxiliary worktrees and baseline archives remain under ignored runtime/.

## 3. Running environment and configuration

ssh oracle, existing authenticated ubuntu/Tailscale connection, sudo available.
Ubuntu24.04 ARM64, 2CPU/~8GiB RAM, ample disk; no new infrastructure.
All observed active: kolibre-stage, kolibre-mcp-stage, kolibre-knowledge-stage,
kolibre-stage-idp, caddy, bookorbit-mcp. Existing BookOrbit containers healthy;
Siyuan containers running; loopback health 3000=200,6806/6807=401 as expected.

Public MCP https://books.drkhn.site/kolibre-mcp-stage/mcp.
API /kolibre-api-stage →127.0.0.1:18081; MCP→18082; Keycloak→18083.
Issuer https://books.drkhn.site/kolibre-auth-stage/realms/kolibre-stage.
Persistent data /var/lib/kolibre-stage; root config /etc/kolibre-stage.
Both current release symlinks use full application hashes above.
/etc/kolibre-stage/revisions.json verified all485/978 source file hashes.
knowledge-revision.json records the new helper/backup hashes separately;
original integration-revision.json records previous provider helper revision.

New worker same restricted Kolibre service user/data, 50% CPU/768MiB/Nice10,
enabled, per-library knowledge.sqlite3 + model cache in DATA_DIR. Both retrieval
flags enabled; default four-tool configuration remains supported. HF_HOME in
staging data; implicit HF token lookup disabled without weakening ProtectHome.
Native TTL15min, OIDC300s, rotated refresh/offline policy unchanged. Predefined
ChatGPT client, exact callback and guarded anonymous DCR unchanged.

Five synthetic EPUBs: shared original plus Signals between nerve cells and Heat
and disorder; one original private book per founder/sister. Original reading
state/notes retained. Sister shared edit/upload grant restored after every probe.
No migration. Unrelated services/data unchanged.

## 4. Completed and verified work

Actual ChatGPT four-tool authentication/privacy/expiry/revocation/reconnect/restore:
user supplied screenshots/fresh tool results; see CHATGPT_ACCEPTANCE.md. Precise
automatic-refresh vs prompted-reauthentication behavior remains unspecified.

New tests: backend81OK; bridge/logging13pass; real local CPU/MCP retrieval1pass
(~9.5s), default four-tool regression1pass. Coverage includes concurrent users,
foreign denial, own notes, revocation/reconnection, changed/deleted EPUBs, actual
shared→private move, reindex and authenticated source downloads. Interrupted
index replacement and model change covered in backend tests. Bridge Ruff clean.

Actual public HTTPS FastMCP client with native AND genuine Keycloak code/S256:
five tools, both identities, concurrent retrieval, own annotations, foreign
denial, live revocation/reconnection/restoration PASS. Public semantic-only top1
conceptual queries select both newly ingested relevant synthetic books, pending=0.
Worker~257MiB/API~236MiB peak, small-corpus public queries0.3–1.8s.
Raw evidence evidence/deployment/knowledge-*.log; tracked compact evidence
verification/knowledge-2026-11-07/. KNOWLEDGE.md contains exact interpretation.

Fresh baseline encrypted backup20261107T162840Z.tar.gz.age decrypts locally;
SQLite integrity ok, two users/three baseline EPUBs/nonempty IdP dump/config.
Not a booted full-host/PostgreSQL restore. Earlier reboot evidence remains valid.
Backup script now stops/restores worker and includes its unit. No new reboot.

Earlier server tests/legacy results remain in VPS_RESULTS.md: actual full
CalibreMCP285pass/42fail/23errors/10skip, same unsuccessful IDs as baseline.
Not rerun for this milestone; never claim full suite or all CI green.

## 5. Work currently in progress

No implementation, indexing migration or deployment command intentionally left
running. Periodic indexing service is expected. Await actual ChatGPT fifth-tool
selection/citation/quality acceptance. Read-only source verification is complete.

Ignored runtime material: mode0600 staging-credentials.json, chatgpt-client.json,
staging-backup-identity.txt; restricted baseline-restore contains decrypted root
secrets/database and must NEVER be committed/copied into public artifacts.
runtime/baseline.tar.gz.age encrypted snapshot; embedding-models cache; .venv;
Inspector node_modules; vps-validation/synthetic-state.json and completed
revocation record; raw evidence logs/JUnit; auxiliary worktrees/archive fixtures.
No secrets in tracked files; staged JWT/private-key pattern scan clean.

## 6. Architectural decisions and rationale

Kolibre owns retrieval/ACLs; bridge forwards caller token. Per-library SQLite
FTS5+vectors with exact cosine + reciprocal-rank fusion avoids another database
service and unauthorized global top-k starvation. Current ACLs constrain sources
before retrieval and are checked again before returning text. No result cache.
Atomic derived indexes never modify books; stale source/model fingerprints fail
closed; poll worker repairs. Own annotations embedded on request, never shared.
CPU FastEmbed default, configurable HTTPS hosted provider/rebuild epoch; hosted
path not live-tested. Citations use real EPUB section/normalized word offset,
not invented CFIs. ChatGPT handles synthesis/external public research; no crawler,
knowledge graph or unrestricted legacy RAG. Full rationale/limits: KNOWLEDGE.md.

## 7. Known defects, blockers, and security risks

No new confirmed cross-user leak. Known legacy suite/CI failures persist.
Retrieval is a small-corpus initial implementation: exact scans/hashes per query,
English-focused model, simple ranking, no reranker, unsupported non-EPUB formats,
no index disk quota/job dashboard, per-request annotation embedding. Large books
may hit worker bounds; originals remain safe. No calibrated quality benchmark.
Precise reader deep links/annotation-to-passage alignment deferred. Model weights
changing under same ID require explicit rebuild epoch. Hosted provider requires
operator-configured secret and knowingly sends source text externally.

Actual fifth-tool ChatGPT usage, hosted provider, multilingual/real-corpus quality,
full PostgreSQL/host restore/offsite replication and full security audit untested.
Prior risks remain: shared browser origin with BookOrbit, experimental Keycloak
resource-indicators, no immediate provider logout introspection, fine-grained
non-MCP write-scope design needs review. Not production readiness.

## 8. Exact next action and acceptance criteria

Refresh Kolibre staging connector tool metadata in ChatGPT; start a new chat.
Expect five tools including kolibre_semantic_search. Ask for semantic retrieval
of neural communication and entropy/direction-of-processes across authorized
books, citing returned sections/offsets. Verify passage support, identity and
cross-private denial for fifth tool. Record actual outputs as user evidence.
Server-side native/OIDC tool lifecycle tests already pass; do not repeat old
8-minute suites merely to recover state. Improve observed weaknesses next.
No PR merge or irreplaceable-data import authorized by this checkpoint.

## 9. Recovery instructions for a fresh agent session

Read KNOWLEDGE.md, CHATGPT_ACCEPTANCE.md, this file, then inspect git status/log
in all three repositories and ssh oracle service/current symlinks. Avoid printing
secret configs. Development branches are source of retrieval; draft feature
branches intentionally preserve previous review scope. setup.sh reconstructs
code from pinned original anchors + patches including new0007/0005; tests use
runtime model cache, creating it if missing and downloading the CPU model.

Stop/disable worker and set both knowledge flags0 to remove the fifth tool.
For source rollback restore previous c06a7ce…/072c065… symlinks and restart ONLY
Kolibre/bridge. No app-schema migration exists; preserve current data/identity.
Derived indexes can be rebuilt. Do not reseed existing identities or initialize
host again. Backup/recovery paths and limits are in KNOWLEDGE.md/DEPLOYMENT.md.
