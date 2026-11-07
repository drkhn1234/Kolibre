"""Root-only, bounded pre-registration; no changes to anonymous DCR safeguards."""

import argparse
import json
import os
from pathlib import Path

from keycloak_config import REALM, KeycloakAdmin, realm_configuration

CLIENT_ID = "kolibre-chatgpt-stage"
CALLBACK = "https://chatgpt.com/connector_platform_oauth_redirect"


def client_configuration(ttl=300):
    return {
        "clientId": CLIENT_ID,
        "name": "Kolibre staging in ChatGPT",
        "enabled": True,
        "protocol": "openid-connect",
        "publicClient": False,
        "clientAuthenticatorType": "client-secret",
        "standardFlowEnabled": True,
        "implicitFlowEnabled": False,
        "directAccessGrantsEnabled": False,
        "serviceAccountsEnabled": False,
        "consentRequired": True,
        "fullScopeAllowed": False,
        "redirectUris": [CALLBACK],
        "webOrigins": [],
        "defaultClientScopes": ["books:read"],
        # ChatGPT may request OIDC scopes advertised by Keycloak. Offline
        # access requires user consent and still requires books:read.
        "optionalClientScopes": ["offline_access"],
        "attributes": {
            "pkce.code.challenge.method": "S256",
            "use.refresh.tokens": "true",
            "access.token.lifespan": str(ttl),
            "client.offline.session.idle.timeout": "1800",
            "client.offline.session.max.lifespan": "28800",
        },
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--token-seconds", type=int, choices=[120, 300], default=300)
    args = parser.parse_args()
    assert os.geteuid() == 0
    root = Path("/etc/kolibre-stage")
    credentials = json.loads((root / "credentials.json").read_text())
    admin = KeycloakAdmin(
        "http://127.0.0.1:18083/kolibre-auth-stage",
        "kolibre-stage-operator",
        credentials["operator_password"],
    )
    base = f"/admin/realms/{REALM}/clients"
    try:
        response = admin.client.put(
            f"/admin/realms/{REALM}",
            json={
                "offlineSessionMaxLifespanEnabled": True,
                "offlineSessionIdleTimeout": 1800,
                "offlineSessionMaxLifespan": 28800,
            },
        )
        response.raise_for_status()
        response = admin.client.get(base, params={"clientId": CLIENT_ID})
        response.raise_for_status()
        matches = response.json()
        assert len(matches) <= 1
        config = client_configuration(args.token_seconds)
        if matches:
            identifier = matches[0]["id"]
            response = admin.client.get(base + "/" + identifier)
            response.raise_for_status()
            representation = response.json()
            representation.update(config)
            response = admin.client.put(base + "/" + identifier, json=representation)
        else:
            response = admin.client.post(base, json=config)
            identifier = response.headers["location"].rsplit("/", 1)[1]
        response.raise_for_status()
        # Updating ClientRepresentation does not update scope associations
        # in Keycloak. Use the explicit association endpoint on reruns too.
        response = admin.client.get(f"/admin/realms/{REALM}/client-scopes")
        response.raise_for_status()
        realm_scopes = response.json()
        offline = next(s for s in realm_scopes if s["name"] == "offline_access")
        books = next(s for s in realm_scopes if s["name"] == "books:read")
        mapper_url = (
            f"/admin/realms/{REALM}/client-scopes/{books['id']}/protocol-mappers/models"
        )
        response = admin.client.get(mapper_url)
        response.raise_for_status()
        current_mappers = {m["name"]: m for m in response.json()}
        # Keycloak's audience mapper chooses the client value OR custom value,
        # not both. Separate standard mappers preserve the MCP URL audience
        # during offline refresh too; backend audience validation stays strict.
        desired = realm_configuration(
            "https://books.drkhn.site/kolibre-mcp-stage/mcp", {}
        )["clientScopes"][0]["protocolMappers"]
        for mapper in desired:
            existing = current_mappers.get(mapper["name"])
            if existing:
                response = admin.client.put(
                    mapper_url + "/" + existing["id"],
                    json={**mapper, "id": existing["id"]},
                )
            else:
                response = admin.client.post(mapper_url, json=mapper)
            response.raise_for_status()
        response = admin.client.put(
            base + "/" + identifier + "/optional-client-scopes/" + offline["id"]
        )
        response.raise_for_status()
        # This minimal realm imported users without default realm roles.
        # Explicitly permit bounded offline sessions for the two synthetic
        # readers only. This role grants no Kolibre library/admin permission.
        response = admin.client.get(f"/admin/realms/{REALM}/roles/offline_access")
        response.raise_for_status()
        offline_role = response.json()
        for who in ("founder", "sister"):
            response = admin.client.get(
                f"/admin/realms/{REALM}/users",
                params={"username": who, "exact": "true"},
            )
            response.raise_for_status()
            accounts = response.json()
            assert len(accounts) == 1
            response = admin.client.post(
                f"/admin/realms/{REALM}/users/{accounts[0]['id']}/role-mappings/realm",
                json=[offline_role],
            )
            response.raise_for_status()
        response = admin.client.get(base + "/" + identifier + "/client-secret")
        response.raise_for_status()
        # Keep the existing secret on subsequent runs; never print it.
        data = {
            "client_id": CLIENT_ID,
            "client_secret": response.json()["value"],
            "redirect_uri": CALLBACK,
        }
        path = root / "chatgpt-client.json"
        with open(
            os.open(path, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600), "w"
        ) as f:
            json.dump(data, f)
        path.chmod(0o600)
        print(
            f"Configured {CLIENT_ID}: exact ChatGPT callback, S256, consent, books:read, TTL={args.token_seconds}s, optional offline access bounded to 8h/30m idle; secret saved privately"
        )
    finally:
        admin.close()


if __name__ == "__main__":
    main()
