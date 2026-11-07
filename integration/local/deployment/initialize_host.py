"""Root-only initial staging directories/secrets. Does not start any service."""

import json
import os
import pwd
import secrets
import subprocess
from pathlib import Path


def run(*args):
    subprocess.run(args, check=True, capture_output=True)


def private(path, text):
    descriptor = os.open(path, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w") as handle:
        handle.write(text)
    os.chmod(path, 0o600)


def environment(path, values):
    # Values are controlled URL/path/numeric settings or generated URL-safe secrets.
    assert all("\n" not in value and "\r" not in value for value in values.values())
    private(path, "".join(f"{name}={value}\n" for name, value in values.items()))


assert os.geteuid() == 0, "Run with sudo"
for user in ("kolibre-stage", "kolibre-mcp-stage"):
    try:
        pwd.getpwnam(user)
    except KeyError:
        run(
            "useradd",
            "--system",
            "--user-group",
            "--no-create-home",
            "--shell",
            "/usr/sbin/nologin",
            user,
        )
root = Path("/etc/kolibre-stage")
root.mkdir(mode=0o700, exist_ok=True)
os.chmod(root, 0o700)
credentials = root / "credentials.json"
if credentials.exists():
    raise SystemExit(
        "Credentials already exist; refuse to overwrite a persistent installation"
    )
data = {
    "native_passwords": {
        who: secrets.token_urlsafe(32) for who in ("founder", "sister")
    },
    "oidc_passwords": {
        who: secrets.token_urlsafe(32) for who in ("founder", "sister", "unlinked")
    },
    "native_signing_key": secrets.token_hex(32),
    "database_password": secrets.token_urlsafe(40),
    "bootstrap_password": secrets.token_urlsafe(40),
    "operator_password": secrets.token_urlsafe(40),
}
private(credentials, json.dumps(data, indent=2) + "\n")
state = Path("/var/lib/kolibre-stage")
state.mkdir(mode=0o700, exist_ok=True)
account = pwd.getpwnam("kolibre-stage")
os.chown(state, account.pw_uid, account.pw_gid)
os.chmod(state, 0o700)
origin = "https://books.drkhn.site"
issuer = origin + "/kolibre-auth-stage/realms/kolibre-stage"
environment(
    root / "backend.env",
    {
        "DATA_DIR": str(state),
        "DATABASE_URL": "sqlite:////var/lib/kolibre-stage/app.db",
        "ADMIN_USERNAME": "founder",
        "ADMIN_PASSWORD": data["native_passwords"]["founder"],
        "SECRET_KEY": data["native_signing_key"],
        "KOLIBRE_ACCESS_TOKEN_EXPIRE_MINUTES": "15",
        "KOLIBRE_OIDC_ISSUER": issuer,
        "KOLIBRE_OIDC_AUDIENCE": origin + "/kolibre-mcp-stage/mcp",
        "KOLIBRE_OIDC_JWKS_URI": issuer + "/protocol/openid-connect/certs",
        "CORS_ORIGINS": origin,
        "PYTHONUNBUFFERED": "1",
    },
)
environment(
    root / "bridge.env",
    {
        "KOLIBRE_BACKEND_URL": "http://127.0.0.1:18081",
        "KOLIBRE_MCP_BIND": "127.0.0.1",
        "KOLIBRE_MCP_PORT": "18082",
        "KOLIBRE_MCP_OIDC_ISSUER": issuer,
        "KOLIBRE_MCP_PUBLIC_URL": origin + "/kolibre-mcp-stage",
        "KOLIBRE_MCP_OIDC_SCOPES": "openid books:read",
        "CALIBRE_MCP_LOG_FILE": "/var/log/kolibre-mcp-stage/bridge.jsonl",
        "PYTHONUNBUFFERED": "1",
    },
)
environment(
    root / "postgres.env",
    {
        "POSTGRES_USER": "kolibre_idp",
        "POSTGRES_DB": "keycloak",
        "POSTGRES_PASSWORD": data["database_password"],
    },
)
environment(
    root / "keycloak.env",
    {
        "KC_DB": "postgres",
        "KC_DB_URL": "jdbc:postgresql://idp-db:5432/keycloak",
        "KC_DB_USERNAME": "kolibre_idp",
        "KC_DB_PASSWORD": data["database_password"],
        "KC_DB_POOL_INITIAL_SIZE": "1",
        "KC_DB_POOL_MIN_SIZE": "1",
        "KC_DB_POOL_MAX_SIZE": "10",
        "KC_HOSTNAME": origin + "/kolibre-auth-stage",
        "KC_HTTP_ENABLED": "true",
        "KC_HTTP_RELATIVE_PATH": "/kolibre-auth-stage",
        "KC_PROXY_HEADERS": "xforwarded",
        "KC_PROXY_TRUSTED_ADDRESSES": "172.30.71.1/32",
        "KC_BOOTSTRAP_ADMIN_USERNAME": "stage-bootstrap",
        "KC_BOOTSTRAP_ADMIN_PASSWORD": data["bootstrap_password"],
        "KC_HEALTH_ENABLED": "true",
        "JAVA_OPTS_KC_HEAP": "-Xms128m -Xmx1024m",
    },
)
print(
    "Created isolated users, protected settings and fresh staging secrets; no values printed"
)
