"""Actual persistent-provider implementation and Caddy prefix compatibility."""

# ruff: noqa: F811 -- pytest fixtures imported by name

import base64
import hashlib
import ipaddress
import json
import secrets
import ssl
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlencode, urlsplit

import httpx
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from jose import jwt
from test_inspector_client import Inspector, matrix, revoke_and_reconnect
from test_live_native import ROOT, free_port, populated, stack  # noqa: F401
from test_live_oidc import private_file

sys.path.insert(0, str(ROOT))
from deployment.client_support import keycloak_browser
from deployment.keycloak_config import REALM, KeycloakAdmin

DIST = ROOT / "runtime/keycloak-download"


def certificate(lab):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, "Local provider compatibility CA")]
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
    private_file(
        lab.directory / "ca.pem", cert.public_bytes(serialization.Encoding.PEM).decode()
    )
    private_file(
        lab.directory / "tls.key",
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ).decode(),
    )
    lab.tls = ssl.create_default_context(cafile=lab.directory / "ca.pem")


def start_keycloak(lab):
    lab.keycloak = lab.start(
        "keycloak",
        [
            "start-dev",
            "--features=resource-indicators",
            "--http-host=127.0.0.1",
            f"--http-port={lab.idp_port}",
            "--http-relative-path=/kolibre-auth-stage",
            f"--hostname={lab.public_origin}/kolibre-auth-stage",
            "--proxy-headers=xforwarded",
            "--proxy-trusted-addresses=127.0.0.1",
        ],
        lab.idp_port,
        executable=str(DIST / "keycloak-26.8.2/bin/kc.sh"),
        startup_timeout=90,
    )
    for _ in range(200):
        response = httpx.get(
            f"http://127.0.0.1:{lab.idp_port}/kolibre-auth-stage/realms/master",
            trust_env=False,
        )
        if response.status_code == 200:
            return
        time.sleep(0.1)
    pytest.fail("Keycloak did not become ready")


def configure_keycloak(lab):
    assert (DIST / "keycloak-26.8.2/bin/kc.sh").is_file(), (
        "Install local provider test distribution first"
    )
    certificate(lab)
    lab.idp_port, lab.proxy_port = free_port(), free_port()
    lab.public_origin = f"https://127.0.0.1:{lab.proxy_port}"
    lab.issuer = lab.public_origin + f"/kolibre-auth-stage/realms/{REALM}"
    lab.mcp_url = lab.public_origin + "/kolibre-mcp-stage/mcp"
    lab.oidc_passwords = {
        who: secrets.token_urlsafe(32) for who in ("founder", "sister", "unlinked")
    }
    lab.admin_password = secrets.token_urlsafe(32)
    lab.env.update(
        JAVA_HOME=str(DIST / "jdk-21.0.13+9"),
        JAVA_OPTS_APPEND="-Xms128m -Xmx768m",
        KC_BOOTSTRAP_ADMIN_USERNAME="stage-bootstrap",
        KC_BOOTSTRAP_ADMIN_PASSWORD=lab.admin_password,
        KC_DB_URL=f"jdbc:h2:file:{lab.directory}/keycloak-db;DB_CLOSE_ON_EXIT=FALSE;NON_KEYWORDS=VALUE",
        KOLIBRE_OIDC_ISSUER=lab.issuer,
        KOLIBRE_OIDC_AUDIENCE=lab.mcp_url,
        KOLIBRE_OIDC_JWKS_URI=lab.issuer + "/protocol/openid-connect/certs",
        KOLIBRE_OIDC_CA_BUNDLE=str(lab.directory / "ca.pem"),
        KOLIBRE_MCP_OIDC_ISSUER=lab.issuer,
        KOLIBRE_MCP_PUBLIC_URL=lab.public_origin + "/kolibre-mcp-stage",
        KOLIBRE_MCP_OIDC_SCOPES="openid books:read",
        KOLIBRE_ACCESS_TOKEN_EXPIRE_MINUTES="15",
    )
    start_keycloak(lab)
    admin = KeycloakAdmin(
        f"http://127.0.0.1:{lab.idp_port}/kolibre-auth-stage",
        "stage-bootstrap",
        lab.admin_password,
    )
    try:
        lab.policy_evidence = admin.configure(
            lab.mcp_url, lab.oidc_passwords, ["localhost", "127.0.0.1"]
        )
        (lab.directory / "keycloak-policy-evidence.json").write_text(
            json.dumps(lab.policy_evidence, indent=2)
        )
        # Short but above Inspector's one-minute usability margin.
        response = admin.client.put(
            f"/admin/realms/{REALM}", json={"accessTokenLifespan": 120}
        )
        response.raise_for_status()
    finally:
        admin.close()
    lab.backend.terminate()
    lab.backend.wait(timeout=15)
    lab.start_backend()
    for who in ("founder", "sister"):
        before = time.time()
        lab.login(who)
        expires = jwt.get_unverified_claims(lab.tokens[who])["exp"]
        assert 898 <= expires - before <= 903
        assert lab.request("GET", "/api/users/me", who=who).status_code == 200
    lab.start("bridge", ["-m", "calibre_mcp.kolibre_bridge"], lab.bridge_port)
    config = lab.directory / "Caddyfile"
    routes = (ROOT / "deployment/caddy.routes").read_text()
    for original, replacement in {
        "18081": str(lab.backend_port),
        "18082": str(lab.bridge_port),
        "18083": str(lab.idp_port),
        "TRUSTED_CLIENT_IP": "127.0.0.1",
    }.items():
        routes = routes.replace(original, replacement)
    config.write_text(f"""{{
    admin off
    auto_https off
}}
{lab.public_origin} {{
    bind 127.0.0.1
    tls {lab.directory}/ca.pem {lab.directory}/tls.key
    log {{
        output file {lab.directory}/proxy-paths.jsonl
        format filter {{
            wrap json
            fields {{
                request>uri regexp "[?].*$" ""
                request>headers delete
                resp_headers delete
            }}
        }}
    }}
    {routes}
    # Simulate the existing BookOrbit catch-all. Stage metadata must outrank it.
    handle /.well-known/oauth-authorization-server* {{
        respond "Unrelated application's metadata" 418
    }}
    handle /.well-known/openid-configuration {{
        respond "Unrelated application's metadata" 418
    }}
}}
""")
    lab.env.update(
        XDG_CONFIG_HOME=str(lab.directory / "caddy-config"),
        XDG_DATA_HOME=str(lab.directory / "caddy-data"),
    )
    lab.start(
        "caddy",
        ["run", "--config", str(config), "--adapter", "caddyfile"],
        lab.proxy_port,
        executable=str(DIST / "caddy"),
    )


def keycloak_token(lab, who):
    with httpx.Client(verify=lab.tls, trust_env=False, timeout=30) as client:
        discovery = client.get(lab.issuer + "/.well-known/openid-configuration").json()
        assert discovery["issuer"] == lab.issuer
        assert "S256" in discovery["code_challenge_methods_supported"]
        redirect = "http://127.0.0.1:19876/callback"
        response = client.post(
            discovery["registration_endpoint"],
            json={
                "redirect_uris": [redirect],
                "response_types": ["code"],
                "grant_types": ["authorization_code"],
                "token_endpoint_auth_method": "none",
                "scope": "openid books:read",
            },
        )
        assert response.status_code == 201, (
            f"DCR failed ({response.status_code}): {response.text[:200]}"
        )
        registration = response.json()
        verifier = secrets.token_urlsafe(48)
        state = secrets.token_urlsafe(24)
        parameters = {
            "client_id": registration["client_id"],
            "redirect_uri": redirect,
            "response_type": "code",
            "scope": "openid books:read",
            "resource": lab.mcp_url,
            "state": state,
            "code_challenge_method": "S256",
            "code_challenge": base64.urlsafe_b64encode(
                hashlib.sha256(verifier.encode()).digest()
            )
            .rstrip(b"=")
            .decode(),
        }
        if not getattr(lab, "registration_negatives_checked", False):
            bad = client.post(
                discovery["registration_endpoint"],
                json={
                    "redirect_uris": ["https://untrusted.invalid/callback"],
                    "grant_types": ["authorization_code"],
                    "response_types": ["code"],
                    "token_endpoint_auth_method": "none",
                    "scope": "openid books:read",
                },
            )
            assert bad.status_code == 403, "Untrusted redirect host must be rejected"
            bad = client.post(
                discovery["registration_endpoint"],
                json={
                    "redirect_uris": [redirect],
                    "grant_types": ["authorization_code"],
                    "response_types": ["code"],
                    "token_endpoint_auth_method": "none",
                    "scope": "openid unauthorized:write",
                },
            )
            assert bad.status_code == 403, "Unapproved scopes must be rejected"
            missing_pkce = {
                key: value
                for key, value in parameters.items()
                if key not in ("code_challenge", "code_challenge_method")
            }
            bad = client.get(discovery["authorization_endpoint"], params=missing_pkce)
            assert bad.status_code == 400 or (
                bad.is_redirect and "error=" in bad.headers["location"]
            ), "Provider must enforce PKCE"
            # Resource checks may occur after login. Prove that an issued
            # code cannot be redeemed for a different, unregistered resource.
            probe = keycloak_browser(
                lab,
                discovery["authorization_endpoint"] + "?" + urlencode(parameters),
                who,
            )
            probe_query = parse_qs(urlsplit(probe).query)
            assert probe_query.get("state") == [state] and "code" in probe_query
            bad = client.post(
                discovery["token_endpoint"],
                data={
                    "grant_type": "authorization_code",
                    "code": probe_query["code"][0],
                    "redirect_uri": redirect,
                    "client_id": registration["client_id"],
                    "code_verifier": verifier,
                    "resource": "https://untrusted.invalid/mcp",
                },
            )
            assert (
                bad.status_code == 400 and bad.json().get("error") == "invalid_target"
            ), "Wrong token resource must be rejected"
            parameters["state"] = secrets.token_urlsafe(24)
            state = parameters["state"]
            lab.registration_negatives_checked = True
        callback = keycloak_browser(
            lab, discovery["authorization_endpoint"] + "?" + urlencode(parameters), who
        )
        query = parse_qs(urlsplit(callback).query)
        assert query.get("state") == [state] and "code" in query
        response = client.post(
            discovery["token_endpoint"],
            data={
                "grant_type": "authorization_code",
                "code": query["code"][0],
                "redirect_uri": redirect,
                "client_id": registration["client_id"],
                "code_verifier": verifier,
                "resource": lab.mcp_url,
            },
        )
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
        assert claims.get("sub") and "books:read" in claims["scope"].split()
        return token


def test_keycloak_real_client_and_persistence(populated):
    lab = populated
    configure_keycloak(lab)
    for who in ("founder", "sister"):
        token = keycloak_token(lab, who)
        assert (
            httpx.get(
                lab.url + "/api/users/me", headers={"Authorization": "Bearer " + token}
            ).status_code
            == 401
        )
        lab.ok(
            "POST",
            "/api/users/me/oidc-link",
            who=who,
            json={"password": lab.passwords[who], "oidc_access_token": token},
        )
    clients = [Inspector(lab, who) for who in ("founder", "sister")]
    try:
        for client in clients:
            client.connect(oauth=True, browser=keycloak_browser)
        issued_before = time.monotonic()
        with ThreadPoolExecutor(max_workers=2) as executor:
            list(executor.map(matrix, clients))
        revoke_and_reconnect(lab, *clients)
        lab.keycloak.terminate()
        lab.keycloak.wait(timeout=20)
        start_keycloak(lab)
        for client in clients:
            client.run("disconnect", client.who)
            client.connect()  # Persisted provider key/client/grant plus Inspector token.
            client.call("kolibre_my_annotations")
        # Verify actual expiry and new code flow with real provider accounts.
        remaining = max(0, 121 - (time.monotonic() - issued_before))
        while remaining:
            time.sleep(min(10, remaining))
            remaining = max(0, 121 - (time.monotonic() - issued_before))
        for client in clients:
            code, result = client.run(
                "--connection",
                client.who,
                "tools/call",
                "kolibre_list_libraries",
                "{}",
                success=False,
            )
            assert code != 0 and ("401" in str(result) or "auth" in str(result).lower())
            client.run("disconnect", client.who, "--clear-auth")
            client.connect(oauth=True, browser=keycloak_browser)
            client.call("kolibre_my_annotations")
        (lab.directory / "keycloak-policy-evidence.json").write_text(
            json.dumps(lab.policy_evidence, indent=2)
        )
    finally:
        for client in clients:
            client.close()
