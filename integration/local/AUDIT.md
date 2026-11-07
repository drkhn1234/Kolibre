# Completion audit

This original local audit is historical. The later authorized Oracle/ChatGPT
protocol audit is [VPS_RESULTS.md](VPS_RESULTS.md), with current state and recovery
in [CHECKPOINT.md](CHECKPOINT.md). Its deployed/refresh results supersede earlier
not-tested labels below; actual ChatGPT UI, semantic RAG and production security
review still require separate acceptance.


Each requirement is evaluated against actual execution, with limits stated explicitly. Raw test results and commands are linked from RESULTS.md and COMMANDS.md.

| Specification | Evidence |
|---|---|
| Dedicated forks, specified branches and OIDC includes multi-user foundation | Pinned baseline commits, branch ancestry check, original/replay Git trees identical |
| Local isolation; disposable DBs/books; no production data or deployment | Test fixture subprocess environment, temporary directories, loopback binds, synthetic EPUB generator; legacy suite additionally runs in Bubblewrap |
| Founder admin, sister ordinary; shared + two separately owned private libraries | Real startup/login and account/library HTTP creation; `populated` fixture; two-user direct HTTP/MCP/OPDS tests; owner-only private moves for both accounts |
| Only four authorized tools; no legacy/filesystem/vector tools | Exact tool-name sets from actual MCP `list_tools`; separate bridge factory and entry point inspected |
| Suitable OIDC provider, real capabilities and TLS | Pinned node-oidc-provider, actual discovery/DCR/code+S256 PKCE, wrong-verifier rejection, signed JWT access tokens; default trust rejection and explicit CA success |
| Both native and OIDC authenticated identities | Genuine `/token` issuance; real provider login and token exchange; `/api/users/me` mappings; simultaneous MCP clients |
| Linking is verified and account scoped | Rejection before link, native/password-confirmed link, 409 on cross-account binding, 401 wrong password; unit tests also verify OIDC alone cannot link |
| Invalid signatures, expired tokens, incorrect issuer/audience, unlinked, missing tokens | Live HTTP and MCP negative matrix; absent mandatory JWT claims also tested |
| Token expiry during sessions | Real native login short-TTL test and signed OIDC short-TTL test each accept an initial call then reject a later call with HTTP 401 |
| Library revocation and stale state | Existing native/OIDC MCP sessions reject subsequent calls after live grant removal; backend restart does not restore revoked access; moved book is absent from previously indexed shared FTS |
| Shared/private access table for founder and sister | Concurrent native/OIDC MCP catalog and full-text tests, guessed foreign slugs, own-only annotations; direct HTTP foreign annotation update denial |
| Multiple users and sessions, no selection/token/search leakage | Six native sessions and four OIDC sessions; separate OAuth clients; simultaneous different-private-library calls and own-note checks |
| Direct Kolibre HTTP and separate OPDS credentials | Native content test covers both owners, both private catalogs and foreign-library rejection; guessed annotation IDs cannot be edited |
| Upload shared and private, actual ownership/placement | HTTP ingest/import (private cannot be redirected to shared), real metadata.db and physical EPUB checks |
| Make shared book private; owner progress/notes follow; foreign notes/devices do not | Parameterized founder/sister move test uses actual reading-position, annotation, device registration/queue and move APIs; HTTP reads plus SQLite association verification |
| Interrupted move, journal recovery, only valid copy retained | Process exits at durable ready/source-deleted checkpoints; ordinary restart and owner-only recovery; idempotent retries; missing/truncated/same-size corruption regressions; incomplete review never becomes completed on retry |
| Existing backend tests, privacy/OIDC and compilation | 76 backend tests and compileall pass in original and fresh replay |
| React build | npm ci + TypeScript/Vite build pass; existing Kolibre CI also green |
| Restricted bridge and FastMCP checks | 12 bridge tests plus live FastMCP HTTP/OAuth sessions; full lint/format pass |
| Wider repository suite and existing CI investigated | Full collection attempted; additional fixture-backed broader selection executed on current and original baseline; same failure IDs and exact CI collection failures documented |
| Launch mechanism, environment examples, synthetic setup, tests, README, evidence and commit hashes | setup.sh, test.sh, environment.example, lockfiles, tests/, patches/, README.md, COMMANDS.md, RESULTS.md; clean bootstrap and test replay |
| No unit-only production-readiness claim; future OAuth clients/RAG/security/Oracle needs identified | Explicit Not tested/future work in RESULTS.md; no Oracle access or deployment |

The wider legacy suite's pre-existing failures are reported as failures. GUI OAuth clients, semantic RAG and eventual Oracle staging are explicitly outside the verified local outcome and are not represented as passing.
