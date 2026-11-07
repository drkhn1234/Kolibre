"""Add only reviewed staging routes; preserve and roll back the existing proxy."""

import argparse
import ipaddress
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--client-ip", required=True)
args = parser.parse_args()
ipaddress.ip_address(args.client_ip)
assert os.geteuid() == 0
source = Path("/etc/caddy/Caddyfile")
original = source.read_bytes()
info = source.stat()
text = original.decode()
marker = "books.drkhn.site {\n"
assert text.count(marker) == 1, (
    "Unexpected existing proxy structure; inspect before changing"
)
reference = "import /etc/caddy/kolibre-stage.routes"
assert reference not in text, "Staging import already exists; do not reapply blindly"
stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
backup = Path("/var/backups/kolibre-stage") / ("proxy-before-" + stamp)
backup.mkdir(mode=0o700, parents=True)
shutil.copy2(source, backup / "Caddyfile")
template = Path(__file__).with_name("caddy.routes").read_text()
assert "TRUSTED_CLIENT_IP" in template
routes = Path("/etc/caddy/kolibre-stage.routes")
routes.write_text(template.replace("TRUSTED_CLIENT_IP", args.client_ip))
routes.chmod(0o644)
candidate = source.with_name("Caddyfile.kolibre-stage-candidate")
candidate.write_text(text.replace(marker, marker + "\t" + reference + "\n", 1))
os.chown(candidate, info.st_uid, info.st_gid)
os.chmod(candidate, info.st_mode & 0o777)
subprocess.run(
    ["caddy", "validate", "--adapter", "caddyfile", "--config", str(candidate)],
    check=True,
)
os.replace(candidate, source)
try:
    subprocess.run(["systemctl", "reload", "caddy"], check=True)
except subprocess.CalledProcessError:
    source.write_bytes(original)
    subprocess.run(["systemctl", "reload", "caddy"], check=True)
    raise
print("Staging routes loaded; original proxy preserved at", backup)
