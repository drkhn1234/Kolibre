"""Public HTTPS expiry with actual Inspector and actual provider-issued tokens."""

import json
import subprocess
import time

import httpx
from jose import jwt
from validate import ROOT, Inspector, RemoteLab, keycloak_browser, keycloak_token


def ttl(seconds):
    subprocess.run(
        [
            "ssh",
            "oracle",
            "sudo",
            "/opt/kolibre-stage/current/.venv/bin/python",
            "/opt/kolibre-stage/deployment/set_realm_ttl.py",
            "--seconds",
            str(seconds),
        ],
        capture_output=True,
        text=True,
        check=True,
    )


lab = RemoteLab()
lab.restore()
clients = []
try:
    ttl(120)
    tokens = {who: keycloak_token(lab, who) for who in ("founder", "sister")}
    for who, token in tokens.items():
        response = httpx.get(
            lab.url + "/api/users/me",
            headers={"Authorization": "Bearer " + token},
            trust_env=False,
            timeout=20,
        )
        assert response.status_code == 200 and response.json()["username"] == who
    clients = [Inspector(lab, who) for who in ("founder", "sister")]
    for client in clients:
        client.connect(oauth=True, browser=keycloak_browser)
        client.call("kolibre_my_annotations")
    deadline = time.monotonic() + 121
    while time.monotonic() < deadline:
        time.sleep(min(10, deadline - time.monotonic()))
    for token in tokens.values():
        headers = {"Authorization": "Bearer " + token}
        assert (
            httpx.get(
                lab.url + "/api/users/me", headers=headers, trust_env=False, timeout=20
            ).status_code
            == 401
        )
        assert (
            httpx.get(
                lab.mcp_url, headers=headers, trust_env=False, timeout=20
            ).status_code
            == 401
        )
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
        notes = json.dumps(client.call("kolibre_my_annotations"))
        other = "sister" if client.who == "founder" else "founder"
        assert (
            f"{client.who}-secret-note" in notes and f"{other}-secret-note" not in notes
        )
    credentials = json.loads((ROOT / "runtime/staging-credentials.json").read_text())
    # Extra native server-verification probe. Unlike the OIDC tokens above,
    # this expired token is constructed from the staging signing key, rather
    # than claimed to have expired naturally after HTTP /token issuance.
    expired = jwt.encode(
        {"sub": "sister", "exp": int(time.time()) - 10},
        credentials["native_signing_key"],
        algorithm="HS256",
    )
    for url in (lab.url + "/api/users/me", lab.mcp_url):
        assert (
            httpx.get(
                url,
                headers={"Authorization": "Bearer " + expired},
                trust_env=False,
                timeout=20,
            ).status_code
            == 401
        )
    print(
        "PASS: Real OIDC tokens expired at API/MCP and existing Inspector sessions; both users reauthenticated with isolated notes. Expired signed-native probes also rejected."
    )
finally:
    try:
        ttl(300)
    finally:
        for client in clients:
            client.close()
            (ROOT / "evidence/deployment" / f"expiry-{client.who}.json").write_text(
                (lab.directory / f"inspector-{client.who}.json").read_text()
            )
