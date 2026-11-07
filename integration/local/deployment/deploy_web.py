"""Publish built Kolibre web UI under its own path; preserve BookOrbit routes."""

import argparse
import hashlib
import json
import os
import re
import subprocess
import tarfile
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument("revision")
a = p.parse_args()
assert os.geteuid() == 0 and re.fullmatch("[a-f0-9]{40}", a.revision)
root = Path("/srv/kolibre-web")
release = root / "releases" / a.revision
assert not release.exists()
release.mkdir(parents=True)
with tarfile.open("/tmp/kolibre-web-" + a.revision + ".tar") as t:
    t.extractall(release, filter="data")
for f in release.rglob("*"):
    f.chmod(0o755 if f.is_dir() else 0o644)
route = Path("/etc/caddy/kolibre-stage.routes")
before = route.read_text()
marker = "# Kolibre web UI (managed)"
assert marker not in before, "Web route exists; use an explicit upgrade"
addition = """# Kolibre web UI (managed)
redir /kolibre-stage /kolibre-stage/ 308
handle_path /kolibre-stage/* {
    root * /srv/kolibre-web/current
    header {
        Referrer-Policy no-referrer
        X-Content-Type-Options nosniff
        Cache-Control no-cache
    }
    try_files {path} /index.html
    file_server
}
"""
link = root / "current"
link.symlink_to(release)
try:
    # Match the existing application upload limit; no change to unrelated routes.
    route.write_text(addition + before.replace("max_size 25MB", "max_size 300MB"))
    subprocess.run(
        ["caddy", "validate", "--config", "/etc/caddy/Caddyfile"], check=True
    )
    subprocess.run(["systemctl", "reload", "caddy"], check=True)
except Exception:
    route.write_text(before)
    link.unlink()
    raise
manifest = {
    "git_commit": a.revision,
    "release": str(release),
    "files_sha256": {
        str(f.relative_to(release)): hashlib.sha256(f.read_bytes()).hexdigest()
        for f in release.rglob("*")
        if f.is_file()
    },
}
Path("/etc/kolibre-stage/web-revision.json").write_text(json.dumps(manifest, indent=2))
print("Web interface deployed at https://books.drkhn.site/kolibre-stage/")
