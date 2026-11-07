# Proposed Oracle staging deployment

Prepared 2026-11-07 after the independent MCP Inspector client tests passed. **Plan only: no Oracle connection, inventory, DNS change, installation, migration, or deployment has been performed. Explicit user authorization is required before VPS access or deployment.**

## Scope and decision

Stage only the restricted four-tool MCP bridge and a synthetic two-user Kolibre installation. Start with empty staging databases and synthetic EPUBs; do not import production books, accounts, annotations, BookOrbit storage, Siyuan storage, or existing Calibre libraries. Semantic/vector RAG is outside this milestone.

Preferred placement is a **separate OCI staging VM and data volume**, which keeps resource exhaustion and filesystem mistakes away from BookOrbit/Siyuan. A same-VPS installation is a conditional alternative, not an assumed safe target. Before authorizing that alternative, obtain a read-only inventory of existing listeners, proxy configuration, OS/architecture, service users, mounts, memory/CPU/disk headroom, backup jobs and firewall rules. None of those VPS facts is currently known. Do not replace the existing proxy, reuse its service accounts, alter existing application routes, or upgrade shared runtimes.

Use systemd services and isolated Python environments for Kolibre and the bridge. This matches the tested launch model and preserves the bridge's loopback bind restriction. The repository's quickstart Compose file has default credentials, unrestricted host port mappings, unpinned backend dependencies and no suitable persistent IdP; it is not the deployment manifest. Do not bypass the bridge's loopback guard to make a container network work.

For the persistent staging IdP, propose **Keycloak with a dedicated PostgreSQL database**, isolated from every existing database. This choice supplies an operational login UI and persistent realm/client/key state; it is **not yet an integration-tested substitute** for the disposable node-oidc-provider used locally. The provider substitution must pass local tests before deployment. The disposable provider has in-memory registrations/grants and a test interaction endpoint; it must not be deployed.

## Capacity reservation

These are proposed budgets for two synthetic users, not benchmarked production requirements or observed VPS capacity.

| Resource | Proposed allocation |
|---|---|
| CPU | 4 vCPU staging VM; single Kolibre worker and single bridge worker; cap background FTS work |
| RAM | 8 GiB staging minimum, 12 GiB preferred during builds/indexing; if co-hosted, this is **additional available headroom**, not the total VPS RAM |
| Kolibre | Start with 1 GiB memory budget, up to 2 GiB after measured indexing; one process owns watchers/write queue/SQLite |
| Restricted bridge | 512 MiB budget; no Calibre/LanceDB/vector initialization or direct library access |
| Keycloak | 2 GiB process/container budget; tune heap within that limit |
| Dedicated PostgreSQL | 512 MiB initial budget; measure connections and cache needs |
| TLS proxy/static UI | 128–256 MiB allowance; reuse existing listener only through approved additive configuration |
| Disk | 20 GiB OS/releases plus **at least 50 GiB separate staging data volume** for tiny synthetic libraries; grow from measured usage |
| Free disk reserve | At least 30% free; provision space for source + private target + recovery copies + backup snapshot simultaneously |

Keycloak recommends a 2 GB limit for smaller container deployments; the remaining allocations above are our starting estimates. [Keycloak memory guidance](https://www.keycloak.org/server/containers).

Do dependency/image builds locally where practical. Check target CPU architecture before choosing artifacts; the tested machine is x86_64, and Oracle Ampere/ARM compatibility has not been demonstrated. Pin immutable application hashes, dependency locks, and reviewed Keycloak/PostgreSQL/proxy versions or image digests. Do not use floating `latest` tags or assume the current Dockerfile's Python 3.11 matches the tested Python 3.12 environment.

## Network and endpoint contract

All names below are **unregistered planning placeholders** under `.example`, not existing DNS records. Assign user-approved actual hostnames before creating certificates or issuing tokens. Verify reserved ports are unused before applying anything; do not displace existing listeners.

| Component | Proposed bind / mapping | External route |
|---|---|---|
| Approved TLS ingress | Public 443; optionally 80 only for ACME/redirect | New staging hostnames only |
| Kolibre backend | `127.0.0.1:18081` | `https://kolibre-stage.example/` to backend API; optional UI under same origin |
| Restricted bridge | `127.0.0.1:18082` | Entire `https://mcp-stage.example/` origin, including `/mcp` and `/.well-known/*` |
| Keycloak | `127.0.0.1:18083` | Selected login/discovery/token/JWKS/DCR paths on `https://auth-stage.example/` |
| IdP health/management | `127.0.0.1:19000` | No public route |
| PostgreSQL | Dedicated Unix socket preferred; otherwise `127.0.0.1:15432` | No public route |
| MCP OAuth callback | Client workstation's loopback, chosen client port | Never a VPS port forward; redirect lands in the actual client |

No public 8081/10721/18081/18082/18083/19000/15432. OCI NSGs/security lists **and** the host firewall must enforce the intended ingress; preserve SSH/VPN administrative access and all existing services. If a private trial is chosen, restrict TLS ingress to approved tester addresses/VPN. Do not add a browser login gate in front of MCP discovery/token endpoints; it can prevent clients from handling OAuth 401 challenges. [OCI security rules](https://docs.oracle.com/en-us/iaas/Content/Network/Concepts/securityrules.htm).

Use publicly trusted HTTPS certificates for approved real hostnames, with automated renewal and monitoring. TLS must verify normally in all clients and JWKS calls. No test keys, local CA, `verify=False`, or `NODE_TLS_REJECT_UNAUTHORIZED=0` in staging.

Proxy the MCP origin without path stripping, response buffering, or caching. Preserve Authorization, WWW-Authenticate, MCP session/protocol headers, Accept, content type and methods including streaming GET/POST/DELETE. Set streaming/read timeouts to permit long-lived MCP responses (initial proposal 10 minutes), then test idle reconnect. Apply a small MCP request-size limit, and a separate bounded upload limit on Kolibre. Trust forwarded headers only from the loopback proxy, which must overwrite incoming forwarded headers. Caddy is a candidate for a new VM; on an existing VPS adapt the existing proxy instead of starting a competing listener. [Caddy streaming controls](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy).

A public-origin check must establish that the initialize response, protected-resource metadata and authorization-server metadata refer to these same HTTPS names. Merely reaching `/mcp` from localhost does not verify the deployed proxy contract.

## Identity configuration and unresolved provider gate

Proposed nonsecret application configuration, once actual domains replace the placeholders:

```dotenv
DATA_DIR=/var/lib/kolibre-stage
DATABASE_URL=sqlite:////var/lib/kolibre-stage/app.db
KOLIBRE_BACKEND_URL=http://127.0.0.1:18081
KOLIBRE_MCP_BIND=127.0.0.1
KOLIBRE_MCP_PORT=18082
KOLIBRE_MCP_PUBLIC_URL=https://mcp-stage.example
KOLIBRE_MCP_OIDC_ISSUER=https://auth-stage.example/realms/kolibre-stage
KOLIBRE_OIDC_ISSUER=https://auth-stage.example/realms/kolibre-stage
KOLIBRE_OIDC_JWKS_URI=https://auth-stage.example/realms/kolibre-stage/protocol/openid-connect/certs
KOLIBRE_OIDC_AUDIENCE=https://mcp-stage.example/mcp
KOLIBRE_MCP_OIDC_SCOPES=openid books:read
CORS_ORIGINS=https://kolibre-stage.example
```

`KOLIBRE_MCP_PUBLIC_URL` has no `/mcp`; the audience includes `/mcp`. Configure Keycloak RS256 JWT access tokens with that exact audience and the advertised issuer. Configure code flow with mandatory S256 PKCE, no implicit/password grant for the MCP client, and narrow redirect URIs/client scopes. Start with a five-minute access-token lifetime; this is a proposed staging policy, not a tested refresh policy. Link each verified `(issuer, subject)` to its own synthetic Kolibre user with native authentication and password confirmation. Never map by email or copy development identity links into a new issuer.

The bridge's advertised issuer currently documents a DCR-capable provider. Keycloak's anonymous DCR is restricted by default; do **not** disable its protections globally. Proposed staging policy: dedicated realm, only approved tester origins/registration source addresses and loopback redirect patterns, consent required, only necessary protocol mappers/scopes, and a low registration limit. Test the exact client's registration request through the public-origin proxy. If this cannot be constrained safely, use a pre-registered public client only after proving this bridge/client combination supports that path, or select another tested provider. Do not call DCR, audience/resource handling, static-client operation, key rotation or refresh renewal verified merely because Keycloak supports OIDC. [Keycloak registration policies](https://www.keycloak.org/securing-apps/client-registration).

Fix the IdP's external hostname and trust only the proxy address for forwarded headers. Keep admin routes and management/metrics off the public vhost; use an administrative tunnel or separate private endpoint. A dedicated DB persists realm subjects, signing keys, registrations and grants. [Keycloak hostname configuration](https://www.keycloak.org/server/hostname), [reverse-proxy guidance](https://www.keycloak.org/server/reverseproxy).

Generate staging-native signing keys, administrator credentials, IdP administration credentials and DB credentials after authorization. Keep them outside releases/Git in root-owned protected configuration or systemd credentials, readable only by the intended service. Inspect how credentials are delivered before writing units; the existing app reads environment values, so a protected service environment file may be necessary. Native tokens currently default to seven days: agree a staging policy or implement a separately tested configuration mechanism before issuing non-test accounts. No secret values belong in this plan or deployment logs.

## Persistent storage and process isolation

| Path (proposed) | Owner / purpose |
|---|---|
| `/opt/kolibre-stage/releases/<Kolibre-hash>/` | Root-owned immutable source and isolated venv; runtime user cannot rewrite it |
| `/opt/kolibre-mcp-stage/releases/<CalibreMCP-hash>/` | Separate bridge release/venv; no user library discovery |
| `/var/lib/kolibre-stage/` | Dedicated `kolibre-stage` user, mode 0700; app.db, `libraries/`, ingest, covers, users/devices, dictionaries, journal-related files and write-queue state |
| `/var/lib/kolibre-stage/libraries/<folder>/` | `metadata.db`, actual formats, covers, full-text SQLite files; never a production-library symlink |
| `/var/lib/kolibre-stage-idp/` | Dedicated IdP/DB users; durable PostgreSQL database, needed IdP configuration and key material |
| `/etc/kolibre-stage/`, `/etc/kolibre-mcp-stage/` | Protected runtime settings/credentials; no shared production secret files |
| `/var/backups/kolibre-stage/` | Separate backup identity and retention quota, plus encrypted off-host copies |

No bridge mount or permission to read Kolibre book storage is needed: it talks only to the configured backend. Do not put either service in BookOrbit/Siyuan groups or share their volumes, Docker sockets, SSH keys or environment files. Protect service homes and system paths, use `NoNewPrivileges`, private temp directories and explicit writable paths. On an existing VPS identify actual production data paths and make them inaccessible to staging service units. Separate Unix users are not protection against root; a new VM is the stronger boundary.

Use one worker for the SQLite-backed Kolibre process, preventing duplicate watchers/migration/write-queue ownership. Set memory/CPU/task limits in a staging systemd slice, log rotation and disk quotas/alerts. Do not let staging OOM or FTS work consume the reserved production budget. Disable auto wiki scraping/outbound enrichment for synthetic tests. Keep OPDS off unless separately included in the approved staging validation.

For optional React UI, validate its backend-origin behavior locally before inclusion. The existing frontend build primarily selects a backend port; HTTPS same-origin proxying and external hostname behavior have not been demonstrated. A wrong build-time port must not expose 18081 publicly as a workaround.

## Backup, restore and rollback

Proposed objectives for this synthetic stage: **RPO 24 hours, RTO 2 hours**, plus a manual backup immediately before every update or migration. Retain 7 daily, 4 weekly and 3 monthly encrypted off-host copies, subject to an approved storage budget. Keep backup keys outside the backed-up host and test recovery access.

Back up the **complete** Kolibre DATA_DIR and configuration/release manifest, not app.db alone. App DB, Calibre databases, book files, annotations/device data and move journals must describe one consistent point. Quiesce uploads/moves/indexing, stop only staging writers, confirm their exit and no active move, then snapshot/copy the whole data tree while quiesced. Do not `cp` open SQLite databases and ignore WAL/SHM. Take the IdP DB's supported consistent PostgreSQL backup and retain IdP settings/signing identity as part of the same documented generation. Secrets backups remain encrypted and access controlled.

OCI volume backups may supplement this procedure, but they do not by themselves establish application-level consistency across live SQLite files and independent IdP storage. [OCI block volume backup documentation](https://docs.oracle.com/en-us/iaas/Content/Block/Concepts/blockvolumebackups.htm).

Restore into a separate empty directory/VM: verify manifest/hashes and SQLite integrity, check both account mappings and all three libraries, repeat MCP private-content denials and inspect transfer journals before allowing writes. Never auto-recover a `needs_review` transfer by deleting a copy. A rollback restores the **matching prior data snapshot and release**, not just the executable; Kolibre runs schema work on startup. Do not point an older build at a newly migrated DB speculatively. Never restore over BookOrbit/Siyuan or a production library.

## Ordered execution gates — not executed

1. Review this plan; choose new VM versus co-hosting, actual domains, allowed tester addresses and budget. **Obtain explicit authorization for the precise VPS access/deployment scope.**
2. After authorization, inventory target read-only and record baseline BookOrbit/Siyuan health, listeners, resource usage and backups. Stop if capacity/port/storage isolation cannot be demonstrated.
3. Before changing the VPS, pin/test the proposed persistent IdP, HTTPS proxy, target architecture, dependency artifacts and optional UI locally. Repeat Inspector native/OAuth isolation, registration, expiry/relogin and revocation/reconnect using the selected provider. Add refresh and key-rotation checks if either is promised for stage.
4. Prepare concrete service units/proxy/DNS/firewall/storage/backup changes for the inventoried target. Review only additive changes; do not copy quickstart Compose or test credentials. Preserve baseline configuration and verify a restore into an isolated path.
5. Deploy a fresh **synthetic** stage only within the authorized scope, create users/libraries/explicit links, then run the acceptance checks through the real HTTPS endpoint from the actual client workstation. No production-data migration.
6. Confirm BookOrbit/Siyuan routes, health and data paths are unchanged; compare resource headroom to baseline. Record exact release hashes, config revision excluding secrets, public-origin metadata, protocol/tool discovery, test output and backup restore evidence. Close public staging access if acceptance fails.

Acceptance requires the four-tool allowlist; successful native and OIDC sessions for both users; foreign catalogs/search/notes denied; live revocation and expiry enforced before/after reconnect; no production mounts/routes/DB changes; validated TLS/discovery/callback behavior; persistent IdP restart; and a demonstrated restore. Security review, broader endpoint audit, refresh behavior, load limits and semantic RAG remain explicit separate work. Local Inspector success alone does not authorize this plan's execution.
