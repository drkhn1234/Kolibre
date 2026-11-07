#!/usr/bin/env bash
# Restrict legacy test discovery to this lab; hide personal files, mounts and networking.
set -euo pipefail
lab_root=$(cd "$(dirname "$0")" && pwd)
python_runtime=$("$lab_root/.venv/bin/python" -c 'import sys; from pathlib import Path; print(Path(sys.base_prefix).parent)')
exec bwrap --die-with-parent --unshare-net --new-session \
  --ro-bind /usr /usr --symlink usr/lib /lib --symlink usr/lib64 /lib64 \
  --ro-bind /etc /etc --proc /proc --dev /dev --tmpfs /tmp \
  --dir "$(dirname "$python_runtime")" --ro-bind "$python_runtime" "$python_runtime" \
  --dir "$(dirname "$lab_root")" --bind "$lab_root" "$lab_root" \
  --chdir "$PWD" -- "$@"
