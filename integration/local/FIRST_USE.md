# Use Kolibre now

Web interface: **https://books.drkhn.site/kolibre-stage/**

Sign in as `founder` with the native Kolibre password, privately available in
`runtime/staging-credentials.json` → `native_passwords` → `founder` on this
workstation. Sister uses `native_passwords.sister`. These differ from Keycloak
passwords used to connect ChatGPT. Do not paste passwords into chats/issues.
Use the existing application user management to choose personal credentials.

Start with the five synthetic books or upload COPIES of your own EPUBs through
the normal import screen. Choose shared or private visibility intentionally.
Original BookOrbit libraries have not been migrated or modified. Automatic
knowledge indexing runs every30seconds; model indexing takes additional time
for larger books. MCP returns pending_books for incomplete/unsupported items.

ChatGPT endpoint remains https://books.drkhn.site/kolibre-mcp-stage/mcp.
Refresh connector metadata/start a new conversation if needed. Five restricted
read-only tools, including kolibre_semantic_search, are enabled.

Try: "Use Kolibre semantic search to explain how neurons communicate, citing
book titles and passage locations." Then ask about your uploaded book's topic.
The model searches your permitted books and your own annotations. Exact EPUB
reader deep links are not implemented; citations contain section/word offsets.
Semantic retrieval currently indexes EPUBs; other existing Kolibre book formats
remain usable in the catalog but aren't newly supported by semantic indexing.

## Deployed architecture

Real Calibre metadata.db catalogs remain authoritative. Kolibre authorizes API
requests; CalibreMCP forwards each caller's token. Vectors now use CalibreMCP's
LanceVectorStore and embedded LanceDB0.41.0, not Python scans of SQLite vectors.
SQLite remains only for source tracking/lexical search (and normal app data).
Atomic per-book Lance updates, prefiltering valid source generations and final
live authorization/source checks preserve private-library boundaries.
Existing vector store was extended to accept precomputed embeddings and atomic
per-book replacements. No unrestricted legacy MCP tools are exposed.
CPU FastEmbed and hybrid retrieval/citations/own annotations remain supported.

Backend d03ec0416fa6cd93ea8f2dda09f45e263c1e712f;
CalibreMCP60d0b39997a921b4fcc91cade97037e64edb3da2;
web a5a9b43eec5b9c92796cdbf69ac04896267218d8.
Backend imports the exact bridge source via its private venv .pth, managed by
upgrade_sources.py. A restricted retrieval log lives in the Kolibre data dir.
User libraries/authentication/reading state were preserved, indexes rebuilt.

UI build: VITE_BACKEND_URL=/kolibre-api-stage npm run build -- --base=/kolibre-stage/.
Caddy serves /srv/kolibre-web/current; managed routes preserve BookOrbit's /
and existing API/discovery. API upload limit300MB. No new DNS/firewall change.
This shares the existing HTTPS origin; it is not separate browser-origin isolation.
Web login uses existing native authentication; ChatGPT continues using OIDC.

## Focused verification, not a new campaign

Actual local LanceDB integration1passed23.02s (embeddings, MCP, privacy, moves,
changed/deleted sources/reindex). Two index recovery tests pass. Lance storage
regression1passed1.04s checks atomic updates, prefilter and preservation of other
books. Existing bridge tests13passed2.72s. Frontend TypeScript/Vite build passes.
Public HTTPS actual MCP native+Keycloak code/S256: concurrent two users, own
notes, private denials, revoke/reconnect/restore PASS after Lance migration.
Frontend/assets/SPA-deep-route/reader HTML return200; existing BookOrbit200.
Browser automation could not open a tab due tool timeoutMs error, so interactive
web login/reading is not claimed observed. No KOReader synchronization project
or broad suite/database benchmark was started. Legacy suite limitations remain.

## Operations/recovery

systemd Kolibre/bridge/indexer/IdP remain persistent and bounded. Original
BookOrbit/Siyuan remain running. Previous source releases and baseline tags are
retained. Existing encrypted backup timer protects original books, application
and identity state; derived Lance indexes are rebuildable. Backup stops/restores
indexer too. Web bundles are reproducible artifacts; web-revision.json records
hashes and source. Full replacement-host recovery remains unproven, not a reason
to delay first use with copies. Do not replace irreplaceable originals yet.

If a problem appears, report the operation, book format/approximate size,
shared/private scope and visible error. No credentials needed. Worker failures:
`ssh oracle 'sudo journalctl -u kolibre-knowledge-stage -n 40 --no-pager'`.
