#!/usr/bin/env bash
set -euo pipefail

BACKUP_DIR=/work/P7/backups
# Backups run weekly (see crontab on the VM); keep the last ~4 weeks
KEEP_DAYS=28
COMPOSE_FILE=/work/P7/p7/docker/database.compose.yml
# A core table that must exist and contain rows. If it doesn't, the database is
# empty or wrong (e.g. Postgres started on an empty data folder) and we must not
# rotate away the older, good backups.
SENTINEL_TABLE=trips

psql_value() {
    docker compose -f "$COMPOSE_FILE" exec -T postgres \
        psql -U postgres -d p7 -tAX -c "$1"
}

if [ "$(psql_value "SELECT to_regclass('public.$SENTINEL_TABLE') IS NOT NULL")" != "t" ]; then
    echo "$(date -Is) ABORT: table '$SENTINEL_TABLE' does not exist; database looks empty. No backup taken, old backups kept." >&2
    exit 1
fi

if [ "$(psql_value "SELECT EXISTS (SELECT 1 FROM $SENTINEL_TABLE)")" != "t" ]; then
    echo "$(date -Is) ABORT: table '$SENTINEL_TABLE' is empty. No backup taken, old backups kept." >&2
    exit 1
fi

target="$BACKUP_DIR/p7_$(date +%F_%H%M).dump"

docker compose -f "$COMPOSE_FILE" exec -T postgres \
    pg_dump -U postgres -d p7 --format=custom > "$target.partial"
mv "$target.partial" "$target"

echo "$(date -Is) OK: wrote $target ($(du -h "$target" | cut -f1))"

# Only rotate once a verified backup exists
find "$BACKUP_DIR" -name 'p7_*.dump' -mtime +"$KEEP_DAYS" -delete
