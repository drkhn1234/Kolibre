"""Genuine deployed native-token expiry, temporarily using a one-minute TTL.

Restarts ONLY the staging backend twice and restores its original setting even
on test failure. Do not run concurrently with other staging MCP validation.
"""

import json
import subprocess
import time

import httpx
from jose import jwt
from validate import ROOT, Inspector, RemoteLab


def minutes(value):
    script = """
from pathlib import Path
import re,subprocess
p=Path('/etc/kolibre-stage/backend.env')
text=p.read_text()
assert 'KOLIBRE_ACCESS_TOKEN_EXPIRE_MINUTES=' in text
text=re.sub(r'^KOLIBRE_ACCESS_TOKEN_EXPIRE_MINUTES=.*$',
 'KOLIBRE_ACCESS_TOKEN_EXPIRE_MINUTES=VALUE',text,flags=re.M)
p.write_text(text);p.chmod(0o600)
subprocess.run(['systemctl','restart','kolibre-stage'],check=True)
""".replace("VALUE", str(value))
    subprocess.run(
        ["ssh", "oracle", "sudo", "/opt/kolibre-stage/current/.venv/bin/python", "-"],
        input=script,
        text=True,
        capture_output=True,
        check=True,
    )
    for _ in range(60):
        try:
            if (
                httpx.get(
                    "https://books.drkhn.site/kolibre-api-stage/openapi.json",
                    trust_env=False,
                    timeout=5,
                ).status_code
                == 200
            ):
                return
        except httpx.HTTPError:
            pass
        time.sleep(1)
    raise RuntimeError("Staging backend not ready")


def main():
    # Read only the numeric setting, never export the environment/secrets.
    original = subprocess.check_output(
        [
            "ssh",
            "oracle",
            "sudo",
            "/opt/kolibre-stage/current/.venv/bin/python",
            "-c",
            "\"from pathlib import Path; print(next(x.split('=',1)[1] for x in Path('/etc/kolibre-stage/backend.env').read_text().splitlines() if x.startswith('KOLIBRE_ACCESS_TOKEN_EXPIRE_MINUTES=')))\"",
        ],
        text=True,
    ).strip()
    assert original.isdigit() and 1 <= int(original) <= 10080
    lab, clients = RemoteLab(), []
    try:
        minutes(1)
        for who in ("founder", "sister"):
            lab.login(who)
            # Used only to schedule the test; API/MCP establish authenticity.
            expires = jwt.get_unverified_claims(lab.tokens[who])["exp"]
            assert 55 <= expires - time.time() <= 61
            client = Inspector(lab, who, lab.tokens[who])
            clients.append(client)
            client.connect()
            client.call("kolibre_my_annotations")
        deadline = (
            max(jwt.get_unverified_claims(t)["exp"] for t in lab.tokens.values()) + 1
        )
        while time.time() < deadline:
            time.sleep(max(0.01, min(5, deadline - time.time())))
        for client in clients:
            who = client.who
            headers = {"Authorization": "Bearer " + lab.tokens[who]}
            for url in (lab.url + "/api/users/me", lab.mcp_url):
                assert (
                    httpx.get(
                        url, headers=headers, trust_env=False, timeout=20
                    ).status_code
                    == 401
                )
            code, result = client.run(
                "--connection",
                who,
                "tools/call",
                "kolibre_list_libraries",
                "{}",
                success=False,
            )
            assert code != 0 and ("401" in str(result) or "auth" in str(result).lower())
            lab.login(who)
            client.run("disconnect", who, "--clear-auth")
            client.write_config(lab.tokens[who])
            client.connect()
            notes = json.dumps(client.call("kolibre_my_annotations"))
            other = "sister" if who == "founder" else "founder"
            assert f"{who}-secret-note" in notes and f"{other}-secret-note" not in notes
        print(
            "PASS: genuinely HTTP-issued native tokens expired at API/MCP and existing Inspector sessions for both users; password reauthentication/reconnection preserved private notes. Native refresh grants are unsupported; login issues a new token."
        )
    finally:
        try:
            minutes(int(original))
            print(f"Restored staging native TTL={original} minutes")
        finally:
            for client in clients:
                client.close()
                (
                    ROOT / "evidence/deployment" / f"native-expiry-{client.who}.json"
                ).write_text(
                    (lab.directory / f"inspector-{client.who}.json").read_text()
                )


if __name__ == "__main__":
    main()
