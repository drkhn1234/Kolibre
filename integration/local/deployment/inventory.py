"""Read-only, credential-free VPS inventory; run over SSH with sudo python3."""

import hashlib
import json
import platform
import shutil
import subprocess
import urllib.error
import urllib.request
from pathlib import Path


def command(*args):
    return subprocess.run(
        args, capture_output=True, text=True, check=True
    ).stdout.strip()


def values(node, key):
    if isinstance(node, dict):
        for name, value in node.items():
            if name == key:
                yield value
            yield from values(value, key)
    elif isinstance(node, list):
        for value in node:
            yield from values(value, key)


ids = command("docker", "ps", "-q").split()
containers = json.loads(command("docker", "inspect", *ids)) if ids else []
caddyfile = Path("/etc/caddy/Caddyfile")
config = json.loads(command("caddy", "adapt", "--config", str(caddyfile)))
servers = config.get("apps", {}).get("http", {}).get("servers", {})
health = {}
for port in (3000, 3001, 6806, 6807):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=5) as response:
            health[str(port)] = response.status
    except urllib.error.HTTPError as error:
        health[str(port)] = error.code
    except OSError as error:
        health[str(port)] = type(error).__name__
result = {
    "checked_at": command("date", "--iso-8601=seconds"),
    "architecture": platform.machine(),
    "os": platform.freedesktop_os_release(),
    "cpu_count": command("nproc"),
    "memory": command("free", "-m"),
    "disk": command("df", "-hT", "/"),
    "containers": [
        {
            "name": c["Name"],
            "image": c["Config"]["Image"],
            "image_id": c["Image"],
            "running": c["State"]["Running"],
            "health": c["State"].get("Health", {}).get("Status"),
            "started": c["State"]["StartedAt"],
            "mounts": [
                {k: m.get(k) for k in ("Type", "Source", "Destination", "RW")}
                for m in c["Mounts"]
            ],
            "restart": c["HostConfig"]["RestartPolicy"],
            "memory_limit": c["HostConfig"]["Memory"],
            "ports": c["NetworkSettings"]["Ports"],
        }
        for c in containers
    ],
    "compose_projects": json.loads(
        command("docker", "compose", "ls", "--format", "json")
    ),
    "proxy": {
        "listeners": {name: server.get("listen") for name, server in servers.items()},
        "hosts": list(values(servers, "host")),
        "upstreams": list(values(servers, "upstreams")),
        "caddyfile_sha256": hashlib.sha256(caddyfile.read_bytes()).hexdigest(),
    },
    "loopback_health": health,
    "listeners": command("ss", "-ltnp"),
    "firewall_v4": command("iptables", "-S"),
    "firewall_v6": command("ip6tables", "-S"),
    "tailscale_serve": command("tailscale", "serve", "status"),
    "java": shutil.which("java"),
}
print(json.dumps(result, indent=2))
