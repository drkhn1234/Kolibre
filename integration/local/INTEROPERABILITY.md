# Independent MCP client interoperability — 2026-11-07

For the later deployed milestone, use [VPS_RESULTS.md](VPS_RESULTS.md) and
[CHATGPT.md](CHATGPT.md). Actual Inspector over public HTTPS, persistent Keycloak,
predefined ChatGPT OAuth client, genuine native/OIDC expiry, refresh rotation,
replay rejection and two-user privacy are now verified. The current full local
suite has 21 passes. ChatGPT account-side behavior is still untested.


The shipped **MCP Inspector 2.14.0 `mcpdo` terminal client** connected to the restricted Kolibre FastMCP HTTP server. The final combined run completed **18 passed, 1 existing warning in 312.40 seconds**, including three independent-client scenarios and all 15 prior live scenarios. The earlier focused run was **3 passed in 195.44 seconds**. This adds an independently packaged JavaScript client to the previously verified Python FastMCP SDK tests. Oracle and production services were not accessed during that historical local milestone.

## Client and reproducible commands

Dependencies are locked in `clients/inspector/package-lock.json`: Inspector 2.14.0 and a private Node 22.23.4 runtime. Application HEADs remain Kolibre `d4155e553b442d7dcb321f0a491f9066b9a51968` and CalibreMCP `12ecf368644609156d4f16ba9e43663284b79153`. No application fix was required for the client tests.

```sh
# Existing lab with its Python/provider environments already installed:
npm ci --prefix clients/inspector --no-audit --no-fund
./client-test.sh

# Entire lab, including the independent client scenarios:
.venv/bin/python -m pytest tests -v --tb=short \
  --junitxml=evidence/client-milestone-junit.xml
```

For a new lab follow README.md / `./setup.sh`, which now installs both the provider and Inspector locks. Do not run setup solely to inspect state; it can recreate the Python environment. The host npm used Node 22.23.2 during installation and emitted an engine warning. All actual Inspector commands were explicitly run with the locked supported **22.23.4** binary; the system Node installation was unchanged. A subsequent `npm ci` succeeded in 11 seconds (`evidence/inspector-install.log`).

`tests/test_inspector_client.py` invokes the installed executable rather than reimplementing MCP. Representative executable commands, with generated private configuration paths omitted:

```text
mcpdo --format json --config <private-profile> connect founder
mcpdo --format json --config <private-profile> connections/show founder
mcpdo --format json --config <private-profile> --connection founder tools/list
mcpdo --format json --config <private-profile> --connection founder tools/call kolibre_list_libraries {}
mcpdo --format json --config <private-profile> --connection sister tools/call kolibre_list_books {"library":"shared"}
mcpdo --format json --config <private-profile> disconnect sister
mcpdo --format json --config <private-profile> connect sister
```

Inspector documents `mcpdo` as an experimental connection CLI with a persistent daemon and named sessions. Its “legacy” protocol-era label means the classic initialize handshake, not a failed or deprecated connection. [Official client documentation](https://github.com/modelcontextprotocol/inspector/blob/main/clients/mcpdo/README.md).

## Passed against running components

| Check | Observed result |
|---|---|
| MCP initialize | Server `Kolibre (authenticated read-only bridge)`, FastMCP `3.4.11`; negotiated **2025-11-25**; `transport: live`; tool capability present |
| Tool discovery | Exactly `kolibre_list_libraries`, `kolibre_list_books`, `kolibre_search_fulltext`, `kolibre_my_annotations`; no legacy/filesystem/vector tools |
| Native authentication | Genuine Kolibre `/token` credentials supplied in mode-0600 per-profile files, never command-line arguments |
| OAuth/OIDC | Inspector starts with no bearer, discovers the resource/issuer, registers, generates S256 PKCE/state, listens on its own loopback callback, exchanges code and stores its token |
| Two independent sessions | Founder and sister connected to the same bridge simultaneously; threaded overlapping calls use distinct authenticated Inspector profiles |
| Shared/own private books and FTS | Both readers retrieve shared and their own private content using actual `tools/call` |
| Guessed foreign private IDs | Each user's catalog/search/annotation calls return `isError: true`, Inspector exit 5 and `Library not found`; no foreign title/note appears |
| Own annotations | Each response contains only that reader's synthetic notes; the other reader's note is absent |
| Live revocation | Existing sister session immediately loses shared books/search/notes and the shared library disappears from its current list; founder retains shared access |
| Revoked reconnect | Disconnect/reconnect does not restore shared access; sister still reads her private library; explicitly restoring the grant takes effect on the next call |
| Native token expiry | Genuine short-TTL native login works before expiry, fails in the same connection after expiry, and stale reconnect fails; fresh `/token` login reconnects successfully |
| OIDC token expiry | Actual provider-issued access tokens expire in both existing Inspector connections; calls fail; clearing local auth and completing new independent code flows restores each user's own access |
| Persisted OAuth reconnect | Before expiry, disconnect/reconnect succeeds from Inspector's own stored credentials without a harness-supplied bearer or repeated browser authorization |
| Existing OIDC regressions | `.venv/bin/python -m pytest tests/test_live_oidc.py -v --tb=short ...`: **3 passed**, 1 existing memory-storage warning, 36.85 seconds |
| Harness/static checks | Ruff lint/format for the new test file, shell syntax, provider JavaScript syntax and Git whitespace checks pass |

The final 18-test combined run validates the stricter denial error-text assertions and sanitized trace archiving as well as every original live test. Its one warning concerns the original Python OAuth fixture's memory-only client store; Inspector uses its own encrypted disposable file store. The final traces contain 94 commands, 36 successful tool calls, 20 expected library denials, three expired-auth call failures and four completed OAuth callbacks. All five disposable profile daemons stopped. See `evidence/inspector-summary.json`.

## What is real, and what is automated

All backend, bridge, IdP, databases, permissions, tokens and MCP transports are actual running implementations. The OAuth profile is not seeded with the linking token: linking first uses a separate genuine code-flow token, then Inspector independently performs its own DCR and code flow. Separate cookie jars authenticate the synthetic provider users and consent. The resulting redirect is sent over HTTP to **Inspector's real callback listener**, allowing the client to validate state and exchange the code. There are no custom OAuth callback/token-storage overrides in Inspector.

The human login interaction is driven by HTTP against the existing disposable provider's JSON interaction API. No desktop chat application's GUI, browser rendering, or language-model tool-selection behavior is exercised. This is verified terminal MCP client interoperability, not a blanket claim for Claude Desktop, ChatGPT, Cursor, VS Code or every OAuth client.

Each profile has an isolated daemon/socket/catalog/OAuth state/client settings file and encrypted scratch secret file. Both the storage path and higher-priority OAuth path override are explicit. Generated encryption secrets remain in child-process environment only. Node's extra CA trust is scoped to these processes, and Python's trust remains an explicit test SSL context. The normal personal Inspector catalog/keychain and system trust are untouched. Disposable Inspector profiles are removed after their daemons stop; sanitized traces are retained, not raw auth URLs/codes/JWTs. Synthetic app DBs and test TLS/signing keys remain under pytest temporary directories as in the earlier lab.

## Diagnosed setup failures and fixes

1. Initial harness supplied `MCP_CATALOG_PATH` together with `--config`. Inspector rejects that pair as mutually exclusive. Removed the catalog environment override while retaining an explicit private `--config` on every command. This was a test-launch mistake, before reaching Kolibre, not an application authorization defect. Evidence: `evidence/inspector-harness-config-before.log`.
2. The first OAuth expiry scenario issued 45-second JWTs. Inspector's client-side usability check applies a 60-second expiry margin, so its helper completed OAuth/MCP while the daemon still classified the new token as expired. The test now uses genuine 120-second provider tokens, leaves time for useful calls, then waits past actual expiry. It does not change client security checks or disable verification. The provider's existing default stays 300 seconds; an optional bounded `LAB_ACCESS_TOKEN_TTL` changes only the disposable test provider. Evidence: `evidence/inspector-short-oidc-before.log` and the final passing scenarios.

No Kolibre or CalibreMCP application defect was confirmed during this milestone; both application repositories remain untouched. New regression coverage and configuration fixes are in the top-level integration lab, uncommitted and unpushed. There are no new application-fix commit hashes.

## Evidence and remaining limits

- Focused run: `evidence/inspector.log`, `evidence/inspector-junit.xml`.
- Combined final run: `evidence/client-milestone-full.log`, `evidence/client-milestone-junit.xml`.
- Sanitized per-command transcripts from the final run: `evidence/inspector/test_inspector_*-{founder,sister}.json`; each records connect/show/discovery/tool results, exit codes and redacted errors. Matching copies are in the fixture directories.
- OIDC regression: `evidence/oidc-regression.log`, `evidence/oidc-regression-junit.xml`.
- Static checks: `evidence/client-static-checks.log`; final Git/runtime snapshots: `evidence/client-final-{git,environment}.json`.
- The raw evidence directories remain ignored local artifacts. The current source/report changes have not been copied into the previously published Kolibre `integration/local/` snapshot.

Refresh-token renewal was deliberately disabled in the expiry client configuration so expiry could not be hidden by renewal. Refresh/rotation, external IdPs, production DCR policies, GUI clients, proxy/public HTTPS behavior, ARM artifacts, sustained load and formal security review remain **not tested**. Only native short-TTL fixture issuance was changed; the application still has its existing seven-day native default. Permission-scoped semantic/vector RAG remains unimplemented. The unrelated legacy CalibreMCP failures documented in RESULTS.md were not rerun or fixed in this milestone.

The next concrete preparation is to test the selected persistent staging IdP and HTTPS proxy locally, then review [ORACLE_STAGING_PLAN.md](ORACLE_STAGING_PLAN.md). VPS access/deployment needs separate explicit user authorization.
