"""OIDC tokens come from an HTTPS provider's real DCR/code/PKCE flow."""

import asyncio
import base64
from datetime import datetime, timedelta, timezone
import hashlib
import ipaddress
import json
import os
import secrets
import ssl
import time
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from fastmcp import Client
from fastmcp.client.auth import OAuth
from fastmcp.client.transports import StreamableHttpTransport
import httpx
from jose import jwk, jwt
import pytest

from test_live_native import ROOT, TOOLS, free_port, populated, stack  # noqa: F401


def private_file(path, data):
    with open(
        os.open(path, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600), "w"
    ) as handle:
        handle.write(data)


def configure_oidc(lab):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    name = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, "Disposable integration CA")]
    )
    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=1))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(
            x509.SubjectAlternativeName(
                [x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]
            ),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )
    cert_path, key_path = lab.directory / "ca.pem", lab.directory / "tls.key"
    private_file(cert_path, cert.public_bytes(serialization.Encoding.PEM).decode())
    private_file(key_path, pem)
    signing_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    lab.signing_pem = signing_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    signing_jwk = jwk.construct(lab.signing_pem, "RS256").to_dict()
    signing_jwk.update(kid="lab-signing", use="sig", alg="RS256")
    jwks_path = lab.directory / "jwks-private.json"
    private_file(jwks_path, json.dumps({"keys": [signing_jwk]}))
    lab.issuer = f"https://127.0.0.1:{free_port()}"
    lab.mcp_url = f"https://127.0.0.1:{lab.bridge_port}/mcp"
    lab.tls = ssl.create_default_context(cafile=cert_path)
    lab.oidc_passwords = {
        name: secrets.token_urlsafe(24) for name in ("founder", "sister", "unlinked")
    }
    lab.env.update(
        LAB_ISSUER=lab.issuer,
        LAB_RESOURCE=lab.mcp_url,
        LAB_ACCOUNTS=json.dumps(lab.oidc_passwords),
        LAB_JWKS=str(jwks_path),
        LAB_TLS_CERT=str(cert_path),
        LAB_TLS_KEY=str(key_path),
        KOLIBRE_OIDC_ISSUER=lab.issuer,
        KOLIBRE_OIDC_AUDIENCE=lab.mcp_url,
        KOLIBRE_OIDC_JWKS_URI=lab.issuer + "/jwks",
        KOLIBRE_OIDC_CA_BUNDLE=str(cert_path),
        KOLIBRE_MCP_OIDC_ISSUER=lab.issuer,
        KOLIBRE_MCP_PUBLIC_URL=lab.mcp_url.removesuffix("/mcp"),
    )
    lab.env["KOLIBRE_MCP_OIDC_SCOPES"] = "openid books:read"
    lab.start(
        "oidc",
        [str(ROOT / "oidc/provider.mjs")],
        int(urlsplit(lab.issuer).port),
        executable="node",
    )
    with pytest.raises(httpx.ConnectError):
        httpx.get(lab.issuer + "/.well-known/openid-configuration", trust_env=False)
    lab.backend.terminate()
    lab.backend.wait(timeout=15)
    lab.start_backend()
    lab.start(
        "bridge",
        [
            "-c",
            """import os, uvicorn
from calibre_mcp.kolibre_bridge.server import create_bridge
uvicorn.run(create_bridge().http_app(path="/mcp"), host="127.0.0.1", port=int(os.environ["KOLIBRE_MCP_PORT"]), ssl_certfile=os.environ["LAB_TLS_CERT"], ssl_keyfile=os.environ["LAB_TLS_KEY"])
""",
        ],
        lab.bridge_port,
    )


def browser_authorize(lab, url, who):
    """Exercise the provider's cookie-bound login and consent UI over HTTPS."""
    with httpx.Client(verify=lab.tls, trust_env=False) as browser:
        for _ in range(20):
            if not url.startswith(lab.issuer + "/"):
                return url
            response = browser.get(url)
            if response.is_redirect:
                url = urljoin(url, response.headers["location"])
                continue
            response.raise_for_status()
            prompt = response.json()["prompt"]
            fields = (
                {"username": who, "password": lab.oidc_passwords[who]}
                if prompt == "login"
                else {"approve": "yes"}
            )
            response = browser.post(url, data=fields, headers={"Origin": lab.issuer})
            assert response.is_redirect, (
                f"Provider interaction failed ({response.status_code})"
            )
            url = urljoin(url, response.headers["location"])
    raise AssertionError("Authorization redirect loop")


def authorize(lab, who, wrong_verifier=False):
    with httpx.Client(verify=lab.tls, trust_env=False) as client:
        discovery = client.get(lab.issuer + "/.well-known/openid-configuration").json()
        assert discovery["issuer"] == lab.issuer
        assert "S256" in discovery["code_challenge_methods_supported"]
        assert "authorization_code" in discovery["grant_types_supported"]
        redirect = "http://127.0.0.1:19876/callback"
        registration = client.post(
            discovery["registration_endpoint"],
            json={
                "redirect_uris": [redirect],
                "response_types": ["code"],
                "grant_types": ["authorization_code"],
                "token_endpoint_auth_method": "none",
            },
        )
        assert registration.status_code == 201
        verifier = secrets.token_urlsafe(48)
        challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
            .rstrip(b"=")
            .decode()
        )
        state = secrets.token_urlsafe(24)
        callback = browser_authorize(
            lab,
            discovery["authorization_endpoint"]
            + "?"
            + urlencode(
                {
                    "client_id": registration.json()["client_id"],
                    "redirect_uri": redirect,
                    "response_type": "code",
                    "scope": "openid books:read",
                    "resource": lab.mcp_url,
                    "state": state,
                    "code_challenge": challenge,
                    "code_challenge_method": "S256",
                }
            ),
            who,
        )
        query = parse_qs(urlsplit(callback).query)
        assert query.get("state") == [state]
        assert "code" in query, "Provider did not issue an authorization code"
        response = client.post(
            discovery["token_endpoint"],
            data={
                "grant_type": "authorization_code",
                "code": query["code"][0],
                "redirect_uri": redirect,
                "client_id": registration.json()["client_id"],
                "code_verifier": secrets.token_urlsafe(48)
                if wrong_verifier
                else verifier,
                "resource": lab.mcp_url,
            },
        )
        if wrong_verifier:
            assert response.status_code == 400
            assert response.json()["error"] == "invalid_grant"
            return None
        assert response.status_code == 200, (
            f"Token exchange failed ({response.status_code})"
        )
        token = response.json()["access_token"]
        claims = jwt.decode(
            token,
            client.get(discovery["jwks_uri"]).json(),
            algorithms=["RS256"],
            audience=lab.mcp_url,
            issuer=lab.issuer,
        )
        assert claims["sub"] == who
        return token


@pytest.fixture
def oidc(populated):
    lab = populated
    configure_oidc(lab)
    lab.oidc_tokens = {}
    for who in ("founder", "sister"):
        token = authorize(lab, who)
        # Signed and correctly addressed is insufficient until explicitly linked.
        response = httpx.get(
            lab.url + "/api/users/me", headers={"Authorization": "Bearer " + token}
        )
        assert response.status_code == 401
        lab.ok(
            "POST",
            "/api/users/me/oidc-link",
            who=who,
            json={"password": lab.passwords[who], "oidc_access_token": token},
        )
        response = httpx.get(
            lab.url + "/api/users/me", headers={"Authorization": "Bearer " + token}
        )
        assert response.status_code == 200
        assert response.json()["username"] == who
        lab.oidc_tokens[who] = token
    return lab


def mcp_client(lab, token):
    def factory(**kwargs):
        return httpx.AsyncClient(verify=lab.tls, trust_env=False, **kwargs)

    return Client(
        StreamableHttpTransport(lab.mcp_url, auth=token, httpx_client_factory=factory)
    )


@pytest.mark.asyncio
async def test_oidc_real_provider_and_isolation(oidc):
    lab = oidc
    authorize(lab, "sister", wrong_verifier=True)

    async def reader(who):
        other = "sister" if who == "founder" else "founder"
        async with mcp_client(lab, lab.oidc_tokens[who]) as client:
            assert {tool.name for tool in await client.list_tools()} == TOOLS
            libraries = await client.call_tool("kolibre_list_libraries")
            assert lab.private[who] in str(libraries.data)
            assert lab.private[other] not in str(libraries.data)
            for folder in ("shared", lab.private[who]):
                assert not (
                    await client.call_tool("kolibre_list_books", {"library": folder})
                ).is_error
                result = await client.call_tool(
                    "kolibre_search_fulltext", {"library": folder, "query": "quasar"}
                )
                assert "quasar" in str(result.data)
            denied = await client.call_tool(
                "kolibre_list_books",
                {"library": lab.private[other]},
                raise_on_error=False,
            )
            assert denied.is_error
            notes = await client.call_tool("kolibre_my_annotations")
            assert f"{who}-secret-note" in str(notes.data)
            assert f"{other}-secret-note" not in str(notes.data)

    await asyncio.gather(*(reader(who) for who in ["founder", "sister"] * 2))
    assert (
        lab.request(
            "POST",
            "/api/users/me/oidc-link",
            who="founder",
            json={
                "password": lab.passwords["founder"],
                "oidc_access_token": lab.oidc_tokens["sister"],
            },
        ).status_code
        == 409
    )
    assert (
        lab.request(
            "POST",
            "/api/users/me/oidc-link",
            who="sister",
            json={
                "password": "incorrect-password",
                "oidc_access_token": lab.oidc_tokens["sister"],
            },
        ).status_code
        == 401
    )
    async with mcp_client(lab, lab.tokens["founder"]) as client:
        assert not (await client.call_tool("kolibre_list_libraries")).is_error
    async with mcp_client(lab, lab.oidc_tokens["sister"]) as client:
        await client.call_tool("kolibre_list_books", {"library": "shared"})
        lab.ok(
            "PUT",
            "/api/kolibre/libraries/shared/permessi",
            json={"user_id": lab.sister["id"], "revoca": True},
        )
        assert (
            await client.call_tool(
                "kolibre_list_books", {"library": "shared"}, raise_on_error=False
            )
        ).is_error


@pytest.mark.asyncio
async def test_oidc_invalid_tokens_and_expiration(oidc):
    lab = oidc
    base = jwt.get_unverified_claims(lab.oidc_tokens["sister"])

    def signed(**changes):
        return jwt.encode(
            {**base, **changes},
            lab.signing_pem,
            algorithm="RS256",
            headers={"kid": "lab-signing"},
        )

    invalid = [
        None,
        "invalid",
        signed(exp=int(time.time()) - 60),
        signed(aud="wrong-audience"),
        signed(iss="https://wrong.example"),
        signed(sub="unlinked"),
        signed(scope="openid"),
        signed(scope="books:read:all"),
        signed(scope=["books:read"]),
        authorize(lab, "unlinked"),
    ]
    for missing in ("aud", "iss", "exp", "sub", "scope"):
        claims = {name: value for name, value in base.items() if name != missing}
        invalid.append(
            jwt.encode(
                claims,
                lab.signing_pem,
                algorithm="RS256",
                headers={"kid": "lab-signing"},
            )
        )
    stranger = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    invalid.append(
        jwt.encode(
            base,
            stranger.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            ),
            algorithm="RS256",
            headers={"kid": "lab-signing"},
        )
    )
    for token in invalid:
        headers = {"Authorization": "Bearer " + token} if token else {}
        assert httpx.get(lab.url + "/api/users/me", headers=headers).status_code == 401
        with httpx.Client(verify=lab.tls, trust_env=False) as client:
            response = client.get(lab.mcp_url, headers=headers)
            assert response.status_code == 401
    expires = int(time.time()) + 5
    authenticated_before_expiry = False
    called_after_expiry = False
    with pytest.raises(httpx.HTTPStatusError) as rejected:
        async with mcp_client(lab, signed(exp=expires)) as client:
            await client.call_tool("kolibre_list_libraries")
            authenticated_before_expiry = True
            await asyncio.sleep(max(0, expires - time.time()) + 1)
            called_after_expiry = True
            await client.call_tool("kolibre_list_libraries")
    assert authenticated_before_expiry and called_after_expiry
    assert rejected.value.response.status_code == 401


@pytest.mark.asyncio
async def test_mcp_oauth_discovery_dcr_pkce(oidc):
    lab = oidc

    def factory(**kwargs):
        return httpx.AsyncClient(verify=lab.tls, trust_env=False, **kwargs)

    class HeadlessOAuth(OAuth):
        # Only replace the user's browser interaction. The real MCP OAuth
        # implementation does discovery, DCR, state/PKCE, exchange and storage.
        async def redirect_handler(self, authorization_url):
            query = parse_qs(urlsplit(authorization_url).query)
            assert query["code_challenge_method"] == ["S256"]
            assert query["resource"] == [lab.mcp_url]
            self.callback_url = await asyncio.to_thread(
                browser_authorize, lab, authorization_url, self.who
            )

        async def callback_handler(self):
            query = parse_qs(urlsplit(self.callback_url).query)
            assert "code" in query
            return query["code"][0], query["state"][0]

    async def login(who):
        oauth = HeadlessOAuth(
            lab.mcp_url,
            scopes=["openid", "books:read"],
            callback_host="127.0.0.1",
            httpx_client_factory=factory,
        )
        oauth.who = who
        async with Client(
            StreamableHttpTransport(
                lab.mcp_url, auth=oauth, httpx_client_factory=factory
            )
        ) as client:
            result = await client.call_tool("kolibre_my_annotations")
            assert f"{who}-secret-note" in str(result.data)
            other = "sister" if who == "founder" else "founder"
            assert f"{other}-secret-note" not in str(result.data)

    await asyncio.gather(login("founder"), login("sister"))
