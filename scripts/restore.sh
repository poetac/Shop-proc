#!/usr/bin/env bash
# Restore a SQLite backup produced by backup.sh (HANDOFF.md §13 item 2, §15).
#
# ALWAYS verify a restore before go-live. Usage:
#   scripts/restore.sh /data/backups/shop-20260101-020000.db.gz /data/shop.db
#
# The live DB is copied aside to <target>.pre-restore before overwriting.
set -euo pipefail

SRC="${1:?usage: restore.sh <backup.db.gz> <target.db>}"
TARGET="${2:?usage: restore.sh <backup.db.gz> <target.db>}"

if [[ ! -f "$SRC" ]]; then
  echo "restore: backup not found: $SRC" >&2
  exit 1
fi

tmp="$(mktemp)"
if [[ "$SRC" == *.gz ]]; then
  gunzip -c "$SRC" > "$tmp"
else
  cp "$SRC" "$tmp"
fi

# Sanity-check the restored file is a valid SQLite DB before swapping it in.
if ! sqlite3 "$tmp" "PRAGMA integrity_check;" | grep -q "^ok$"; then
  echo "restore: integrity check FAILED — aborting" >&2
  rm -f "$tmp"
  exit 1
fi

if [[ -f "$TARGET" ]]; then
  cp "$TARGET" "$TARGET.pre-restore"
  echo "restore: saved current DB to $TARGET.pre-restore"
fi

mv "$tmp" "$TARGET"
echo "restore: restored $SRC -> $TARGET"
