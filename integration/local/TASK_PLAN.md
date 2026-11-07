# ChatGPT interoperability milestone

Authorized scope: local repositories and Oracle staging; preserve BookOrbit and
Siyuan; commit/push development and draft PR branches; no PR merges.

- [x] Recover actual sources/services and identify stale documentation.
- [x] Diagnose expiry exit 2: unsupported CLI phase, not an OAuth failure.
- [x] Execute full CalibreMCP suite and compare with original bridge baseline.
      Both have the same 42 failures / 23 errors; no new failure IDs.
- [x] Reproduce and fix missing OIDC `books:read` enforcement; 79 backend tests pass.
- [x] Add read-only tool hints and per-tool OAuth metadata; 13 bridge tests pass.
- [x] Add regression coverage for the expiry CLI route; local OIDC/CLI checks pass.
- [x] Deploy exact tested sources and persist a verifiable revision manifest.
- [x] Verify predefined ChatGPT OAuth client with real PKCE, issuer callbacks,
      refresh rotation, expiry and two-user MCP privacy/reconnection.
- [x] Resolve advertised offline scope, bound offline sessions, preserve MCP URL
      audience during offline refresh; real basic/offline privacy/revocation pass.
- [x] Update the stacked draft PRs without merging or rewriting existing history.
- [x] Reconcile documentation and final environment/checkpoint evidence.
- [ ] Account-side ChatGPT connection and model tool selection: requires the
      user's authenticated ChatGPT interface; not implied by protocol tests.

This file is updated at milestone completion; raw evidence is under
`evidence/deployment/`, which is deliberately ignored by Git.
