# Multi-user privacy: Phase 1 development boundary

**Status: draft, not production-ready.** This fork implements the first
shared-by-default / opt-in-private book upload path. It does not implement
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
- GitHub Actions compiles the Python backend, runs isolation tests, and builds
  the React frontend.

## Explicitly not completed / required before deployment

1. Audit **all** API routes, filesystem tools, reconciliation jobs and
   background workers for indirect cross-user access, including library import,
   restoration/trash, device association, global search, and maintenance.
2. Implement **Make private** for an existing shared book, transactionally
   moving its Calibre files and carefully remapping **only the owner's**
   reading records. Other users' existing downloaded copies need not be erased.
3. Build a proper upload-only UI and ensure old permission clients understand
   `can_upload`; do not grant destructive `can_edit` just to upload.
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
python -m unittest discover -s tests -p 'test_ingest_access.py' -v
```

From `frontend-react/`:

```sh
npm ci
npm run build
```

Never merge this branch as proof of complete application-level privacy
without the remaining audit and integration tests.
