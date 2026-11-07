"""Persistent Keycloak realm configuration; caller supplies generated secrets."""

import httpx

REALM = "kolibre-stage"
POLICY_TYPE = "org.keycloak.services.clientregistration.policy.ClientRegistrationPolicy"


def realm_configuration(mcp_url, passwords):
    return {
        "realm": REALM,
        "enabled": True,
        "sslRequired": "external",
        "registrationAllowed": False,
        "resetPasswordAllowed": False,
        "bruteForceProtected": True,
        "failureFactor": 5,
        "accessTokenLifespan": 300,
        "ssoSessionIdleTimeout": 1800,
        "ssoSessionMaxLifespan": 28800,
        "defaultSignatureAlgorithm": "RS256",
        "revokeRefreshToken": True,
        "refreshTokenMaxReuse": 0,
        "users": [
            {
                "username": who,
                "enabled": True,
                "firstName": "Synthetic",
                "lastName": who,
                "email": f"{who}@kolibre-stage.invalid",
                "emailVerified": False,
                "credentials": [
                    {"type": "password", "value": password, "temporary": False}
                ],
            }
            for who, password in passwords.items()
        ],
        "clients": [
            {
                "clientId": "kolibre-mcp-resource",
                "enabled": True,
                "protocol": "openid-connect",
                "bearerOnly": True,
                "attributes": {"resource_url": mcp_url},
            }
        ],
        "clientScopes": [
            {
                "name": "books:read",
                "protocol": "openid-connect",
                "attributes": {
                    "include.in.token.scope": "true",
                    "display.on.consent.screen": "true",
                    "consent.screen.text": "Read the Kolibre content permitted to your account",
                },
                "protocolMappers": [
                    {
                        "name": "Stable Keycloak subject",
                        "protocol": "openid-connect",
                        "protocolMapper": "oidc-sub-mapper",
                        "config": {"access.token.claim": "true"},
                    },
                    {
                        "name": "Kolibre MCP audience",
                        "protocol": "openid-connect",
                        "protocolMapper": "oidc-audience-mapper",
                        "consentRequired": False,
                        "config": {
                            "included.custom.audience": mcp_url,
                            "id.token.claim": "false",
                            "access.token.claim": "true",
                        },
                    },
                    {
                        "name": "Kolibre MCP client audience",
                        "protocol": "openid-connect",
                        "protocolMapper": "oidc-audience-mapper",
                        "consentRequired": False,
                        "config": {
                            "included.client.audience": "kolibre-mcp-resource",
                            "id.token.claim": "false",
                            "access.token.claim": "true",
                        },
                    },
                ],
            }
        ],
        "defaultOptionalClientScopes": ["books:read"],
        "clientProfiles": {
            "profiles": [
                {
                    "name": "kolibre-public-client-security",
                    "executors": [
                        {
                            "executor": "pkce-enforcer",
                            "configuration": {"auto-configure": True},
                        },
                        {
                            "executor": "reject-implicit-grant",
                            "configuration": {"auto-configure": True},
                        },
                        {
                            "executor": "reject-ropc-grant",
                            "configuration": {"auto-configure": True},
                        },
                    ],
                }
            ]
        },
        "clientPolicies": {
            "policies": [
                {
                    "name": "kolibre-public-client-security",
                    "enabled": True,
                    "conditions": [
                        {
                            "condition": "client-access-type",
                            "configuration": {"type": ["public"]},
                        }
                    ],
                    "profiles": ["kolibre-public-client-security"],
                }
            ]
        },
    }


class KeycloakAdmin:
    def __init__(self, base_url, username, password, verify=True):
        self.client = httpx.Client(
            base_url=base_url, verify=verify, trust_env=False, timeout=30
        )
        response = self.client.post(
            "/realms/master/protocol/openid-connect/token",
            data={
                "client_id": "admin-cli",
                "grant_type": "password",
                "username": username,
                "password": password,
            },
        )
        response.raise_for_status()
        self.client.headers["Authorization"] = (
            "Bearer " + response.json()["access_token"]
        )

    def close(self):
        self.client.close()

    def configure(self, mcp_url, passwords, trusted_hosts):
        response = self.client.post(
            "/admin/realms", json=realm_configuration(mcp_url, passwords)
        )
        response.raise_for_status()  # Refuse to overwrite an existing realm.
        base = f"/admin/realms/{REALM}"
        response = self.client.get(base + "/components", params={"type": POLICY_TYPE})
        response.raise_for_status()
        policies = response.json()
        changed = []
        for policy in policies:
            if policy.get("subType") != "anonymous":
                continue
            config = policy.setdefault("config", {})
            provider = policy["providerId"]
            if provider == "trusted-hosts":
                config.update(
                    {
                        # Inspector supplies its official project URI during DCR.
                        # Caddy separately restricts DCR request sources in stage.
                        "trusted-hosts": list(trusted_hosts) + ["github.com"],
                        "host-sending-registration-request-must-match": ["true"],
                        "client-uris-must-match": ["true"],
                    }
                )
            elif provider == "max-clients":
                config["max-clients"] = ["24"]
            elif provider == "allowed-client-templates":
                config["allowed-client-scopes"] = ["openid", "books:read"]
                config["allow-default-scopes"] = ["true"]
            else:
                continue  # Keep consent, mapper, full-scope and origin safeguards.
            updated = self.client.put(base + "/components/" + policy["id"], json=policy)
            updated.raise_for_status()
            changed.append(provider)
        assert "trusted-hosts" in changed and "max-clients" in changed, changed
        return {
            "realm": REALM,
            "policies": [
                {
                    "provider": p["providerId"],
                    "subtype": p.get("subType"),
                    "config": p.get("config", {}),
                }
                for p in policies
            ],
        }
