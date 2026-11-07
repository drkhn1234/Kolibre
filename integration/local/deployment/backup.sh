#!/usr/bin/env bash
set -euo pipefail
umask 077
test "$(id -u)" = 0
base=/var/backups/kolibre-stage/snapshots
install -d -m 0700 "$base/daily" "$base/weekly" "$base/monthly"
work=$(mktemp -d /run/kolibre-stage-backup.XXXXXXXX)
stamp=$(date -u +%Y%m%dT%H%M%SZ)
output="$base/daily/$stamp.tar.gz.age"
backend_active=0
bridge_active=0
idp_active=0
worker_active=0
systemctl is-active --quiet kolibre-stage && backend_active=1
systemctl is-active --quiet kolibre-mcp-stage && bridge_active=1
test "$(docker inspect --format '{{.State.Running}}' kolibre-stage-idp-1)" != true || idp_active=1
systemctl is-active --quiet kolibre-knowledge-stage && worker_active=1
restore_services() {
    if test "$idp_active" = 1; then
        docker compose -f /opt/kolibre-stage/deployment/compose.yml start idp >/dev/null
    fi
    if test "$backend_active" = 1; then systemctl start kolibre-stage; fi
    if test "$bridge_active" = 1; then systemctl start kolibre-mcp-stage; fi
    if test "$worker_active" = 1; then systemctl start kolibre-knowledge-stage; fi
    rm -rf -- "$work"
}
trap restore_services EXIT
trap 'exit 1' HUP INT TERM
if test "$worker_active" = 1; then systemctl stop kolibre-knowledge-stage; fi
systemctl stop kolibre-mcp-stage kolibre-stage
docker compose -f /opt/kolibre-stage/deployment/compose.yml stop idp >/dev/null
python3 - <<'PY'
import sqlite3
with sqlite3.connect('/var/lib/kolibre-stage/app.db') as db:
    assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
    assert db.execute('SELECT count(*) FROM private_book_moves WHERE active_key IS NOT NULL').fetchone()[0] == 0, 'Resolve active move before scheduled snapshot'
PY
docker exec kolibre-stage-idp-db-1 pg_dump -U kolibre_idp -d keycloak > "$work/idp.sql"
cp -a /etc/kolibre-stage "$work/settings"
cp -a /opt/kolibre-stage/deployment "$work/deployment"
cp /usr/local/sbin/kolibre-stage-backup "$work/backup-script"
install -d -m 0700 "$work/units"
cp /etc/systemd/system/kolibre-stage.service /etc/systemd/system/kolibre-mcp-stage.service /etc/systemd/system/kolibre-stage-idp.service "$work/units/"
cp /etc/systemd/system/kolibre-stage-backup.service /etc/systemd/system/kolibre-stage-backup.timer "$work/units/"
if test -f /etc/systemd/system/kolibre-knowledge-stage.service; then cp /etc/systemd/system/kolibre-knowledge-stage.service "$work/units/"; fi
cp /etc/caddy/kolibre-stage.routes "$work/routes"
tar -czf - -C /var/lib kolibre-stage -C "$work" idp.sql settings units routes deployment backup-script |
    age -r "$(cat /etc/kolibre-stage/backup-recipient.txt)" -o "$output.partial"
mv "$output.partial" "$output"
sha256sum "$output" > "$output.sha256"
python3 - "$output" <<'PY'
from datetime import datetime, timezone
import os
from pathlib import Path
import sys
source=Path(sys.argv[1]); base=source.parent.parent
now=datetime.now(timezone.utc)
for folder,key in [('weekly',now.strftime('%G-W%V')),('monthly',now.strftime('%Y-%m'))]:
    destination=base/folder/(key+'.tar.gz.age')
    temporary=destination.with_suffix('.tmp')
    if temporary.exists(): temporary.unlink()
    os.link(source,temporary); os.replace(temporary,destination)
for folder,keep in [('daily',7),('weekly',4),('monthly',3)]:
    files=sorted((base/folder).glob('*.age'),key=lambda p:p.name,reverse=True)
    for file in files[keep:]:
        file.unlink()
        checksum=Path(str(file)+'.sha256')
        if checksum.exists(): checksum.unlink()
PY
printf 'Encrypted staging snapshot: %s\n' "$output"
