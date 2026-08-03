#!/bin/bash
# Apply new Qdrant keys from a file and recreate container.
# Usage: bash apply-qdrant-env.sh /path/to/qdrant.env.new
set -euo pipefail

NEW_ENV="${1:?path to qdrant.env.new}"
HOMELAB="${HOMELAB:-$HOME/homelab}"
test -f "$NEW_ENV"
test -d "$HOMELAB"

cp -a "$HOMELAB/.env" "$HOMELAB/.env.bak.$(date -u +%Y%m%dT%H%M%SZ)" 2>/dev/null || true
# Merge: keep unknown keys, replace the three known
python3 - <<'PY' "$NEW_ENV" "$HOMELAB/.env"
import sys
from pathlib import Path
new_path, env_path = Path(sys.argv[1]), Path(sys.argv[2])
new = {}
for line in new_path.read_text(encoding="utf-8").splitlines():
    line=line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    k,v=line.split("=",1)
    new[k.strip()]=v.strip()
old = {}
if env_path.exists():
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.strip().startswith("#") or "=" not in line:
            continue
        k,v=line.split("=",1)
        old[k.strip()]=v.strip()
old.update({k:new[k] for k in ("B_LAN_IP","QDRANT__SERVICE__API_KEY","QDRANT__SERVICE__READ_ONLY_API_KEY") if k in new})
# Ensure B_LAN_IP
if "B_LAN_IP" not in old:
    raise SystemExit("B_LAN_IP missing")
text="\n".join(f"{k}={old[k]}" for k in sorted(old)) + "\n"
env_path.write_text(text, encoding="utf-8")
print("updated", env_path)
PY

cd "$HOMELAB"
# shellcheck disable=SC1091
set -a
# shellcheck source=/dev/null
source "$HOMELAB/.env"
set +a
docker compose up -d
sleep 3
curl -sS "http://${B_LAN_IP:?B_LAN_IP missing}:6333/readyz"
echo
echo "OK: qdrant restarted with new keys — update A MCP reader + ingest writer env"
