> New knowledge-retrieval milestone: see [KNOWLEDGE.md](KNOWLEDGE.md) for current sources, fifth-tool staging tests and limitations; [CHATGPT_ACCEPTANCE.md](CHATGPT_ACCEPTANCE.md) records the actual four-tool ChatGPT acceptance. Earlier results below remain historical.

# Oracle staging execution log

Current milestone: explicitly authorized VPS access, administration and deployment, starting 2026-11-07. The former checkpoint-only and no-VPS stop conditions are superseded. No paid OCI resource provisioning or draft PR merges.

## Preserved sources

- Lab interoperability work committed before deployment: `b73d25fb026cf08b0a07a53052d0e1a8b11ff62e` (`dev/local-integration-lab`, local repository without remote).
- Kolibre `d4155e553b442d7dcb321f0a491f9066b9a51968`, `dev/local-multiuser-integration`; clean and exact remote match.
- CalibreMCP `12ecf368644609156d4f16ba9e43663284b79153`, same development branch; clean and exact remote match.
- No credentials/keys/databases/logs were committed. No application branch merge or reset.

## Infrastructure baseline

Authenticated connection `ssh oracle` resolves to user `ubuntu` on `oracle-drkhn.taila29458.ts.net`; sudo works. No SSH key contents were read or copied.

- Ubuntu 24.04.5 LTS, aarch64, 2 CPUs, 7915 MiB RAM, approximately 6839 MiB available, no swap; root ext4 96 GiB, 83 GiB available. Low initial load (~0.07).
- Docker 29.9.2; Caddy 2.11.7; Python 3.12.3; Node 22.23.4. Docker, Caddy, Tailscale and bookorbit-mcp enabled at boot.
- Existing healthy BookOrbit app/db and two Siyuan containers. Loopback binds: BookOrbit 3000, BookOrbit MCP systemd 3001, Siyuan 6806, sister's Siyuan 6807. GET baseline: 3000=200, 3001 root=404, both Siyuan roots=401 (expected authentication).
- Existing data: `/home/ubuntu/services/bookorbit/{books,data/app,data/postgres}`, BookOrbit DB also has a Docker-managed volume at `/var/lib/postgresql`; Siyuan workspaces `/home/ubuntu/services/siyuan/workspace` and `/home/ubuntu/services/siyuan-ladin/workspace`. Never mount these into staging.
- Existing Compose projects: bookorbit, siyuan, siyuan-ladin. No changes planned to their containers/configuration/data.
- Existing Caddyfile SHA256 before change: `e79fa08893d5980604db0371100f6bf6658c175961adfdc92afb11f4b2544bed`. Caddy bound 10.0.0.91:80/443, admin 127.0.0.1:2019. Existing vhosts `books.drkhn.site`, `notes.drkhn.site`, `notes-ladin.drkhn.site`. BookOrbit's existing `/mcp` and auth/discovery routes must remain intact.
- Public VPS IPv4 92.5.118.40; verified `https://books.drkhn.site/` returns 200 with normal certificate validation. Caddy has Let's Encrypt certificates for the existing vhosts in its private data directory. Do not copy private TLS keys into this repository.
- IPv4 host firewall accepts established/loopback/SSH and 80/443 on the primary NIC, then rejects other inbound traffic; Docker forwarding rules and Oracle metadata-service safeguards exist. IPv6 has Tailscale/Docker rules; do not expose IPv6 wildcard staging listeners.
- Tailscale online, private addresses 100.74.111.119 and fd7a:115c:a1e0::fa01:6feb. Existing Serve HTTP ports 3000/6806 remain. MagicDNS and certificate domain enabled.
- `drkhn.site` authoritative NS are Spaceship. The connected Cloudflare zone is pending and has no A records; no Cloudflare DNS changes were made. New staging hostnames do not resolve. Do not migrate the zone or alter production DNS merely to deploy stage.

## Current persistent staging

Authoritative current revisions, exact tests and limitations are in
[VPS_RESULTS.md](VPS_RESULTS.md); connection instructions are in
[CHATGPT.md](CHATGPT.md). CHECKPOINT.md is the recovery entry point.

The existing VM accommodates the measured resource-limited services. Source
releases live under /opt/kolibre-stage/releases and /opt/kolibre-mcp-stage/releases;
current symlinks select them. No paid resource or PR merge was needed.

| Public path on https://books.drkhn.site | Loopback target |
|---|---|
| /kolibre-api-stage/ | 127.0.0.1:18081 (prefix stripped) |
| /kolibre-mcp-stage/mcp | 127.0.0.1:18082/mcp (stage prefix stripped) |
| /.well-known/oauth-protected-resource/kolibre-mcp-stage/mcp | 127.0.0.1:18082, unchanged path |
| /kolibre-auth-stage/ | 127.0.0.1:18083, unchanged path |

The two exact stage AS/OIDC well-known aliases route to Keycloak's canonical
discovery endpoint, ahead of existing BookOrbit handlers. Keycloak's public
master/admin routes remain blocked. Backend/API ports are loopback-only;
PostgreSQL is private. Caddy's original vhost and BookOrbit discovery endpoints
are preserved. A graceful reload updated the single approved DCR source IP.

Backend and bridge have separate service users, ProtectSystem=strict,
ProtectHome=true, NoNewPrivileges and bounded memory/CPU. Keycloak uses production
start with PostgreSQL in a separate Docker network/volume, pinned image digests
in deployment/compose.yml, and an experimental resource-indicators feature.
Credentials are generated, mode 0600 under /etc/kolibre-stage, never in Git.
Data/libraries/SQLite reside under /var/lib/kolibre-stage (0700).

Native tokens normally last 15 minutes. OIDC tokens normally last 300 seconds;
refresh rotates with reuse zero. Explicit issuer/subject linking never uses an
email heuristic. Anonymous DCR retains trusted-source/client-URI/consent/scope/
mapper/full-scope safeguards and a 24-client cap. The predefined confidential
ChatGPT client is separately provisioned with an exact callback and required
S256; no OpenAI IP exception was added to DCR.

Encrypted stage snapshots retain 7 daily, 4 weekly, 3 monthly. The backup timer
is enabled and snapshots are present. Offline decryption identity is on the
workstation only; a full replacement-host restore drill/off-host replication
remains to be demonstrated with durable evidence. Backups briefly stop only
stage applications/IdP and restore their prior running state.

The prior authorized real VM reboot is evidenced by state-before-reboot.json
and state-after-reboot.json: boot IDs differ; book hashes, linked identities,
database counts, signing keys and registered clients match. This milestone did
not repeat that reboot. The prior deployment necessarily had a reboot interruption;
it is inaccurate to claim zero interruption throughout the entire project.
BookOrbit and Siyuan recovered and remain healthy on unchanged data mounts.

Source upgrades use deployment/upgrade_sources.py, uploaded Git archives and
independent copied dependency environments. Readiness failure restores old
symlinks and restarts only the two stage services. A file-level source manifest
is persisted at /etc/kolibre-stage/revisions.json. Application revisions are
c06a7cea001c853a9dfc74bd1e6e8ce627307e26 and
072c06541585dc494ad137faf84603f8d6617194, respectively.

Final offline compatibility follow-up: the predefined ChatGPT client explicitly
associates optional offline_access; only founder/sister receive that IdP role.
Offline sessions have an eight-hour max and 30-minute idle timeout. Separate
standard audience mappers preserve both the resource-client ID and MCP URL on
offline refresh. Real basic/offline refresh, revocation and MCP isolation pass;
local Keycloak regression rerun passes. No application services needed a restart
for these provider configuration updates.
