"""Verify the predefined ChatGPT client's protocol contract, not the ChatGPT UI.

Intercept the synthetic login's redirect locally without delivering its code to
ChatGPT. Tokens stay in memory/private Inspector profiles; output contains no
codes, passwords, client secrets or JWTs. Use a 120s client TTL for this probe,
then restore 300s with configure_chatgpt.py in a shell finally/trap.
"""

import base64
import hashlib
import json
import secrets
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import parse_qs, urlencode, urlsplit

import httpx
from jose import jwt
from validate import (
    ROOT,
    Inspector,
    RemoteLab,
    keycloak_browser,
    matrix,
    revoke_and_reconnect,
)


def main():
    lab = RemoteLab()
    lab.restore()
    path = ROOT / "runtime/chatgpt-client.json"
    assert path.stat().st_mode & 0o077 == 0
    config = json.loads(path.read_text())
    with httpx.Client(trust_env=False, timeout=30) as http:
        metadata = http.get(lab.issuer + "/.well-known/openid-configuration").json()
        assert metadata["issuer"] == lab.issuer
        assert metadata["authorization_response_iss_parameter_supported"] is True
        assert "S256" in metadata["code_challenge_methods_supported"]
        jwks = http.get(metadata["jwks_uri"]).json()

        def claims(token):
            key = next(
                k
                for k in jwks["keys"]
                if k["kid"] == jwt.get_unverified_header(token)["kid"]
            )
            result = jwt.decode(
                token,
                key,
                algorithms=["RS256"],
                issuer=lab.issuer,
                audience=lab.mcp_url,
            )
            assert "books:read" in result["scope"].split() and result["sub"]
            return result

        def authorize(
            who,
            *,
            challenge=True,
            bad_redirect=False,
            bad_verifier=False,
            bad_secret=False,
        ):
            verifier, state = secrets.token_urlsafe(48), secrets.token_urlsafe(24)
            parameters = {
                "client_id": config["client_id"],
                "redirect_uri": config["redirect_uri"]
                + ("/unapproved" if bad_redirect else ""),
                "response_type": "code",
                "scope": "openid books:read",
                "resource": lab.mcp_url,
                "state": state,
            }
            if challenge:
                parameters.update(
                    code_challenge_method="S256",
                    code_challenge=base64.urlsafe_b64encode(
                        hashlib.sha256(verifier.encode()).digest()
                    )
                    .rstrip(b"=")
                    .decode(),
                )
            url = metadata["authorization_endpoint"] + "?" + urlencode(parameters)
            if not challenge or bad_redirect:
                response = http.get(url)
                assert response.status_code == 400 or (
                    response.is_redirect and "error=" in response.headers["location"]
                )
                return
            callback = keycloak_browser(lab, url, who)
            assert callback.startswith(config["redirect_uri"] + "?")
            query = parse_qs(urlsplit(callback).query)
            assert query["state"] == [state] and query["iss"] == [lab.issuer]
            response = http.post(
                metadata["token_endpoint"],
                data={
                    "grant_type": "authorization_code",
                    "code": query["code"][0],
                    "redirect_uri": config["redirect_uri"],
                    "client_id": config["client_id"],
                    "client_secret": "incorrect"
                    if bad_secret
                    else config["client_secret"],
                    "code_verifier": secrets.token_urlsafe(48)
                    if bad_verifier
                    else verifier,
                    "resource": lab.mcp_url,
                },
            )
            if bad_secret or bad_verifier:
                assert response.status_code in (400, 401)
                assert "access_token" not in response.json()
                assert response.json()["error"] in (
                    "invalid_client",
                    "invalid_grant",
                    "unauthorized_client",
                ), {
                    "status": response.status_code,
                    "error": response.json().get("error"),
                }
                return
            assert response.status_code == 200
            result = response.json()
            claims(result["access_token"])
            assert result.get("refresh_token") and result.get("id_token")
            return result

        for kwargs in (
            {"challenge": False},
            {"bad_redirect": True},
            {"bad_verifier": True},
            {"bad_secret": True},
        ):
            authorize("sister", **kwargs)
        tokens = {who: authorize(who) for who in ("founder", "sister")}
        identities = {
            who: claims(data["access_token"])["sub"] for who, data in tokens.items()
        }
        assert len(set(identities.values())) == 2
        for who in tokens:
            lab.login(who)
        lab.progress()
        clients = [Inspector(lab, who, tokens[who]["access_token"]) for who in tokens]
        try:
            for client in clients:
                client.connect()
                _, tools = client.run("--connection", client.who, "tools/list")
                for tool in tools["tools"]:
                    assert tool["annotations"]["readOnlyHint"] is True
                    assert tool["_meta"]["securitySchemes"] == [
                        {"type": "oauth2", "scopes": ["books:read"]}
                    ]
            with ThreadPoolExecutor(max_workers=2) as pool:
                list(pool.map(matrix, clients))
            revoke_and_reconnect(lab, *clients)
            deadline = (
                max(claims(data["access_token"])["exp"] for data in tokens.values()) + 1
            )
            assert deadline - time.time() <= 122, (
                "Configure this client to 120s for expiry validation"
            )
            while time.time() < deadline:
                time.sleep(max(0.01, min(5, deadline - time.time())))
            for client in clients:
                who = client.who
                headers = {"Authorization": "Bearer " + tokens[who]["access_token"]}
                assert (
                    http.get(lab.url + "/api/users/me", headers=headers).status_code
                    == 401
                )
                assert http.get(lab.mcp_url, headers=headers).status_code == 401
                code, result = client.run(
                    "--connection",
                    who,
                    "tools/call",
                    "kolibre_list_libraries",
                    "{}",
                    success=False,
                )
                assert code != 0 and (
                    "401" in str(result) or "auth" in str(result).lower()
                )
                refreshed = http.post(
                    metadata["token_endpoint"],
                    data={
                        "grant_type": "refresh_token",
                        "refresh_token": tokens[who]["refresh_token"],
                        "client_id": config["client_id"],
                        "client_secret": config["client_secret"],
                        "resource": lab.mcp_url,
                    },
                )
                assert refreshed.status_code == 200
                fresh = refreshed.json()
                assert claims(fresh["access_token"])["sub"] == identities[who]
                assert fresh["refresh_token"] != tokens[who]["refresh_token"]
                client.run("disconnect", who, "--clear-auth")
                client.write_config(fresh["access_token"])
                client.connect()
                matrix(client)
                replay = http.post(
                    metadata["token_endpoint"],
                    data={
                        "grant_type": "refresh_token",
                        "refresh_token": tokens[who]["refresh_token"],
                        "client_id": config["client_id"],
                        "client_secret": config["client_secret"],
                        "resource": lab.mcp_url,
                    },
                )
                assert (
                    replay.status_code == 400
                    and replay.json()["error"] == "invalid_grant"
                )
                again = authorize(who)
                assert claims(again["access_token"])["sub"] == identities[who]
                client.run("disconnect", who, "--clear-auth")
                client.write_config(again["access_token"])
                client.connect()
                matrix(client)
            print(
                "PASS: predefined ChatGPT client: exact redirect/issuer, S256, bad verifier/secret/redirect rejected; signed resource tokens map two users; actual Inspector initialization/four read-only tools/concurrent privacy/revocation/reconnect; real token expiry; refresh rotation/replay rejection and fresh code reauthentication preserve identities. ChatGPT UI NOT tested."
            )
        finally:
            for client in clients:
                client.close()
                (
                    ROOT / "evidence/deployment" / f"chatgpt-protocol-{client.who}.json"
                ).write_text(
                    (lab.directory / f"inspector-{client.who}.json").read_text()
                )


if __name__ == "__main__":
    main()
