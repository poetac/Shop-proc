#!/usr/bin/env bash
# Restore a SQLite backup produced by backup.sh (HANDOFF.md §13 item 2, §15).
#
# ALWAYS verify a restore before go-live, and STOP THE APP before restoring so
# no writes race the swap (and any WAL sidecars are quiescent). Usage:
#   scripts/restore.sh <backup.db.gz> <target.db> [uploads.tgz] [upload_parent_dir]
# e.g.
#   scripts/restore.sh /data/backups/shop-20260101-020000.db.gz /data/shop.db \
#                      /data/backups/uploads-20260101-020000.tgz /data
#
# The live DB is copied aside to <target>.pre-restore before overwriting.
set -euo pipefail

SRC="${1:?usage: restore.sh <backup.db.gz> <target.db> [uploads.tgz] [upload_parent_dir]}"
TARGET="${2:?usage: restore.sh <backup.db.gz> <target.db> [uploads.tgz] [upload_parent_dir]}"
UPLOADS_SRC="${3:-}"
UPLOAD_PARENT="${4:-/data}"

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

# Clear stale WAL/SHM sidecars so SQLite doesn't replay an old journal.
rm -f "$TARGET-wal" "$TARGET-shm"
mv "$tmp" "$TARGET"
echo "restore: restored $SRC -> $TARGET"

# Optionally restore uploaded files alongside the DB.
if [[ -n "$UPLOADS_SRC" ]]; then
  if [[ ! -f "$UPLOADS_SRC" ]]; then
    echo "restore: uploads archive not found: $UPLOADS_SRC" >&2
    exit 1
  fi
  mkdir -p "$UPLOAD_PARENT"
  tar xzf "$UPLOADS_SRC" -C "$UPLOAD_PARENT"
  echo "restore: restored uploads $UPLOADS_SRC -> $UPLOAD_PARENT"
fi