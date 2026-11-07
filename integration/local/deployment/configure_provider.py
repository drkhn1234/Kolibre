"""Initialize only the dedicated staging realm and replace its bootstrap admin."""

import argparse
import ipaddress
import json
import os
from pathlib import Path

from keycloak_config import REALM, KeycloakAdmin

parser = argparse.ArgumentParser()
parser.add_argument("--client-ip", required=True)
args = parser.parse_args()
ipaddress.ip_address(args.client_ip)
assert os.geteuid() == 0
root = Path("/etc/kolibre-stage")
credentials = json.loads((root / "credentials.json").read_text())
base_url = "http://127.0.0.1:18083/kolibre-auth-stage"
operator = "kolibre-stage-operator"
with_admin = KeycloakAdmin(
    base_url, "stage-bootstrap", credentials["bootstrap_password"]
)
try:
    evidence = with_admin.configure(
        "https://books.drkhn.site/kolibre-mcp-stage/mcp",
        credentials["oidc_passwords"],
        ["localhost", "127.0.0.1", args.client_ip],
    )
    response = with_admin.client.post(
        "/admin/realms/master/users",
        json={
            "username": operator,
            "enabled": True,
            "firstName": "Stage",
            "lastName": "Operator",
            "email": "operator@kolibre-stage.invalid",
            "credentials": [
                {
                    "type": "password",
                    "value": credentials["operator_password"],
                    "temporary": False,
                }
            ],
        },
    )
    response.raise_for_status()
    identifier = response.headers["location"].rsplit("/", 1)[1]
    role = with_admin.client.get("/admin/realms/master/roles/admin")
    role.raise_for_status()
    response = with_admin.client.post(
        f"/admin/realms/master/users/{identifier}/role-mappings/realm",
        json=[role.json()],
    )
    response.raise_for_status()
finally:
    with_admin.close()
admin = KeycloakAdmin(base_url, operator, credentials["operator_password"])
try:
    response = admin.client.get(f"/admin/realms/{REALM}")
    response.raise_for_status()
    bootstrap = admin.client.get(
        "/admin/realms/master/users",
        params={"username": "stage-bootstrap", "exact": "true"},
    )
    bootstrap.raise_for_status()
    for account in bootstrap.json():
        response = admin.client.delete("/admin/realms/master/users/" + account["id"])
        response.raise_for_status()
finally:
    admin.close()
path = root / "provider-policy.json"
path.write_text(json.dumps(evidence, indent=2) + "\n")
path.chmod(0o600)
environment = root / "keycloak.env"
environment.write_text(
    "\n".join(
        line
        for line in environment.read_text().splitlines()
        if not line.startswith("KC_BOOTSTRAP_ADMIN_")
    )
    + "\n"
)
environment.chmod(0o600)
print(
    "Persistent realm configured; permanent operator verified; bootstrap user removed. No secrets printed."
)
