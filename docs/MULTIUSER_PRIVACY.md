# Multi-user privacy: shared/private uploads and book relocation

**Status: draft, not production-ready.** See [the multi-user authorization audit](MULTIUSER_AUTH_AUDIT.md) for verified endpoints, regressions, remaining trust boundaries, and known gaps. This fork implements shared-by-default uploads, opt-in private
uploads, and manual shared-to-private book relocation. It does not implement
end-to-end encryption or secure multi-tenant RAG.

## Agreed behavior

- The **first non-private Calibre library** in the administrator-defined library
  order is the default shared upload destination. Each user must have
  `can_upload` (or edit/owner privileges) to import there.
- Selecting **Private upload** stages the file under the authenticated user,
  then automatically creates/uses that person's own private Calibre library.
- A private library is **never readable, writable, or shareable by another
  account**, including the founder or a system administrator in the web UI.
- Human uploads use per-user staging directories. Unowned historical/watcher
  staging remains accessible only to the founder.
- Personal highlights, vocabulary, and reading sessions must remain scoped by
  their real `user_id` even for books stored in shared Calibre libraries.
- No device-side deletion is required when a formerly shared book becomes
  private. Existing downloaded copies may remain.

## Current implementation

- `Library.is_private`, `IngestedBook.uploader_id`,
  `IngestedBook.is_private` and `LibraryPermission.can_upload` with
  idempotent startup migrations.
- Shared/private per-upload form selection in the React import interface.
- Owner-filtered ingest listing, file previews, staging covers, bulk job status,
  and pre-import authorization.
- Private-library creation during import; Calibre metadata and book contents
  are stored under a separate private Calibre `metadata.db`.
- Founder's default permission overrides do **not** bypass private-library
  ownership in `permessi.py`.
- OPDS, Calibre Desktop library transfer, and the principal KOReader catalog /
  sync paths now consult library accessibility.
- Authors/reading statistics filter visible libraries and the authenticated
  user; Calibre Desktop annotation imports include the owning user in the
  upsert lookup.
- **Make private** in the book's context menu copies an existing shared book
  into the current user's private Calibre library, then removes the shared
  copy. The server chooses the private destination and requires permission
  to edit the shared source; a user with `can_upload` alone cannot remove
  shared books.
- The private move copies all available ebook formats and Calibre metadata.
  Only the moving user's positions, sessions, highlights, reading coverage,
  device-book associations and flagged-device actions are remapped.
  Other users' reading data remains on the old shared identity; their
  downloaded ebook files are not revoked.
- Existing generic `copy-to` + `delete_source` requests cannot target a
  private library. This prevents the older all-user migration path from
  inadvertently moving another person's private data.
- **Crash recovery:** `PrivateBookMove` is a durable, owner-scoped journal
  with a unique active move key. The new Calibre copy gets a unique recovery
  token in the SAME transaction as its `books` insertion, allowing recovery
  to locate the target even if the application crashed before saving its ID.
- A private move checkpoints the target ID, copy-complete state, source
  deletion and completion. All writes in the private-copy path explicitly
  opt out of the generic delayed Calibre write retry queue (critical for
  preventing a postponed delete of the shared source).
- Failure or user-invoked recovery checks the actual Calibre DB contents:
  if the shared source exists, remove the incomplete private target; if
  the source is gone AND the copy was completed, finish only the owner's
  reading-state migration. Missing or ambiguous evidence leads to
  `needs_review` rather than destructive guessing.
- The owning account sees an interrupted-move banner in the Library view,
  with an explicit Recover action. `GET /library-transfer/private-moves`
  and `POST /library-transfer/private-moves/{id}/recover` filter by the
  **authenticated owner**, with no founder override. Recovery API responses
  do not include filesystem paths, recovery tokens or book titles.
- Private upload/move log messages avoid book titles and filesystem paths,
  and private additions no longer trigger global automatic Wikipedia author
  scraping.
- Shared-library settings include an **Access** tab for choosing a user and
  granting upload-only permissions independently of edit/delete. Existing
  grants can be updated or revoked according to server-side authority.
- GitHub Actions compiles the Python backend, runs cross-user isolation
  and crash-recovery tests, and builds the React frontend.

## Milestone 4: cross-user authorization hardening

The audit uncovered and closed several indirect paths that bypassed ordinary
library permissions:

- A founder/admin could re-import another user's managed/private Calibre
  directory through a second zero-copy library name.
- Private libraries lost their `is_private` and `owner_id` when restored
  from admin-visible trash. Private trash now records the original owner and
  is inaccessible through the application to anyone else.
- Device fingerprint pairing and queued overwrites could point at another
  person's private library through supplied identifiers.
- Global orphan-reading-statistics pairing/discard by MD5 could relocate or
  delete other users' reading sessions. Decisions are now per-user, and
  historical global decisions are intentionally not reused.
- Annotations' widowed-note excerpts read all users' notes after choosing
  a single user's book group. The note query now filters by user too.
- Annotation repairs and vocabulary/title lookups were able to open
  unauthorized libraries. Shared-server hash mappings are no longer
  reassigned by personal annotation repair.
- Raw multi-user logs are no longer exposed through the admin HTTP API.
- Unregistered library folders, missing identity and directory traversal
  are rejected at the shared access/path boundary.
- Real two-principal HTTP integration tests use temporary Calibre SQLite
  libraries to exercise the FastAPI dependency chain and verify cross-user
  denials. More device/OPDS integration remains to be tested.

## Explicitly not completed / required before deployment

1. Audit **all** API routes, filesystem tools, reconciliation jobs and
   background workers for indirect cross-user access, including library import,
   restoration/trash, device association, global search, and maintenance.
2. **Test recovery on real multi-database crashes**, and complete the
   remaining exceptional states marked `needs_review` with a supervised
   repair workflow. The move is recoverable using journal checkpoints and
   a Calibre recovery token, but it is **not one atomic transaction** across
   the source Calibre database, destination Calibre database, Kolibre app
   database and filesystem. Never promise unconditional automatic recovery.
   In particular, a vanished source before the copy-complete checkpoint
   must be examined rather than accepted as a successful move.
3. The React library settings now provide an **Access** tab for shared libraries
   to grant upload-only access by default, edit/share/manage separately, and
   revoke grants when authorized. The backend remains the source of truth.
   **Still needed:** browser-driven permission UI tests and localization of
   the new English labels. Never grant destructive `can_edit` just to upload.
4. CalibreMCP still has process-global library state and unfiltered retrieval.
   **Do not expose it to non-admin users or point it at private collections**
   until MCP authentication, per-operation ACLs and authorized library-index
   selection are implemented and tested.
5. Review authorization for browser media URLs and avoid putting durable
   credentials into exposed URLs or logs.
6. Exercise the actual upload/import, OPDS, KOReader and Calibre Desktop
   workflows against a separate test database and throwaway libraries.
7. Keep root/VPS administrator access out of the scope of Phase 1; real
   cryptographic protection from the server operator is deferred.

## Local check commands

From `backend/`:

```sh
python -m compileall -q app tests
python -m unittest discover -s tests -p 'test_*.py' -v
```

From `frontend-react/`:

```sh
npm ci
npm run build
```

Never merge this branch as proof of complete application-level privacy
without the remaining audit and integration tests.
