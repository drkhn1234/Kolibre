"""Root-only opt-in for derived retrieval; does not touch identity/other apps."""

import os
import subprocess
from pathlib import Path

assert os.geteuid() == 0
for name, key in [
    ("backend", "KOLIBRE_KNOWLEDGE_ENABLED"),
    ("bridge", "KOLIBRE_MCP_KNOWLEDGE_ENABLED"),
]:
    path = Path("/etc/kolibre-stage") / (name + ".env")
    lines = [l for l in path.read_text().splitlines() if not l.startswith(key + "=")]
    path.write_text("\n".join(lines + [key + "=1"]) + "\n")
    path.chmod(0o600)
path = Path("/etc/kolibre-stage/backend.env")
lines = [
    l
    for l in path.read_text().splitlines()
    if not l.startswith(
        ("HF_HOME=", "HF_HUB_DISABLE_IMPLICIT_TOKEN=", "CALIBRE_MCP_LOG_FILE=")
    )
]
path.write_text(
    "\n".join(
        lines
        + [
            "HF_HOME=/var/lib/kolibre-stage/huggingface",
            "HF_HUB_DISABLE_IMPLICIT_TOKEN=1",
            "CALIBRE_MCP_LOG_FILE=/var/lib/kolibre-stage/calibremcp-retrieval.jsonl",
        ]
    )
    + "\n"
)
path.chmod(0o600)
subprocess.run(["systemctl", "daemon-reload"], check=True)
subprocess.run(
    ["systemctl", "restart", "kolibre-stage", "kolibre-mcp-stage"], check=True
)
subprocess.run(["systemctl", "enable", "kolibre-knowledge-stage.service"], check=True)
subprocess.run(["systemctl", "restart", "kolibre-knowledge-stage.service"], check=True)
print("Knowledge retrieval enabled; dedicated worker bounded to 50% CPU / 768 MiB.")
