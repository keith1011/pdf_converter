#!/bin/bash
# Wave 1: create recovery point — jobs tarball + Qdrant snapshot + RP manifest.
# Run on B (needs curl, writer key from ~/homelab/.env).
# Usage: bash backup-recovery-point.sh
set -euo pipefail

DATA_ROOT="${DATA_ROOT:-/data/pdf-scaner}"
HOMELAB_ENV="${HOMELAB_ENV:-$HOME/homelab/.env}"

if [[ ! -f "$HOMELAB_ENV" ]]; then
  echo "missing $HOMELAB_ENV" >&2
  exit 1
fi
# shellcheck disable=SC1090
set -a
# shellcheck source=/dev/null
source "$HOMELAB_ENV"
set +a

# Compose binds Qdrant to B_LAN_IP only — not loopback
QDRANT_URL="${QDRANT_URL:-http://${B_LAN_IP:?B_LAN_IP missing}:6333}"
WRITER_KEY="${QDRANT__SERVICE__API_KEY:?writer key missing in .env}"
RP_ID="${RP_ID:-$(date -u +%Y%m%dT%H%M%SZ)}"
JOBS_DST="$DATA_ROOT/backups/jobs/$RP_ID"
QDRANT_DST="$DATA_ROOT/backups/qdrant/$RP_ID"
RP_FILE="$DATA_ROOT/backups/recovery_points/${RP_ID}.json"

mkdir -p "$JOBS_DST" "$QDRANT_DST" "$(dirname "$RP_FILE")"

echo "== packing jobs (exclude .incoming) =="
tar -C "$DATA_ROOT/jobs" \
  --exclude='.incoming' \
  -czf "$JOBS_DST/jobs.tar.gz" \
  .

echo "== qdrant full snapshot =="
SNAP_RESP=$(curl -sS -X POST "$QDRANT_URL/snapshots" \
  -H "api-key: $WRITER_KEY" \
  -H "Content-Type: application/json")
echo "$SNAP_RESP" | tee "$QDRANT_DST/snapshot-create.json"

SNAP_NAME=$(SNAP_RESP="$SNAP_RESP" python3 - <<'PY'
import json, os
d = json.loads(os.environ["SNAP_RESP"])
r = d.get("result")
name = ""
if isinstance(r, dict):
    name = r.get("name") or ""
elif isinstance(r, list) and r and isinstance(r[-1], dict):
    name = r[-1].get("name") or ""
print(name)
PY
)

if [[ -z "$SNAP_NAME" ]]; then
  echo "FAIL: could not parse full snapshot name" >&2
  exit 1
fi
echo "$SNAP_NAME" > "$QDRANT_DST/snapshot_name.txt"
curl -sS -f -H "api-key: $WRITER_KEY" \
  "$QDRANT_URL/snapshots/${SNAP_NAME}" \
  -o "$QDRANT_DST/${SNAP_NAME}"
ls -lh "$QDRANT_DST/${SNAP_NAME}"

echo "== collection snapshot exam_segments_v1 =="
COLL=exam_segments_v1
COLL_RESP=$(curl -sS -X POST "$QDRANT_URL/collections/${COLL}/snapshots" \
  -H "api-key: $WRITER_KEY")
echo "$COLL_RESP" | tee "$QDRANT_DST/collection-${COLL}-snapshot.json"
COLL_NAME=$(COLL_RESP="$COLL_RESP" python3 - <<'PY'
import json, os
d = json.loads(os.environ["COLL_RESP"])
r = d.get("result")
name = ""
if isinstance(r, dict):
    name = r.get("name") or ""
elif isinstance(r, list) and r and isinstance(r[-1], dict):
    name = r[-1].get("name") or ""
print(name)
PY
)
if [[ -n "$COLL_NAME" ]]; then
  echo "$COLL_NAME" > "$QDRANT_DST/collection_snapshot_name.txt"
  curl -sS -f -H "api-key: $WRITER_KEY" \
    "$QDRANT_URL/collections/${COLL}/snapshots/${COLL_NAME}" \
    -o "$QDRANT_DST/${COLL_NAME}"
  ls -lh "$QDRANT_DST/${COLL_NAME}"
fi

python3 - <<PY
import json
from pathlib import Path
rp = {
  "rp_id": "$RP_ID",
  "created_at": __import__("datetime").datetime.utcnow().isoformat() + "Z",
  "jobs_path": "$JOBS_DST/jobs.tar.gz",
  "qdrant_snapshot_dir": "$QDRANT_DST",
  "full_snapshot": "$SNAP_NAME",
  "collection_snapshot": "$COLL_NAME",
  "note": "Wave1 recovery point — restore jobs tarball + matching qdrant snapshots together",
  "collection": "exam_segments_v1",
}
Path("$RP_FILE").write_text(json.dumps(rp, indent=2) + "\n", encoding="utf-8")
print("OK wrote", "$RP_FILE")
PY

echo "OK: recovery point $RP_ID"
