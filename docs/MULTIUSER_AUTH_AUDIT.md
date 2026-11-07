# Multi-user application authorization audit

**Status: actively audited; not a completed production security assessment.**

This checklist covers app/API privacy from other authenticated users **including
founder and administrator accounts**. It does not protect data from a VPS root
operator, database administrator with direct SQLite access, or an attacker
who controls the server runtime. End-to-end encryption is deferred.

## Policy and trust boundaries

- Physical Calibre libraries: shared by default; one private library per
  user. `Library.is_private` requires `Library.owner_id == requester.id`.
  Neither `is_admin` nor `is_founder` overrides private ownership.
- Personal highlights, sessions, vocabulary and device state are scoped by
  the authenticated user/device owner even on a shared book.
- Administrative functions may manage system configuration but must not
  read other users' private catalog data or personal notes via the app.
- All filesystem access must use **both** a registered library and a verified
  read/write permission. Raw folder names and arbitrary paths are not
  authorization; `config.library_path` now rejects traversal.
- KOReader device tokens inherit only their registered owner's permissions.
- A global cache, shared hash index or background job is not an exception
  to the same privacy boundary.

## Audited / fixed with regression coverage

| Subsystem | Verified control | Tests |
|---|---|---|
| Shared/private library visibility | Founder cannot access other users' private Calibre libraries; upload permission independent of edit | `test_ingest_access.py` |
| Staging / bulk import | Per-user staging paths and item ownership; destination authorization before write; owner-only job control | `test_ingest_access.py` |
| Zero-copy library import | Reject managed library roots, their symlink aliases and trash as import sources; unregistered `private_*` folders are not auto-registered as shared after a crash | `test_private_library_lifecycle.py` |
| Library trash / restore | Private trash ownership recorded before moving; founder cannot list, purge, or restore; restored library stays private | `test_private_library_lifecycle.py` |
| Central read/write gate | Reject missing identity and unknown/unregistered folder names | `test_private_library_lifecycle.py` |
| Calibre paths | Reject `../`, absolute locations, embedded separators and NUL | `test_library_path_validation.py` |
| KOReader and device pairing | Hash identity, flagged candidates, manual pairing, overwritten files, catalog and sync data check device owner ACL | `test_device_private_library_acl.py` |
| Orphan reading sessions | User-specific hash pairing/discard and no cross-user data migration; legacy global hashes no longer trusted | `test_user_stats_isolation.py` |
| Annotation previews | Widowed group excerpts and device-name lookup filtered to requesting owner | `test_personal_content_acl.py` |
| Annotation/vocabulary metadata | Cannot open foreign private library to look up title, suggest repair, add a word, or reassign a global BookHash during personal note repair | `test_personal_content_acl.py` |
| Entity/library maintenance | Explicit per-library operations use the same ACL as all-library operations | `test_user_stats_isolation.py` |
| Administrator application logs | Raw logs unavailable in multi-user mode; log redaction alone is insufficient | `test_user_stats_isolation.py` |
| HTTP dependency integration | Real throwaway Calibre metadata.db files, two test principals, FastAPI dependency resolution, HTTP Basic OPDS access and cross-user GET/POST | `test_two_user_http_isolation.py` |
| Private book relocation | Owner-only reading-history migration, journal, atomic recovery marker and conservative reconciliation | `test_private_book_*.py`, `test_private_move_marker.py` |

The CI workflow compiles Python, executes all `test_*.py` privacy regression
cases, and builds the React frontend. It verifies only code paths asserted
by these tests; CI success **does not imply total privacy**.

## Critical compatibility note

Previous Kolibre versions recorded `StatsHashPairing` and `StatsHashDiscard`
by MD5 **globally**. Their persisted decisions are not consulted by the
new user-scoped tables `UserStatsHashPairing` and `UserStatsHashDiscard`.
That is deliberate to prevent account A from assigning or discarding
account B's reading history. Some historical orphan sessions may need to
be paired again by their owners. A consent-aware migration is not yet built.

## Remaining before production

1. Exercise all less-common endpoint branches with real two-user HTTP
   sessions and device-token flows, including uploads, media responses,
   individual library maintenance and administrative operations.
2. Real KOReader devices/OPDS clients and external Calibre Desktop plugin:
   test two users, an owner revocation, and cross-user access attempts.
3. Restart/kill/recovery tests across **real** source and destination Calibre
   databases plus Kolibre's app database; handle `needs_review` states.
4. Audit background workers and shared caches for inadvertent exposure:
   author metadata, full-text indexing and RAG are separate concerns.
5. Review backup/restore operations and file permission isolation in the
   intended Docker/Oracle deployment.
6. Implement CalibreMCP authentication, per-operation ACLs and isolated
   private/shared RAG indexes. Do not deploy its existing process-global
   library switcher for multiple users.
7. Decide whether shared-library users with upload-only rights should also
   have a policy-approved way to make *their own* uploaded books private
   later; current Make Private requires shared-library edit permission.
8. Introduce observability that exposes system health without disclosing
   raw personal paths, book titles, or annotations.

The deployment remains unchanged and the GitHub PR must stay **Draft** until
the required remaining tests and review are complete.
