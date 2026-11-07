"""Update only the approved lab egress address in both DCR safeguards."""

import argparse
import ipaddress
import json
import os
import re
import subprocess
from pathlib import Path

from keycloak_config import POLICY_TYPE, REALM, KeycloakAdmin

parser = argparse.ArgumentParser()
parser.add_argument("--client-ip", required=True)
args = parser.parse_args()
assert ipaddress.ip_address(args.client_ip).is_global and os.geteuid() == 0
root = Path("/etc/kolibre-stage")
secrets = json.loads((root / "credentials.json").read_text())
admin = KeycloakAdmin(
    "http://127.0.0.1:18083/kolibre-auth-stage",
    "kolibre-stage-operator",
    secrets["operator_password"],
)
routes = Path("/etc/caddy/kolibre-stage.routes")
old = routes.read_text()
pattern = r"(@approved_client remote_ip )([^\s]+)"
match = re.search(pattern, old)
assert match and ipaddress.ip_address(match[2]).is_global
base = f"/admin/realms/{REALM}/components"
original_policy = None
try:
    response = admin.client.get(base, params={"type": POLICY_TYPE})
    response.raise_for_status()
    policy = next(
        p
        for p in response.json()
        if p.get("subType") == "anonymous" and p["providerId"] == "trusted-hosts"
    )
    original_policy = json.loads(json.dumps(policy))
    hosts = policy["config"]["trusted-hosts"]
    assert match[2] in hosts
    policy["config"]["trusted-hosts"] = [
        args.client_ip if h == match[2] else h for h in hosts
    ]
    assert policy["config"]["host-sending-registration-request-must-match"] == ["true"]
    assert policy["config"]["client-uris-must-match"] == ["true"]
    routes.write_text(re.sub(pattern, lambda m: m[1] + args.client_ip, old))
    subprocess.run(
        ["caddy", "validate", "--config", "/etc/caddy/Caddyfile"],
        check=True,
        capture_output=True,
    )
    response = admin.client.put(base + "/" + policy["id"], json=policy)
    response.raise_for_status()
    subprocess.run(["systemctl", "reload", "caddy"], check=True)
except BaseException:
    routes.write_text(old)
    if original_policy:
        response = admin.client.put(
            base + "/" + original_policy["id"], json=original_policy
        )
        response.raise_for_status()
    subprocess.run(["systemctl", "reload", "caddy"], check=True)
    raise
finally:
    admin.close()
print(
    json.dumps(
        {
            "previous_test_egress": match[2],
            "approved_test_egress": args.client_ip,
            "registration_safeguards_preserved": True,
        }
    )
)
