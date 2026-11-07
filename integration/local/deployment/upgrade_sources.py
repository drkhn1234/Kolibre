"""Root-only staging source upgrade from uploaded Git archives, with rollback.

The caller uploads /tmp/kolibre-source-REV.tar and supplies the two full Git
revisions. Existing dependencies are copied, not redownloaded. Persistent data,
identity services, Caddy and unrelated applications are untouched.
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tarfile
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", required=True)
    parser.add_argument("--bridge", required=True)
    args = parser.parse_args()
    assert os.geteuid() == 0
    releases = []
    for name, revision in (
        ("kolibre-stage", args.backend),
        ("kolibre-mcp-stage", args.bridge),
    ):
        assert re.fullmatch(r"[a-f0-9]{40}", revision)
        root = Path("/opt") / name
        old = (root / "current").resolve(strict=True)
        target = root / "releases" / revision
        if target == old:
            saved = json.loads(Path("/etc/kolibre-stage/revisions.json").read_text())[
                name
            ]
            assert saved["git_commit"] == revision and saved["release"] == str(target)
            releases.append((root, old, target, revision, saved["files_sha256"]))
            continue
        assert not target.exists(), f"Release already exists: {target}"
        archive = Path("/tmp") / f"kolibre-source-{revision}.tar"
        target.mkdir()
        with tarfile.open(archive) as source:
            source.extractall(target, filter="data")
        # Keep an independent dependency environment so rollback remains viable.
        shutil.copytree(old / ".venv", target / ".venv", symlinks=True)
        if name == "kolibre-mcp-stage":
            pth = (
                target
                / ".venv/lib/python3.12/site-packages/_editable_impl_calibremcp.pth"
            )
            assert pth.read_text().strip() == str(old / "src")
            pth.write_text(str(target / "src") + "\n")
        files = {
            str(path.relative_to(target)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in target.rglob("*")
            if path.is_file() and ".venv" not in path.relative_to(target).parts
        }
        releases.append((root, old, target, revision, files))
    # Pin backend retrieval imports to this exact CalibreMCP source release.
    # Dependencies already exist in the isolated environment; never import legacy tools.
    backend_target = releases[0][2]
    bridge_target = releases[1][2]
    assert backend_target != releases[0][1] or bridge_target == releases[1][1], (
        "Bridge changes require a new backend dependency environment"
    )
    (
        backend_target / ".venv/lib/python3.12/site-packages/kolibre_retrieval.pth"
    ).write_text(str(bridge_target / "src") + "\n")
    changed = [
        root.name for root, old, target, revision, files in releases if target != old
    ]
    try:
        for root, old, target, revision, files in releases:
            if target == old:
                continue
            temporary = root / "current.next"
            temporary.symlink_to(target)
            temporary.replace(root / "current")
        if changed:
            subprocess.run(["systemctl", "restart", *changed], check=True)
        import time
        import urllib.error
        import urllib.request

        for _ in range(60):
            try:
                with urllib.request.urlopen(
                    "http://127.0.0.1:18081/openapi.json", timeout=3
                ) as response:
                    assert response.status == 200
                with urllib.request.urlopen(
                    "http://127.0.0.1:18082/.well-known/oauth-protected-resource/kolibre-mcp-stage/mcp",
                    timeout=3,
                ) as response:
                    assert response.status == 200
                break
            except (OSError, urllib.error.URLError):
                time.sleep(1)
        else:
            raise RuntimeError("Stage did not become ready")
    except BaseException:
        for root, old, target, revision, files in releases:
            if target == old:
                continue
            temporary = root / "rollback.next"
            temporary.symlink_to(old)
            temporary.replace(root / "current")
        if changed:
            subprocess.run(["systemctl", "restart", *changed], check=True)
        raise
    manifest = {
        root.name: {
            "git_commit": revision,
            "release": str(target),
            "files_sha256": files,
        }
        for root, old, target, revision, files in releases
    }
    Path("/etc/kolibre-stage/revisions.json").write_text(
        json.dumps(manifest, indent=2) + "\n"
    )
    print(json.dumps({name: value["git_commit"] for name, value in manifest.items()}))


if __name__ == "__main__":
    main()
