> New knowledge-retrieval milestone: see [KNOWLEDGE.md](KNOWLEDGE.md) for current sources, fifth-tool staging tests and limitations; [CHATGPT_ACCEPTANCE.md](CHATGPT_ACCEPTANCE.md) records the actual four-tool ChatGPT acceptance. Earlier results below remain historical.

# Local Kolibre–CalibreMCP integration lab

Current milestone: persistent Oracle staging and server-side ChatGPT OAuth
preparation are verified. Start with [CHECKPOINT.md](CHECKPOINT.md),
[VPS_RESULTS.md](VPS_RESULTS.md), and [CHATGPT.md](CHATGPT.md). The real ChatGPT
account connection remains the next acceptance step. Historical local results
below are retained; they are not the current deployment inventory.

This lab launches a real Kolibre backend, restricted CalibreMCP HTTP server and disposable HTTPS OIDC provider. Tests create founder/sister accounts, genuine native and OIDC access tokens, synthetic EPUBs, application SQLite databases and real Calibre-format libraries. Authorization is exercised through HTTP and MCP, without dependency overrides.

Requirements: Linux, Git, `uv`, Node 22 and npm. Docker was absent on the tested Ubuntu 26.10 machine, so local subprocesses and a Python 3.12 virtual environment provide the equivalent reproducible setup. The independent Inspector client uses its own pinned Node 22.23.4 binary, installed locally by npm; the system runtime is unchanged.

The complete current suite also tests persistent Keycloak locally. Bootstrap
downloads pinned, checksum-checked JDK/Keycloak/Caddy userspace test artifacts
on Linux x86_64 (about 400 MiB compressed); it reuses existing downloads.
`bash deployment/setup_local_keycloak.sh` installs only these optional local
test dependencies into ignored runtime storage. The H2 test instance is never
used on the VPS, which runs production-mode Keycloak with PostgreSQL.

```sh
./setup.sh
./test.sh
```

The bootstrap clones the two forks at pinned revisions, applies the focused patches in `patches/`, installs `requirements.lock`, and installs the pinned node-oidc-provider package. It leaves existing checkouts intact. A fresh-directory replay was performed; see [RESULTS.md](RESULTS.md) and [AUDIT.md](AUDIT.md).

`test.sh` writes `evidence/integration.log`. It includes the independent Inspector tests after setup installs their dependencies. Individual tests can be run with `.venv/bin/python -m pytest tests/test_live_move_recovery.py -v`, or the native/OIDC modules. Each fixture chooses loopback ports, generates random credentials, starts its components and stops them on teardown. The native launcher uses `python -m calibre_mcp.kolibre_bridge`. The OIDC launcher serves the same restricted bridge with Uvicorn TLS. No legacy tools are mounted.

`environment.example` describes the configuration without secrets. `requirements.lock` and `oidc/package-lock.json` pin dependencies. The synthetic EPUB generator, account creation, library permissions, indexing and annotation setup are in `tests/test_live_native.py`; they use the actual application endpoints.

The provider supports DCR, authorization code with required S256 PKCE, and RS256 JWT access tokens for the MCP resource audience. Each run creates a certificate and private signing key in mode-0600 temporary files. `KOLIBRE_OIDC_CA_BUNDLE` scopes backend trust to the JWKS connection; clients use explicit SSL contexts. Default TLS trust rejects the generated certificate. No system trust store is changed.

The original FastMCP OAuth client tests perform discovery, DCR, PKCE, state validation, exchange and token storage. Only user interaction is automated: separate HTTP cookie jars submit each synthetic user's provider password and consent. Those SDK tests use memory-only client caches. [Provider documentation](https://github.com/panva/node-oidc-provider/blob/main/docs/README.md).

The independent client tests use the shipped **MCP Inspector 2.14.0 `mcpdo` executable**, with persistent MCP connections, as a terminal client. Install just its locked dependencies with `npm ci --prefix clients/inspector --no-audit --no-fund`, then run:

```sh
./client-test.sh
```

This runs native and OAuth sessions for both users, the four tools and private-library denials, live revocation, reconnect, token expiry, and fresh sign-in. Inspector owns OAuth discovery/DCR/PKCE/state validation, its real loopback callback, token exchange and encrypted disposable token stores. The harness drives only synthetic provider login/consent; no bearer is injected into the OAuth profiles. All Inspector storage, daemon sockets and callback ports are per-profile scratch paths. `NODE_EXTRA_CA_CERTS` trusts only the generated CA within those client processes. No personal client settings or system trust store are changed.

Inspector considers a JWT expired within 60 seconds of its expiry. The expiry scenario therefore uses genuine provider-issued 120-second tokens, disables refresh-token requests in that test client, and waits past actual expiration. The provider's normal test default remains 300 seconds. See [INTEROPERABILITY.md](INTEROPERABILITY.md) for executed results and client limitations; desktop chat hosts and browser UI are separate untested clients.

Recovery tests crash a backend process immediately after a durable journal checkpoint, confirm its exit, then restart normally and call the owner-authenticated recovery endpoint. They also damage disposable source files to verify that recovery preserves the valid target. A test-only journal timestamp adjustment avoids waiting two minutes for the concurrency guard; no production API bypass is added.

Pytest retains recent temporary directories for debugging, including generated development keys. All data is synthetic. Services bind to `127.0.0.1` and are stopped after tests. No existing Calibre library, production service or VPS is used. The prior application fixes and lab snapshot were pushed to the two `dev/local-multiuser-integration` GitHub branches; this milestone's local changes have not been committed or pushed. Nothing has been merged or deployed. [CHECKPOINT.md](CHECKPOINT.md) records the exact current Git state.

[ORACLE_STAGING_PLAN.md](ORACLE_STAGING_PLAN.md) is a reviewable future plan. VPS access and deployment require explicit authorization; the plan is not an executed deployment.

Additional executed checks are documented in [COMMANDS.md](COMMANDS.md). `isolated-check.sh` is an optional Bubblewrap wrapper for legacy repository tests: it hides personal files and other mounts and isolates networking. The full legacy suite has pre-existing failures; see the results instead of treating the focused integration pass as repository-wide success.
