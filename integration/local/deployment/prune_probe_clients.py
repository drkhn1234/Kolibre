"""Remove only the disposable fixed-loopback clients created by keycloak_token.

No Inspector client, predefined ChatGPT client, account or identity link matches
this filter. Repeated verification must not exhaust the guarded DCR quota.
"""

import hashlib
import json
import os
import re
from pathlib import Path

from keycloak_config import REALM, KeycloakAdmin

assert os.geteuid() == 0
secrets = json.loads(Path("/etc/kolibre-stage/credentials.json").read_text())
admin = KeycloakAdmin(
    "http://127.0.0.1:18083/kolibre-auth-stage",
    "kolibre-stage-operator",
    secrets["operator_password"],
)
base = f"/admin/realms/{REALM}/clients"
try:
    response = admin.client.get(base)
    response.raise_for_status()
    removed = []
    for client in response.json():
        if (
            client.get("publicClient") is True
            and not client.get("name")
            and re.fullmatch(r"[a-f0-9-]{36}", client["clientId"])
            and client.get("redirectUris") == ["http://127.0.0.1:19876/callback"]
        ):
            response = admin.client.delete(base + "/" + client["id"])
            response.raise_for_status()
            removed.append(hashlib.sha256(client["clientId"].encode()).hexdigest())
    print(json.dumps({"deleted_fixed_loopback_test_client_hashes": removed}))
finally:
    admin.close()
