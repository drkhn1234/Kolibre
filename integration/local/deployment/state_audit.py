"""Credential-free durable-state/isolation evidence for the synthetic stage."""

import hashlib
import json
import sqlite3
import subprocess
import urllib.request
from pathlib import Path

root = Path("/var/lib/kolibre-stage")
with sqlite3.connect(root / "app.db") as db:
    assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    users = list(
        db.execute(
            "SELECT id,username,is_admin,oidc_issuer,oidc_subject FROM users ORDER BY id"
        )
    )
    libraries = list(
        db.execute(
            "SELECT folder_name,is_private,owner_id FROM libraries ORDER BY folder_name"
        )
    )
    active_moves = db.execute(
        "SELECT count(*) FROM private_book_moves WHERE active_key IS NOT NULL"
    ).fetchone()[0]
    counts = {
        table: db.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        for table in ("highlights", "reading_positions", "device_books")
    }
assert [(row[1], row[2]) for row in users] == [("founder", 1), ("sister", 0)]
assert len(libraries) == 3 and active_moves == 0
files = []
for folder, private, owner in libraries:
    directory = root / "libraries" / folder
    assert directory.resolve().is_relative_to(root)
    with sqlite3.connect(directory / "metadata.db") as db:
        assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    epubs = list(directory.rglob("*.epub"))
    assert len(epubs) == 1
    files.append(
        {
            "library": folder,
            "private": bool(private),
            "owner_id": owner,
            "epub_sha256": hashlib.sha256(epubs[0].read_bytes()).hexdigest(),
            "file_uid": epubs[0].stat().st_uid,
            "file_mode": oct(epubs[0].stat().st_mode & 0o777),
        }
    )
with urllib.request.urlopen(
    "http://127.0.0.1:18083/kolibre-auth-stage/realms/kolibre-stage/protocol/openid-connect/certs",
    timeout=10,
) as response:
    jwks = json.load(response)
fingerprints = sorted(
    hashlib.sha256(json.dumps(key, sort_keys=True).encode()).hexdigest()
    for key in jwks["keys"]
)


def psql(query):
    return subprocess.run(
        [
            "docker",
            "exec",
            "kolibre-stage-idp-db-1",
            "psql",
            "-U",
            "kolibre_idp",
            "-d",
            "keycloak",
            "-At",
            "-c",
            query,
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


client_ids = psql(
    "SELECT client_id FROM client WHERE realm_id=(SELECT id FROM realm WHERE name='kolibre-stage') ORDER BY client_id"
).splitlines()
provider_ttl = int(
    psql("SELECT access_token_lifespan FROM realm WHERE name='kolibre-stage'")
)
bootstrap_count = int(
    psql(
        "SELECT count(*) FROM user_entity WHERE username='stage-bootstrap' AND realm_id=(SELECT id FROM realm WHERE name='master')"
    )
)
assert provider_ttl == 300 and bootstrap_count == 0
result = {
    "boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
    "users": [
        {
            "id": row[0],
            "username": row[1],
            "administrator": bool(row[2]),
            "binding_sha256": hashlib.sha256(
                (str(row[3]) + "|" + str(row[4])).encode()
            ).hexdigest(),
        }
        for row in users
    ],
    "libraries": files,
    "counts": counts,
    "active_moves": active_moves,
    "jwks_fingerprints": fingerprints,
    "oidc_client_fingerprints": sorted(
        hashlib.sha256(value.encode()).hexdigest() for value in client_ids
    ),
    "oidc_access_token_seconds": provider_ttl,
    "bootstrap_admin_count": bootstrap_count,
    "settings_modes": {
        p.name: oct(p.stat().st_mode & 0o777)
        for p in Path("/etc/kolibre-stage").glob("*.env")
    },
    "services": subprocess.run(
        [
            "systemctl",
            "show",
            "kolibre-stage",
            "kolibre-mcp-stage",
            "-p",
            "User",
            "-p",
            "Group",
            "-p",
            "ProtectHome",
            "-p",
            "ProtectSystem",
            "-p",
            "NoNewPrivileges",
            "-p",
            "MemoryMax",
            "-p",
            "MainPID",
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout,
}
print(json.dumps(result, indent=2))
