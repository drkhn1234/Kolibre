> Superseded storage decision: retrieval now reuses CalibreMCP LanceVectorStore/LanceDB. Read [FIRST_USE.md](FIRST_USE.md) for current deployed revisions, URLs and focused results. The SQLite-vector discussion below describes the previous iteration.

# Knowledge retrieval — initial vertical slice, 2026-11-07

## Decision and trade-offs

Kolibre owns authorized passage retrieval; CalibreMCP forwards the caller's
verified bearer. The legacy unrestricted vector/RAG tools are not reused.
Existing Calibre catalog, library ACLs, own-user Highlight records, authenticated
downloads and SQLite infrastructure are reused. Existing whole-book fulltext.db
is left intact: it loses EPUB section boundaries and cannot supply passage
citations. New EPUB extraction follows the OPF spine.

Storage is a per-library `knowledge.sqlite3`: transactional passage rows, SQLite
FTS5 lexical ranking and normalized embeddings, with exact cosine scoring in
Python. This deliberately avoids LanceDB/ANN/server dependencies and global
nearest-neighbor starvation by private documents. For a small collection it is
simpler to operate. It is O(authorized passages), not a large-corpus architecture;
measure real-library latency before adopting an ANN engine. Storage/query
functions are separated from Embeddings; no generic plugin framework was added.

Hybrid ranking is reciprocal-rank fusion (k=60), supporting semantic-only and
lexical-only modes. Lexical BM25 ranks are currently library-local, merged into
one ranked list; this is a practical initial heuristic, not calibrated relevance.
No reranker or guaranteed relevance threshold. Low-signal queries may return
weak matches; the client should distinguish supplied evidence from inference.

Default CPU provider FastEmbed 0.9.1, BAAI/bge-small-en-v1.5, one inference thread,
384 dimensions. An explicit `openai` provider supports a configured HTTPS
OpenAI-compatible embedding endpoint. It is not tied to OpenAI accounts and has
not been live-tested with a paid provider. Hosted inference sends passage and
own-annotation text to that provider; enable deliberately, never silently.
No paid external compute was used. The initial model is English-focused;
multilingual retrieval quality has not been evaluated.

Citations carry library/book/title/author, content SHA256, EPUB member path,
normalized section word offset, passage text and authenticated API-relative
source_url. Word offsets are not EPUB CFIs. Source links download the book;
precise reader deep-link navigation is deferred. Annotations preserve page/CFI
where present; no fabricated passage alignment. No answer-generation service:
ChatGPT synthesizes and can research public references independently. Finding
related books uses repeated hybrid queries now; no knowledge graph or external
bibliographic crawler in this milestone.

## Safety and indexing

Current Kolibre permissions constrain libraries BEFORE text/vector candidate
retrieval; a final live permission/source check runs before response release.
Book IDs are always library-qualified. No cross-user result cache or global
selection. Own annotations alone are queried/embedded per request (not copied
into shared indexes). This avoids a second annotation synchronization pipeline;
large annotation collections may need a per-user incremental index later.

A separate, single-instance worker scans registered libraries every 30 seconds.
SHA256 + provider/model/revision/chunker identity skips unchanged EPUBs.
Embedding batches of 32; 200-word windows, 40-word overlap, section-boundary
preservation. Each book's new rows commit atomically; interruption keeps old rows,
which source/model validation suppresses if stale. Removed files/books are
suppressed immediately and pruned on the next scan. Moves cannot leave searchable
old shared passages once their source is gone. Original books/metadata are never
written by the indexer. Other formats are not indexed yet. EPUBs exceeding
100 MB uncompressed are rejected with worker logs; malformed sources retry.
`pending_books` reports missing/current-model-unindexed books (including currently
unsupported formats); partial results are explicitly distinguishable from ready.
Worker failures appear in journalctl. There is no job dashboard or durable retry
queue; the repeated scan recovers after restart. No explicit index disk quota yet.
Large books may hit worker memory limits safely, requiring smaller extraction
batches in a later iteration. Source hashing on retrieval favors correctness over
large-corpus speed; no benchmark extrapolation from five synthetic books.

## Configuration and local use

Baseline API is unchanged unless `KOLIBRE_KNOWLEDGE_ENABLED=1`; MCP registers the
fifth tool ONLY with `KOLIBRE_MCP_KNOWLEDGE_ENABLED=1`. Default four-tool tests pass.

Install backend requirements plus `backend/requirements-knowledge.txt`.
Run `python -m backend.app.services.knowledge` with the same DATA_DIR,
DATABASE_URL and library permissions as the backend; `--once` runs one scan.
The worker must run under a dedicated bounded service, not inside request jobs.

Optional hosted settings (values are operator secrets, not examples to commit):
KOLIBRE_EMBED_PROVIDER=openai; KOLIBRE_EMBED_URL is the full HTTPS embeddings URL;
KOLIBRE_EMBED_MODEL is its model ID; KOLIBRE_EMBED_KEY is the provider key.
KOLIBRE_EMBED_REVISION (default 1) is an explicit rebuild epoch; bump when a
provider changes weights/configuration under an unchanged model name. Changing
provider/model/endpoint/revision invalidates old embeddings. Deploy identical
settings to API and worker and restart both. Rebuild indexes, not original books.
Local model artifacts live under DATA_DIR/embedding-models. Set HF_HOME inside
DATA_DIR for isolated service accounts; implicit Hugging Face token lookup is
disabled in staging. Do not broadly disable TLS checks.

GET `/api/kolibre/knowledge/search?q=...&mode=hybrid&limit=10` accepts optional
library and include_annotations. Without library, searches accessible libraries.
MCP `kolibre_semantic_search(query, library?, limit=10, mode='hybrid',
include_annotations=True)` is read-only and uses the same OAuth books:read gate.

## Executed verification

- Backend unittest discover: **81 tests OK**, 7.384s (79 existing + 2 index tests).
- Actual local CPU embeddings + HTTP/MCP integration: **1 passed**, 9.55s:
  concurrent users, exactly five opt-in tools, private denials, own annotations,
  revocation/reconnect, changed/deleted content, real private move and reindex,
  and an authenticated citation download. Synthetic disposable libraries only.
- Default four-tool HTTP/MCP revocation test: **1 passed**, 4.34s.
- Existing bridge/logging tests: **13 passed**, 1.84s; bridge Ruff lint/format clean.
- Deployed HTTPS real FastMCP client, native AND genuine predefined Keycloak
  code/S256 flow: both users, five tools, source identities/own notes,
  foreign denial, live revoke/reconnect/restore PASS. Grants restored in finally.
- Local CPU quality smoke: neural communication query scores relevant passage
  0.754 vs unrelated bread passage 0.349 (initial 0.7.4 smoke; final integration
  uses repository-locked 0.9.1, restored after checking installed dependencies).
- Existing legacy full-suite failures documented in VPS_RESULTS.md were not rerun;
  no claim that 81 backend tests make the legacy Calibre suite green.

Commands/logs: evidence/deployment/knowledge-{backend-final,local-final,
bridge,four-tool-baseline,public,deploy}.log. Raw logs are ignored; reproducible
new tests and this summary are tracked. tests/test_knowledge.py requires the
FastEmbed model cache in runtime/embedding-models (download before running, as
shown by FastEmbed's TextEmbedding cache_dir option); synthetic data is disposable.

## Deployed state and operations

Backend bbb24204e6ebb2b104cac3da5c9075ba65831dad;
bridge 6877e76160dafc25b236ba2200855a3f7576442c.
HTTPS paths, identity provider and user mappings unchanged. /etc/kolibre-stage/
revisions.json records full source hashes. The source-upgrade helper performed
an independent-venv/symlink upgrade; old release directories remain for rollback.
New kolibre-knowledge-stage.service: same restricted Kolibre user/data only,
CPUQuota=50%, MemoryMax=768M, Nice=10; enabled across reboot.
Measured worker peak ~257 MiB, warmed API ~224 MiB, public query times 0.3–1.8s
on the initial three-book corpus. No large-library/hosted/provider benchmark.

Backup script now stops/restores the new worker and includes its unit so derived
SQLite files are consistent. Full PostgreSQL/clean-host restore remains untested;
see CHATGPT_ACCEPTANCE.md for the successful baseline decrypt/content check.

Rollback: stop/disable kolibre-knowledge-stage, set the two KNOWLEDGE_ENABLED env
flags to 0, restore previous current symlinks to c06a7ce… / 072c065… and restart
ONLY Kolibre/bridge. Preserve DATA_DIR and identity state. New derived indexes
are ignored by old code and can be rebuilt; no app-schema migration occurred.
Do not restore an old database merely to roll back this feature.

Next: Refresh connector metadata in ChatGPT and use the fifth tool against the
new shared synthetic examples (Signals between nerve cells / Heat and disorder).
Actual ChatGPT selection/citation quality for the FIFTH tool is not yet observed.
The earlier four-tool user acceptance remains recorded separately.

Final public CPU-quality smoke after the automatic worker indexed the two new
shared synthetic EPUBs: "How do neurons communicate?" → Signals between nerve
cells; "Why do spontaneous processes have a preferred direction?" → Heat and
disorder. Both semantic-only top-1, annotations excluded, pending_books=0.
Raw evidence: knowledge-quality-public.log and knowledge-corpus-seed.log.
Five total synthetic books now exist (three shared, one private per reader).
Final API peak about 236 MiB; worker peak about 257 MiB. These are tiny-corpus
measurements, not a corpus-scale benchmark.
