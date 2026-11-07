"""Exercise the shipped MCP Inspector binary, never a custom MCP client.

Only synthetic provider login/consent is driven by the harness. Inspector owns
discovery, DCR, state, PKCE, callback listener, exchange, and MCP transport.
"""

# ruff: noqa: F811 -- imported pytest fixtures are injected by name

import json
import os
import re
import secrets
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from jose import jwt
from test_live_native import ROOT, TOOLS, free_port, populated, stack  # noqa: F401
from test_live_oidc import authorize, browser_authorize, configure_oidc

CLIENT = ROOT / "clients/inspector/node_modules"
NODE = CLIENT / "node/bin/node"
MCPDO = CLIENT / "@modelcontextprotocol/inspector/clients/mcpdo/build/mcp-bin.js"


def scrub(value):
    """Keep useful evidence without OAuth codes, states, tokens or credentials."""
    if isinstance(value, dict):
        return {
            key: (
                "[redacted]"
                if re.search(
                    r"token|secret|password|authorization|authUrl|state|code_verifier",
                    key,
                    re.IGNORECASE,
                )
                else scrub(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [scrub(item) for item in value]
    if isinstance(value, str):
        value = re.sub(
            r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+",
            "[JWT redacted]",
            value,
        )
        return re.sub(r"https?://[^\s\"<>]+\?[^\s\"<>]+", "[URL query redacted]", value)
    return value


class Inspector:
    def __init__(self, lab, who, token=None):
        assert NODE.is_file() and MCPDO.is_file(), (
            "Run ./client-test.sh to install the pinned Inspector"
        )
        self.lab, self.who = lab, who
        self.scratch = tempfile.TemporaryDirectory(prefix="ki-", dir="/tmp")
        self.directory = Path(self.scratch.name)
        self.evidence = []
        self.env = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith(("MCP_", "NODE_"))
            and key.lower()
            not in ("http_proxy", "https_proxy", "all_proxy", "no_proxy")
        }
        self.env.update(
            PATH=str(NODE.parent) + os.pathsep + os.environ["PATH"],
            MCP_STORAGE_DIR=str(self.directory),
            MCP_INSPECTOR_OAUTH_STATE_PATH=str(self.directory / "oauth.json"),
            MCP_INSPECTOR_SECRET_STORE="file",
            MCP_INSPECTOR_SECRET_FILE=str(self.directory / "secrets.json"),
            MCP_INSPECTOR_SECRET_KEY=secrets.token_urlsafe(32),
            MCP_INSPECTOR_DAEMON_DIR=str(self.directory / "daemon"),
            MCP_CLIENT_CONFIG_PATH=str(self.directory / "client.json"),
            MCP_OAUTH_CALLBACK_URL=f"http://127.0.0.1:{free_port()}/oauth/callback",
            MCP_AUTO_OPEN_ENABLED="false",
            NO_COLOR="1",
        )
        if lab.mcp_url.startswith("https:") and (lab.directory / "ca.pem").is_file():
            self.env["NODE_EXTRA_CA_CERTS"] = str(lab.directory / "ca.pem")
        self.config = self.directory / "session.json"
        self.write_config(token)

    def write_config(self, token=None):
        config = {
            "type": "streamable-http",
            "url": self.lab.mcp_url,
            "oauth": {"scope": "openid books:read", "requestRefreshToken": False},
        }
        if token:
            config["headers"] = {"Authorization": "Bearer " + token}
        # The secret goes through a private file, never process arguments.
        with open(
            os.open(self.config, os.O_CREAT | os.O_TRUNC | os.O_WRONLY, 0o600), "w"
        ) as handle:
            json.dump({"mcpServers": {self.who: config}}, handle)

    def run(self, *args, success=True):
        command = [
            str(NODE),
            str(MCPDO),
            "--format",
            "json",
            "--config",
            str(self.config),
            *args,
        ]
        completed = subprocess.run(
            command,
            env=self.env,
            cwd=self.directory,
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
            timeout=45,
            check=False,
        )
        try:
            data = json.loads(completed.stdout)
        except ValueError:
            data = {"stdout": completed.stdout, "stderr": completed.stderr}
        self.evidence.append(
            {
                "command": list(args),
                "exit": completed.returncode,
                "result": scrub(data),
                "stderr": scrub(completed.stderr),
            }
        )
        if success:
            assert completed.returncode == 0, scrub(data)
        return completed.returncode, data

    def connect(self, oauth=False, browser=browser_authorize):
        _, result = self.run("connect", self.who)
        if oauth:
            assert result.get("pendingAuth") is True, scrub(result)
            auth_url = result["authUrl"]
            query = parse_qs(urlsplit(auth_url).query)
            assert query["code_challenge_method"] == ["S256"]
            assert query["resource"] == [self.lab.mcp_url]
            callback = browser(self.lab, auth_url, self.who)
            assert callback.startswith(self.env["MCP_OAUTH_CALLBACK_URL"] + "?")
            # Deliver to Inspector's real loopback callback; it validates state
            # and performs exchange. No harness token injection here.
            response = httpx.get(callback, trust_env=False, timeout=20)
            assert response.status_code == 200
            self.evidence.append(
                {
                    "oauth": {
                        "pkce": "S256",
                        "resource_matches": True,
                        "loopback_callback_delivered": True,
                    }
                }
            )
        else:
            assert not result.get("pendingAuth"), scrub(result)
        for _ in range(30):
            _, shown = self.run("connections/show", self.who)
            if not shown.get("pendingAuth"):
                break
            time.sleep(0.1)
        else:
            pytest.fail("Inspector did not finish sign-in")
        assert "Kolibre" in str(shown), scrub(shown)
        assert shown["protocolVersion"] == "2025-11-25", scrub(shown)
        assert shown["transport"] == "live", scrub(shown)
        return shown

    def call(self, tool, arguments=None, denied=False):
        code, data = self.run(
            "--connection",
            self.who,
            "tools/call",
            tool,
            json.dumps(arguments or {}),
            success=not denied,
        )
        if denied:
            assert code != 0 and data.get("isError") is True, scrub(data)
            assert "Library not found" in str(data), scrub(data)
        else:
            assert not data.get("isError"), scrub(data)
        return data

    def close(self):
        try:
            self.run("daemon", "stop", success=False)
        finally:
            destination = self.lab.directory / f"inspector-{self.who}.json"
            destination.write_text(json.dumps(self.evidence, indent=2))
            archive = ROOT / "evidence/inspector"
            archive.mkdir(parents=True, exist_ok=True)
            (archive / f"{self.lab.directory.name}-{self.who}.json").write_text(
                destination.read_text()
            )
            self.scratch.cleanup()


def matrix(client):
    lab, who = client.lab, client.who
    other = "sister" if who == "founder" else "founder"
    _, discovered = client.run("--connection", who, "tools/list")
    assert {tool["name"] for tool in discovered["tools"]} == TOOLS
    libraries = json.dumps(client.call("kolibre_list_libraries"))
    assert lab.private[who] in libraries and lab.private[other] not in libraries
    for folder in ("shared", lab.private[who]):
        books = json.dumps(client.call("kolibre_list_books", {"library": folder}))
        assert "book" in books
        result = client.call(
            "kolibre_search_fulltext", {"library": folder, "query": "quasar"}
        )
        assert "quasar" in json.dumps(result)
    notes = json.dumps(client.call("kolibre_my_annotations"))
    assert f"{who}-secret-note" in notes and f"{other}-secret-note" not in notes
    for tool in (
        "kolibre_list_books",
        "kolibre_search_fulltext",
        "kolibre_my_annotations",
    ):
        arguments = {"library": lab.private[other]}
        if tool == "kolibre_search_fulltext":
            arguments["query"] = "quasar"
        denied = client.call(tool, arguments, denied=True)
        assert f"{other}-secret-note" not in json.dumps(denied)
        assert f"{other} private book" not in json.dumps(denied)


def revoke_and_reconnect(lab, founder, sister):
    lab.ok(
        "PUT",
        "/api/kolibre/libraries/shared/permessi",
        json={"user_id": lab.sister["id"], "revoca": True},
    )
    sister.call("kolibre_list_books", {"library": "shared"}, denied=True)
    sister.call(
        "kolibre_search_fulltext", {"library": "shared", "query": "quasar"}, denied=True
    )
    sister.call("kolibre_my_annotations", {"library": "shared"}, denied=True)
    assert "shared" not in json.dumps(sister.call("kolibre_list_libraries"))
    assert "founder shared book" in json.dumps(
        founder.call("kolibre_list_books", {"library": "shared"})
    )
    sister.run("disconnect", "sister")
    sister.connect()  # native header or Inspector's own persisted OAuth tokens
    sister.call("kolibre_list_books", {"library": "shared"}, denied=True)
    assert "sister private book" in json.dumps(
        sister.call("kolibre_list_books", {"library": lab.private["sister"]})
    )
    lab.ok(
        "PUT",
        "/api/kolibre/libraries/shared/permessi",
        json={"user_id": lab.sister["id"], "can_edit": True, "can_upload": True},
    )
    assert "founder shared book" in json.dumps(
        sister.call("kolibre_list_books", {"library": "shared"})
    )


def test_inspector_native_two_sessions_revocation_and_reconnect(populated):
    lab = populated
    lab.start("bridge", ["-m", "calibre_mcp.kolibre_bridge"], lab.bridge_port)
    clients = [Inspector(lab, who, lab.tokens[who]) for who in ("founder", "sister")]
    try:
        for client in clients:
            client.connect()
        with ThreadPoolExecutor(max_workers=2) as executor:
            list(executor.map(matrix, clients))
        revoke_and_reconnect(lab, *clients)
    finally:
        for client in clients:
            client.close()


def test_inspector_native_expiry_requires_fresh_login(stack):
    lab = stack
    lab.backend.terminate()
    lab.backend.wait(timeout=15)
    lab.env["LAB_BACKEND_PORT"] = str(lab.backend_port)
    lab.backend = lab.start(
        "short-native",
        [
            "-c",
            """import os, uvicorn
from backend.app import auth
auth.ACCESS_TOKEN_EXPIRE_MINUTES = .2
uvicorn.run('backend.app.main:app', host='127.0.0.1', port=int(os.environ['LAB_BACKEND_PORT']))
""",
        ],
        lab.backend_port,
    )
    lab.start("bridge", ["-m", "calibre_mcp.kolibre_bridge"], lab.bridge_port)
    lab.login("sister")
    expires = jwt.get_unverified_claims(lab.tokens["sister"])["exp"]
    client = Inspector(lab, "sister", lab.tokens["sister"])
    try:
        client.connect()
        client.call("kolibre_list_libraries")
        time.sleep(max(0, expires - time.time()) + 1)
        code, data = client.run(
            "--connection",
            "sister",
            "tools/call",
            "kolibre_list_libraries",
            "{}",
            success=False,
        )
        assert code != 0 and ("401" in str(data) or "auth" in str(data).lower()), scrub(
            data
        )
        client.run("disconnect", "sister")
        code, _ = client.run("--stored-auth-only", "connect", "sister", success=False)
        assert code != 0
        lab.login("sister")
        client.write_config(lab.tokens["sister"])
        client.connect()
        client.call("kolibre_list_libraries")
    finally:
        client.close()


def test_inspector_oidc_dcr_pkce_isolation_expiry_and_relogin(populated):
    lab = populated
    # Inspector treats JWTs within 60s of expiry as expired. Leave a full
    # minute for useful calls before testing rejection at actual expiration.
    lab.env["LAB_ACCESS_TOKEN_TTL"] = "120"
    configure_oidc(lab)
    for who in ("founder", "sister"):
        token = authorize(lab, who)
        lab.ok(
            "POST",
            "/api/users/me/oidc-link",
            who=who,
            json={"password": lab.passwords[who], "oidc_access_token": token},
        )
    clients = [Inspector(lab, who) for who in ("founder", "sister")]
    try:
        for client in clients:
            client.connect(oauth=True)
        issued_before = time.monotonic()
        with ThreadPoolExecutor(max_workers=2) as executor:
            list(executor.map(matrix, clients))
        revoke_and_reconnect(lab, *clients)
        remaining = max(0, 121 - (time.monotonic() - issued_before))
        while remaining > 0:
            time.sleep(min(remaining, 10))
            remaining = max(0, 121 - (time.monotonic() - issued_before))
        for client in clients:
            code, data = client.run(
                "--connection",
                client.who,
                "tools/call",
                "kolibre_list_libraries",
                "{}",
                success=False,
            )
            assert code != 0 and ("401" in str(data) or "auth" in str(data).lower()), (
                scrub(data)
            )
            client.run("disconnect", client.who, "--clear-auth")
            client.connect(oauth=True)
            notes = json.dumps(client.call("kolibre_my_annotations"))
            other = "sister" if client.who == "founder" else "founder"
            assert (
                f"{client.who}-secret-note" in notes
                and f"{other}-secret-note" not in notes
            )
    finally:
        for client in clients:
            client.close()
