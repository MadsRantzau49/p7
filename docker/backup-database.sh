#!/usr/bin/env bash
set -eu

BACKUP_DIR=/work/P7/backups
KEEP_DAYS=7
COMPOSE_FILE=/work/P7/p7/docker/database.compose.yml

target="$BACKUP_DIR/p7_$(date +%F_%H%M).dump"

docker compose -f "$COMPOSE_FILE" exec -T postgres \
    pg_dump -U postgres -d p7 --format=custom > "$target.partial"
mv "$target.partial" "$target"

find "$BACKUP_DIR" -name 'p7_*.dump' -mtime +"$KEEP_DAYS" -delete