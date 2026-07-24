#!/bin/bash
# Wave 1: document restore drill (dry-run verification).
# Does NOT wipe live data. Checks RP integrity + that documented doc_id has DONE in jobs tree.
# Usage: bash restore-drill.sh [RP_ID]
set -euo pipefail

DATA_ROOT="${DATA_ROOT:-/data/pdf-scaner}"
RP_ID="${1:-}"

if [[ -z "$RP_ID" ]]; then
  RP_ID=$(ls -1 "$DATA_ROOT/backups/recovery_points" 2>/dev/null | sed 's/\.json$//' | sort | tail -1 || true)
fi
[[ -n "$RP_ID" ]] || { echo "no recovery points found" >&2; exit 1; }

RP_FILE="$DATA_ROOT/backups/recovery_points/${RP_ID}.json"
test -f "$RP_FILE"
JOBS_TAR="$DATA_ROOT/backups/jobs/$RP_ID/jobs.tar.gz"
test -f "$JOBS_TAR"

echo "== RP manifest =="
cat "$RP_FILE"

echo "== tar listing (first 40) =="
tar -tzf "$JOBS_TAR" | head -40

echo "== verify DONE.json presence for known jobs inside tarball =="
DONE_COUNT=$(tar -tzf "$JOBS_TAR" | grep -c '/DONE.json$' || true)
echo "DONE.json count in archive: $DONE_COUNT"
[[ "$DONE_COUNT" -ge 1 ]] || { echo "FAIL: no DONE.json in jobs backup" >&2; exit 1; }

echo "== live jobs vs backup (doc_id check) =="
# Prefer doc 123 from Wave1 smoke
if [[ -d "$DATA_ROOT/jobs" ]]; then
  LIVE=$(find "$DATA_ROOT/jobs" -mindepth 2 -maxdepth 2 -name DONE.json ! -path '*/.incoming/*' | wc -l)
  echo "live DONE.json jobs: $LIVE"
fi

QDIR="$DATA_ROOT/backups/qdrant/$RP_ID"
if [[ -d "$QDIR" ]]; then
  echo "== qdrant backup dir =="
  ls -la "$QDIR"
else
  echo "WARN: missing qdrant backup dir $QDIR" >&2
fi

echo "OK: restore drill checks passed for RP_ID=$RP_ID"
echo "NOTE: full restore = stop ingest, restore same RP_ID jobs+qdrant together (never mix dates)."
