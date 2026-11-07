# Local Kolibre–CalibreMCP integration lab

This lab launches a real Kolibre backend, restricted CalibreMCP HTTP server and disposable HTTPS OIDC provider. Tests create founder/sister accounts, genuine native and OIDC access tokens, synthetic EPUBs, application SQLite databases and real Calibre-format libraries. Authorization is exercised through HTTP and MCP, without dependency overrides.

Requirements: Linux, Git, `uv`, Node 22 and npm. Docker was absent on the tested Ubuntu 26.10 machine, so local subprocesses and a Python 3.12 virtual environment provide the equivalent reproducible setup.

```sh
./setup.sh
./test.sh
```

The bootstrap clones the two forks at pinned revisions, applies the focused patches in `patches/`, installs `requirements.lock`, and installs the pinned node-oidc-provider package. It leaves existing checkouts intact. A fresh-directory replay was performed; see [RESULTS.md](RESULTS.md) and [AUDIT.md](AUDIT.md).

`test.sh` writes `evidence/integration.log`. Individual tests can be run with `.venv/bin/python -m pytest tests/test_live_move_recovery.py -v`, or the native/OIDC modules. Each fixture chooses loopback ports, generates random credentials, starts its components and stops them on teardown. The native launcher uses `python -m calibre_mcp.kolibre_bridge`. The OIDC launcher serves the same restricted bridge with Uvicorn TLS. No legacy tools are mounted.

`environment.example` describes the configuration without secrets. `requirements.lock` and `oidc/package-lock.json` pin dependencies. The synthetic EPUB generator, account creation, library permissions, indexing and annotation setup are in `tests/test_live_native.py`; they use the actual application endpoints.

The provider supports DCR, authorization code with required S256 PKCE, and RS256 JWT access tokens for the MCP resource audience. Each run creates a certificate and private signing key in mode-0600 temporary files. `KOLIBRE_OIDC_CA_BUNDLE` scopes backend trust to the JWKS connection; clients use explicit SSL contexts. Default TLS trust rejects the generated certificate. No system trust store is changed.

The FastMCP OAuth client performs discovery, DCR, PKCE, state validation, exchange and token storage. Only user interaction is automated: separate HTTP cookie jars submit each synthetic user's provider password and consent. This verifies a real SDK OAuth client; GUI browsers and third-party desktop clients remain untested. Provider and client caches are memory-only. [Provider documentation](https://github.com/panva/node-oidc-provider/blob/main/docs/README.md).

Recovery tests crash a backend process immediately after a durable journal checkpoint, confirm its exit, then restart normally and call the owner-authenticated recovery endpoint. They also damage disposable source files to verify that recovery preserves the valid target. A test-only journal timestamp adjustment avoids waiting two minutes for the concurrency guard; no production API bypass is added.

Pytest retains recent temporary directories for debugging, including generated development keys. All data is synthetic. Services bind to `127.0.0.1` and are stopped after tests. No existing Calibre library, production service or VPS is used. Nothing is pushed, merged or deployed.

Additional executed checks are documented in [COMMANDS.md](COMMANDS.md). `isolated-check.sh` is an optional Bubblewrap wrapper for legacy repository tests: it hides personal files and other mounts and isolates networking. The full legacy suite has pre-existing failures; see the results instead of treating the focused integration pass as repository-wide success.
