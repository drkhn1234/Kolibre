"""Verify advertised offline scope, bounded refresh and user isolation."""

import argparse
import base64
import hashlib
import json
import secrets
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import parse_qs, urlencode, urlsplit

import httpx
from validate import ROOT, Inspector, RemoteLab, keycloak_browser, matrix


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scope", choices=["basic", "offline"], default="offline")
    mode = parser.parse_args().scope
    requested_scope = "openid books:read" + (
        " offline_access" if mode == "offline" else ""
    )
    lab = RemoteLab()
    lab.restore()
    config = json.loads((ROOT / "runtime/chatgpt-client.json").read_text())
    clients = []
    with httpx.Client(trust_env=False, timeout=30) as http:
        metadata = http.get(lab.issuer + "/.well-known/openid-configuration").json()
        fresh_tokens = {}
        try:
            for who in ("founder", "sister"):
                verifier, state = secrets.token_urlsafe(48), secrets.token_urlsafe(24)
                parameters = {
                    "client_id": config["client_id"],
                    "redirect_uri": config["redirect_uri"],
                    "response_type": "code",
                    "scope": requested_scope,
                    "resource": lab.mcp_url,
                    "state": state,
                    "code_challenge_method": "S256",
                    "code_challenge": base64.urlsafe_b64encode(
                        hashlib.sha256(verifier.encode()).digest()
                    )
                    .rstrip(b"=")
                    .decode(),
                }
                callback = keycloak_browser(
                    lab,
                    metadata["authorization_endpoint"] + "?" + urlencode(parameters),
                    who,
                )
                query = parse_qs(urlsplit(callback).query)
                assert "error" not in query, {"error": query.get("error")}
                assert query["state"] == [state] and query["iss"] == [lab.issuer]
                response = http.post(
                    metadata["token_endpoint"],
                    data={
                        "grant_type": "authorization_code",
                        "code": query["code"][0],
                        "redirect_uri": config["redirect_uri"],
                        "client_id": config["client_id"],
                        "client_secret": config["client_secret"],
                        "code_verifier": verifier,
                        "resource": lab.mcp_url,
                    },
                )
                assert response.status_code == 200
                tokens = response.json()
                assert set(requested_scope.split()) <= set(tokens["scope"].split())
                assert 0 < tokens["refresh_expires_in"] <= 28800
                response = http.post(
                    metadata["token_endpoint"],
                    data={
                        "grant_type": "refresh_token",
                        "refresh_token": tokens["refresh_token"],
                        "client_id": config["client_id"],
                        "client_secret": config["client_secret"],
                        "resource": lab.mcp_url,
                    },
                )
                assert response.status_code == 200
                fresh = response.json()
                assert fresh["refresh_token"] != tokens["refresh_token"]
                assert 0 < fresh["refresh_expires_in"] <= 28800
                fresh_tokens[who] = fresh
                account = http.get(
                    lab.url + "/api/users/me",
                    headers={"Authorization": "Bearer " + fresh["access_token"]},
                )
                if account.status_code != 200:
                    from jose import jwt

                    # Diagnostic only; unverified claims never authorize access.
                    diagnostic = jwt.get_unverified_claims(fresh["access_token"])
                    raise AssertionError(
                        {
                            "status": account.status_code,
                            "audience": diagnostic.get("aud"),
                            "scope": diagnostic.get("scope"),
                            "has_subject": bool(diagnostic.get("sub")),
                        }
                    )
                assert account.json()["username"] == who
                client = Inspector(lab, who, fresh["access_token"])
                clients.append(client)
                client.connect()
            with ThreadPoolExecutor(max_workers=2) as pool:
                list(pool.map(matrix, clients))
            for who, tokens in fresh_tokens.items():
                response = http.post(
                    metadata["revocation_endpoint"],
                    data={
                        "client_id": config["client_id"],
                        "client_secret": config["client_secret"],
                        "token": tokens["refresh_token"],
                        "token_type_hint": "refresh_token",
                    },
                )
                assert response.status_code == 200
                response = http.post(
                    metadata["token_endpoint"],
                    data={
                        "grant_type": "refresh_token",
                        "refresh_token": tokens["refresh_token"],
                        "client_id": config["client_id"],
                        "client_secret": config["client_secret"],
                    },
                )
                assert (
                    response.status_code == 400
                    and response.json()["error"] == "invalid_grant"
                )
            print(
                f"PASS: {requested_scope} accepted for both users; refresh expires_in <=8h, rotates, maps correct accounts and retains concurrent MCP private isolation; revoked refresh tokens rejected. No ChatGPT UI test."
            )
        finally:
            for client in clients:
                client.close()
                (
                    ROOT / "evidence/deployment" / f"{mode}-refresh-{client.who}.json"
                ).write_text(
                    (lab.directory / f"inspector-{client.who}.json").read_text()
                )


if __name__ == "__main__":
    main()
