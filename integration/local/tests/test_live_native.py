"""Real processes, native logins and MCP HTTP; disposable state only."""

import asyncio
import io
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import time
import zipfile

import httpx
import pytest
from fastmcp import Client

ROOT = Path(__file__).resolve().parents[1]
TOOLS = {
    "kolibre_list_libraries",
    "kolibre_list_books",
    "kolibre_search_fulltext",
    "kolibre_my_annotations",
}


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class Stack:
    def __init__(self, directory):
        self.directory = directory
        self.backend_port, self.bridge_port = free_port(), free_port()
        self.url = f"http://127.0.0.1:{self.backend_port}"
        self.mcp_url = f"http://127.0.0.1:{self.bridge_port}/mcp"
        self.passwords = {
            name: secrets.token_urlsafe(24) for name in ("founder", "sister")
        }
        self.env = {
            **os.environ,
            "DATA_DIR": str(directory / "data"),
            "DATABASE_URL": f"sqlite:///{directory}/app.db",
            "SECRET_KEY": secrets.token_hex(32),
            "ADMIN_USERNAME": "founder",
            "ADMIN_PASSWORD": self.passwords["founder"],
            "KOLIBRE_BACKEND_URL": self.url,
            "KOLIBRE_MCP_PORT": str(self.bridge_port),
            "PYTHONPATH": str(ROOT / "repos/Kolibre"),
        }
        self.processes = []
        self.logs = []
        self.tokens = {}

    def start(self, name, args, port, executable=None):
        log = open(self.directory / f"{name}.log", "ab")
        self.logs.append(log)
        proc = subprocess.Popen(
            [executable or sys.executable, *args],
            env=self.env,
            cwd=self.directory,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        self.processes.append(proc)
        for _ in range(200):
            if proc.poll() is not None:
                raise RuntimeError(f"{name} failed; inspect {log.name}")
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                    return proc
            except OSError:
                time.sleep(0.1)
        raise RuntimeError(f"{name} did not listen; inspect {log.name}")

    def start_backend(self):
        self.backend = self.start(
            "backend",
            [
                "-m",
                "uvicorn",
                "backend.app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(self.backend_port),
            ],
            self.backend_port,
        )

    def request(self, method, path, who="founder", **kwargs):
        headers = (
            {"Authorization": f"Bearer {self.tokens[who]}"}
            if who in self.tokens
            else {}
        )
        return httpx.request(
            method,
            self.url + path,
            headers=headers,
            timeout=20,
            trust_env=False,
            **kwargs,
        )

    def ok(self, method, path, **kwargs):
        response = self.request(method, path, **kwargs)
        assert response.status_code < 300, (path, response.status_code, response.text)
        return response.json()

    def login(self, who):
        self.tokens[who] = self.ok(
            "POST",
            "/token",
            who=who,
            data={"username": who, "password": self.passwords[who]},
        )["access_token"]

    def close(self):
        for proc in reversed(self.processes):
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
        for log in self.logs:
            log.close()


@pytest.fixture
def stack(tmp_path):
    stack = Stack(tmp_path)
    try:
        stack.start_backend()
        stack.login("founder")
        stack.ok(
            "PUT", "/api/kolibre/settings/auto-wiki-scrape", json={"enabled": False}
        )
        stack.sister = stack.ok(
            "POST",
            "/api/users",
            json={"username": "sister", "password": stack.passwords["sister"]},
        )
        stack.login("sister")
        stack.ok("POST", "/api/kolibre/libraries", json={"name": "shared"})
        stack.ok(
            "PUT",
            "/api/kolibre/libraries/shared/permessi",
            json={"user_id": stack.sister["id"], "can_edit": True, "can_upload": True},
        )
        yield stack
    finally:
        stack.close()


def test_revocation_survives_backend_restart(stack):
    path = "/api/kolibre/books?library=shared"
    assert stack.request("GET", path, who="sister").status_code == 200
    stack.ok(
        "PUT",
        "/api/kolibre/libraries/shared/permessi",
        json={"user_id": stack.sister["id"], "revoca": True},
    )
    assert stack.request("GET", path, who="sister").status_code == 404
    stack.backend.terminate()
    stack.backend.wait(timeout=15)
    stack.start_backend()
    assert stack.request("GET", path, who="sister").status_code == 404


@pytest.mark.asyncio
async def test_native_mcp_sessions_and_live_revocation(stack):
    stack.start("bridge", ["-m", "calibre_mcp.kolibre_bridge"], stack.bridge_port)

    async def reader(who):
        async with Client(stack.mcp_url, auth=stack.tokens[who]) as client:
            assert {tool.name for tool in await client.list_tools()} == TOOLS
            result = await client.call_tool("kolibre_list_libraries")
            assert "shared" in str(result.data)
            assert str(stack.directory) not in str(result.data)
            return result.data

    await asyncio.gather(*(reader(who) for who in ["founder", "sister"] * 3))
    async with Client(stack.mcp_url, auth=stack.tokens["sister"]) as client:
        await client.call_tool("kolibre_list_books", {"library": "shared"})
        stack.ok(
            "PUT",
            "/api/kolibre/libraries/shared/permessi",
            json={"user_id": stack.sister["id"], "revoca": True},
        )
        result = await client.call_tool(
            "kolibre_list_books", {"library": "shared"}, raise_on_error=False
        )
        assert result.is_error
    assert stack.request("GET", "/api/users/me", who="anonymous").status_code == 401


def epub(title, text):
    result = io.BytesIO()
    with zipfile.ZipFile(result, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip")
        archive.writestr(
            "META-INF/container.xml",
            '<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container" version="1.0"><rootfiles><rootfile full-path="content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>',
        )
        archive.writestr(
            "content.opf",
            f'<package xmlns="http://www.idpf.org/2007/opf" version="2.0" unique-identifier="id"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:identifier id="id">{title}</dc:identifier><dc:title>{title}</dc:title><dc:creator>Synthetic Author</dc:creator><dc:language>en</dc:language></metadata><manifest><item id="chapter" href="chapter.xhtml" media-type="application/xhtml+xml"/></manifest><spine><itemref idref="chapter"/></spine></package>',
        )
        archive.writestr(
            "chapter.xhtml",
            f'<html xmlns="http://www.w3.org/1999/xhtml"><head><title>{title}</title></head><body><p>{text}</p></body></html>',
        )
    return result.getvalue()


@pytest.fixture
def populated(stack):
    stack.books = {}
    stack.private = {}
    stack.notes = {}
    for owner, visibility in [
        ("founder", "shared"),
        ("founder", "private"),
        ("sister", "private"),
    ]:
        title = f"{owner} {visibility} book"
        staged = stack.ok(
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
        imported = stack.ok(
            "POST",
            "/api/kolibre/ingest/import-book",
            who=owner,
            json={"id": staged["staged"][0]["id"], "library": "shared", "title": title},
        )
        folder = imported["library"]
        stack.books[folder] = imported["book_id"]
        if visibility == "private":
            assert folder != "shared"  # private staging cannot be redirected to shared
            stack.private[owner] = folder
        stack.ok(
            "PUT",
            f"/api/kolibre/fulltext/settings?library={folder}",
            who=owner,
            json={"enabled": True},
        )
        stack.ok("POST", f"/api/kolibre/fulltext/reindex?library={folder}", who=owner)
        for _ in range(100):
            if stack.ok(
                "GET",
                f"/api/kolibre/fulltext/search?library={folder}&q=quasar",
                who=owner,
            )["results"]:
                break
            time.sleep(0.1)
        else:
            pytest.fail("Full-text indexing did not produce the synthetic passage")
        # Check physical placement, not just returned identifiers.
        assert list((stack.directory / "data/libraries" / folder).rglob("*.epub"))
    for owner in ("founder", "sister"):
        for folder in ("shared", stack.private[owner]):
            stack.notes[owner, folder] = stack.ok(
                "POST",
                "/api/kolibre/annotations",
                who=owner,
                json={
                    "library": folder,
                    "calibre_book_id": stack.books[folder],
                    "text": f"{owner}-secret-note",
                },
            )
    stack.ok("PUT", "/api/kolibre/settings/opds-feed", json={"enabled": True})
    return stack


@pytest.mark.asyncio
async def test_two_users_private_content_fulltext_annotations_and_opds(populated):
    stack = populated
    stack.start("bridge", ["-m", "calibre_mcp.kolibre_bridge"], stack.bridge_port)

    async def reader(who):
        other = "sister" if who == "founder" else "founder"
        async with Client(stack.mcp_url, auth=stack.tokens[who]) as client:
            libraries = await client.call_tool("kolibre_list_libraries")
            assert stack.private[who] in str(libraries.data)
            assert stack.private[other] not in str(libraries.data)
            for folder in ("shared", stack.private[who]):
                books = await client.call_tool(
                    "kolibre_list_books", {"library": folder}
                )
                assert "book" in str(books.data)
                search = await client.call_tool(
                    "kolibre_search_fulltext", {"library": folder, "query": "quasar"}
                )
                assert "quasar" in str(search.data)
            notes = await client.call_tool("kolibre_my_annotations")
            assert f"{who}-secret-note" in str(notes.data)
            assert f"{other}-secret-note" not in str(notes.data)
            for tool in (
                "kolibre_list_books",
                "kolibre_search_fulltext",
                "kolibre_my_annotations",
            ):
                args = {"library": stack.private[other]}
                if tool == "kolibre_search_fulltext":
                    args["query"] = "quasar"
                denied = await client.call_tool(tool, args, raise_on_error=False)
                assert denied.is_error

    await asyncio.gather(*(reader(who) for who in ["founder", "sister"] * 2))
    for who, other in [("founder", "sister"), ("sister", "founder")]:
        for route in ("books", "fulltext/search?q=quasar&"):
            separator = "" if "?" in route else "?"
            path = f"/api/kolibre/{route}{separator}library={stack.private[other]}"
            assert stack.request("GET", path, who=who).status_code == 404
        # This endpoint has no library or user selector: extra query fields
        # must not change its hard-coded authenticated-user scope.
        notes = stack.ok(
            "GET",
            f"/api/kolibre/annotations?library={stack.private[other]}&user_id={stack.sister['id']}",
            who=who,
        )
        assert f"{who}-secret-note" in str(notes)
        assert f"{other}-secret-note" not in str(notes)
        foreign_id = stack.notes[other, "shared"]["id"]
        assert (
            stack.request(
                "PUT",
                f"/api/kolibre/annotations/{foreign_id}",
                who=who,
                json={"text": "unauthorized overwrite"},
            ).status_code
            == 404
        )
        with httpx.Client(
            base_url=stack.url, auth=(who, stack.passwords[who]), trust_env=False
        ) as opds:
            own = opds.get(f"/opds/{stack.private[who]}/all")
            assert own.status_code == 200
            assert f"{who} private book" in own.text
            assert opds.get(f"/opds/{stack.private[other]}/all").status_code == 404


@pytest.mark.asyncio
async def test_native_login_token_expiration_during_mcp_session(stack):
    lab = stack
    lab.backend.terminate()
    lab.backend.wait(timeout=15)
    lab.env["LAB_BACKEND_PORT"] = str(lab.backend_port)
    lab.backend = lab.start(
        "short-token-backend",
        [
            "-c",
            """import os, uvicorn
from backend.app import auth
# Genuine /token issuance with a test-only short TTL.
auth.ACCESS_TOKEN_EXPIRE_MINUTES = .1
uvicorn.run('backend.app.main:app', host='127.0.0.1', port=int(os.environ['LAB_BACKEND_PORT']))
""",
        ],
        lab.backend_port,
    )
    lab.start("bridge", ["-m", "calibre_mcp.kolibre_bridge"], lab.bridge_port)
    lab.login("sister")
    from jose import jwt

    expires = jwt.get_unverified_claims(lab.tokens["sister"])["exp"]
    authenticated = attempted_after_expiry = False
    with pytest.raises(httpx.HTTPStatusError) as denied:
        async with Client(lab.mcp_url, auth=lab.tokens["sister"]) as client:
            await client.call_tool("kolibre_list_libraries")
            authenticated = True
            await asyncio.sleep(max(0, expires - time.time()) + 1)
            attempted_after_expiry = True
            await client.call_tool("kolibre_list_libraries")
    assert authenticated and attempted_after_expiry
    assert denied.value.response.status_code == 401
    assert lab.request("GET", "/api/users/me", who="sister").status_code == 401
