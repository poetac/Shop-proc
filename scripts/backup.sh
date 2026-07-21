#!/usr/bin/env bash
# Daily SQLite backup (HANDOFF.md §13 item 2).
#
# Uses SQLite's online backup API via `.backup` so it is safe to run while the
# app is live. Keeps the last 14 daily copies. Schedule via cron, e.g.:
#   0 2 * * *  /app/scripts/backup.sh >> /var/log/shop-backup.log 2>&1
#
# Env:
#   DB_PATH     path to the live SQLite file (default: /data/shop.db)
#   BACKUP_DIR  where copies go (default: /data/backups)
#   KEEP        how many daily copies to retain (default: 14)
set -euo pipefail

DB_PATH="${DB_PATH:-/data/shop.db}"
BACKUP_DIR="${BACKUP_DIR:-/data/backups}"
KEEP="${KEEP:-14}"

if [[ ! -f "$DB_PATH" ]]; then
  echo "backup: no database at $DB_PATH — nothing to do" >&2
  exit 0
fi

mkdir -p "$BACKUP_DIR"
stamp="$(date +%Y%m%d-%H%M%S)"
dest="$BACKUP_DIR/shop-$stamp.db"

# Consistent hot copy.
sqlite3 "$DB_PATH" ".backup '$dest'"
gzip -f "$dest"
echo "backup: wrote ${dest}.gz"

# Prune old copies, keeping the most recent $KEEP.
ls -1t "$BACKUP_DIR"/shop-*.db.gz 2>/dev/null | tail -n +"$((KEEP + 1))" | while read -r old; do
  rm -f "$old"
  echo "backup: pruned $old"
done
