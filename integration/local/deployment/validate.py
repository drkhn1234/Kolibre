"""Seed/verify only the synthetic Oracle stage, using the shipped Inspector CLI."""

import argparse
import json
import os
import ssl
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT))

from test_inspector_client import Inspector, matrix, revoke_and_reconnect
from test_keycloak_local import keycloak_token
from test_live_move_recovery import seed_readers
from test_live_native import Stack

from deployment.client_support import keycloak_browser


class RemoteLab(Stack):
    def __init__(self):
        self.directory = ROOT / "runtime/vps-validation"
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.directory.chmod(0o700)
        secrets_path = ROOT / "runtime/staging-credentials.json"
        assert secrets_path.stat().st_mode & 0o077 == 0, (
            "Protect local credentials (0600)"
        )
        credentials = json.loads(secrets_path.read_text())
        self.passwords = credentials["native_passwords"]
        self.oidc_passwords = credentials["oidc_passwords"]
        self.tokens = {}
        self.url = "https://books.drkhn.site/kolibre-api-stage"
        self.mcp_url = "https://books.drkhn.site/kolibre-mcp-stage/mcp"
        self.issuer = "https://books.drkhn.site/kolibre-auth-stage/realms/kolibre-stage"
        self.tls = (
            ssl.create_default_context()
        )  # Public certificates; no test CA override.
        self.state_path = self.directory / "synthetic-state.json"

    def start(self, *args, **kwargs):
        raise RuntimeError(
            "Remote validation must not launch local substitute services"
        )

    def save(self):
        data = {
            "sister": self.sister,
            "private": self.private,
            "books": self.books,
            "notes": [[list(key), value] for key, value in self.notes.items()],
            "devices": self.devices,
        }
        with open(
            os.open(self.state_path, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600), "w"
        ) as handle:
            json.dump(data, handle, indent=2)

    def restore(self):
        data = json.loads(self.state_path.read_text())
        for key in ("sister", "private", "books", "devices"):
            setattr(self, key, data[key])
        self.notes = {tuple(key): value for key, value in data["notes"]}

    def progress(self):
        for who, expected in [("founder", 0.42), ("sister", 0.78)]:
            result = self.ok(
                "GET",
                f"/api/kolibre/books/{self.books['shared']}/reading-position?library=shared",
                who=who,
            )
            assert result["percentage"] == expected
            other = "sister" if who == "founder" else "founder"
            assert (
                self.request(
                    "GET",
                    f"/api/kolibre/books/{self.books[self.private[other]]}/reading-position?library={self.private[other]}",
                    who=who,
                ).status_code
                == 404
            )


def seed(lab):
    assert not lab.state_path.exists(), "Synthetic state already seeded; use verify"
    lab.login("founder")
    lab.ok("PUT", "/api/kolibre/settings/auto-wiki-scrape", json={"enabled": False})
    lab.sister = lab.ok(
        "POST",
        "/api/users",
        json={"username": "sister", "password": lab.passwords["sister"]},
    )
    lab.login("sister")
    lab.ok("POST", "/api/kolibre/libraries", json={"name": "shared"})
    lab.ok(
        "PUT",
        "/api/kolibre/libraries/shared/permessi",
        json={"user_id": lab.sister["id"], "can_edit": True, "can_upload": True},
    )
    # Seed over HTTP; inspect the physical files separately on the actual VPS.
    from test_live_native import epub

    lab.books, lab.private, lab.notes = {}, {}, {}
    import time

    for owner, visibility in [
        ("founder", "shared"),
        ("founder", "private"),
        ("sister", "private"),
    ]:
        title = f"{owner} {visibility} book"
        staged = lab.ok(
            "POST",
            "/api/kolibre/ingest/upload",
            who=owner,
            data={"visibility": visibility},
            files={
                "files": (
                    "synthetic.epub",
                    epub(title, f"quasar {owner} {visibility} passage"),
                    "application/epub+zip",
                )
            },
        )
        assert not staged["rejected"]
        imported = lab.ok(
            "POST",
            "/api/kolibre/ingest/import-book",
            who=owner,
            json={"id": staged["staged"][0]["id"], "library": "shared", "title": title},
        )
        folder = imported["library"]
        lab.books[folder] = imported["book_id"]
        if visibility == "private":
            assert folder != "shared"
            lab.private[owner] = folder
        lab.ok(
            "PUT",
            f"/api/kolibre/fulltext/settings?library={folder}",
            who=owner,
            json={"enabled": True},
        )
        lab.ok("POST", f"/api/kolibre/fulltext/reindex?library={folder}", who=owner)
        for _ in range(150):
            if lab.ok(
                "GET",
                f"/api/kolibre/fulltext/search?library={folder}&q=quasar",
                who=owner,
            )["results"]:
                break
            time.sleep(0.2)
        else:
            raise AssertionError("Remote lexical indexing did not complete")
    for owner in ("founder", "sister"):
        for folder in ("shared", lab.private[owner]):
            lab.notes[owner, folder] = lab.ok(
                "POST",
                "/api/kolibre/annotations",
                who=owner,
                json={
                    "library": folder,
                    "calibre_book_id": lab.books[folder],
                    "text": f"{owner}-secret-note",
                },
            )
    lab.ok("PUT", "/api/kolibre/settings/opds-feed", json={"enabled": False})
    lab.devices = seed_readers(lab)
    lab.save()
    tokens = {}
    import httpx

    for who in ("founder", "sister"):
        token = keycloak_token(lab, who)
        assert (
            httpx.get(
                lab.url + "/api/users/me",
                headers={"Authorization": "Bearer " + token},
                trust_env=False,
            ).status_code
            == 401
        )
        lab.ok(
            "POST",
            "/api/users/me/oidc-link",
            who=who,
            json={"password": lab.passwords[who], "oidc_access_token": token},
        )
        tokens[who] = token
    assert (
        lab.request(
            "POST",
            "/api/users/me/oidc-link",
            who="founder",
            json={
                "password": lab.passwords["founder"],
                "oidc_access_token": tokens["sister"],
            },
        ).status_code
        == 409
    )
    unlinked = keycloak_token(lab, "unlinked")
    assert (
        httpx.get(
            lab.url + "/api/users/me",
            headers={"Authorization": "Bearer " + unlinked},
            trust_env=False,
        ).status_code
        == 401
    )
    print(
        "Seeded two native accounts, three libraries, synthetic EPUBs/notes/progress/devices, and two explicit OIDC links; unlinked/cross-link denied."
    )


def verify(lab, auth, revocation):
    lab.restore()
    for who in ("founder", "sister"):
        lab.login(who)
    lab.progress()
    clients = [
        Inspector(lab, who, lab.tokens[who] if auth == "native" else None)
        for who in ("founder", "sister")
    ]
    for client in clients:
        # Separate permanent evidence per mode rather than overwrite a trace.
        client.archive_name = auth
    try:
        for client in clients:
            client.connect(oauth=auth == "oidc", browser=keycloak_browser)
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(matrix, clients))
        if revocation:
            revoke_and_reconnect(lab, *clients)
        print(
            f"Public HTTPS Inspector {auth}: two identities, four tools, concurrent privacy matrix, reading state, revocation/reconnect={revocation}: PASS"
        )
    finally:
        for client in clients:
            client.close()
            source = lab.directory / f"inspector-{client.who}.json"
            (ROOT / "evidence/deployment" / f"{auth}-{client.who}.json").write_text(
                source.read_text()
            )


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "phase", choices=["seed", "verify-native", "verify-oidc", "verify-expiry"]
    )
    parser.add_argument("--no-revocation", action="store_true")
    arguments = parser.parse_args(argv)
    if arguments.phase == "verify-expiry":
        import subprocess

        subprocess.run([sys.executable, str(ROOT / "deployment/expiry.py")], check=True)
        return
    lab = RemoteLab()
    if arguments.phase == "seed":
        seed(lab)
    else:
        verify(
            lab, arguments.phase.removeprefix("verify-"), not arguments.no_revocation
        )


if __name__ == "__main__":
    main()
