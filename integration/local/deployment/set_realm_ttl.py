"""Shorten only the synthetic staging realm during expiry validation."""

import argparse
import json
from pathlib import Path

from keycloak_config import REALM, KeycloakAdmin

parser = argparse.ArgumentParser()
parser.add_argument("--seconds", required=True, type=int)
seconds = parser.parse_args().seconds
assert 120 <= seconds <= 300
credentials = json.loads(Path("/etc/kolibre-stage/credentials.json").read_text())
admin = KeycloakAdmin(
    "http://127.0.0.1:18083/kolibre-auth-stage",
    "kolibre-stage-operator",
    credentials["operator_password"],
)
try:
    response = admin.client.put(
        f"/admin/realms/{REALM}", json={"accessTokenLifespan": seconds}
    )
    response.raise_for_status()
finally:
    admin.close()
print(
    f"Synthetic staging access-token TTL={seconds}s; other realms/registration unchanged"
)
