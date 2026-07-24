#!/bin/bash
# Wave 2 one-shot on B: install ollama (boot off) + agent venv + smoke query.
# Usage: bash wave2-on-b.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_AGENT="${REPO_AGENT:-$HOME/homelab/agent}"
DATA_SCRIPTS="/data/pdf-scaner/backups/wave1-scripts"

# Prefer synced copies under Samba backups or ~/homelab
if [[ -f "$DATA_SCRIPTS/install-ollama-wave2.sh" ]]; then
  bash "$DATA_SCRIPTS/install-ollama-wave2.sh"
elif [[ -f "$SCRIPT_DIR/install-ollama-wave2.sh" ]]; then
  bash "$SCRIPT_DIR/install-ollama-wave2.sh"
else
  echo "missing install-ollama-wave2.sh" >&2
  exit 1
fi

# Ensure ollama is up for smoke
if ! curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
  if sudo -n systemctl start ollama 2>/dev/null; then
    :
  else
    nohup ollama serve >/tmp/ollama-serve.log 2>&1 &
  fi
  sleep 3
fi

mkdir -p "$HOME/homelab/agent"
# Copy agent from Samba if present
if [[ -d /data/pdf-scaner/backups/wave1-scripts/../wave2-agent ]]; then
  cp -a /data/pdf-scaner/backups/wave2-agent/. "$HOME/homelab/agent/" || true
fi
if [[ -f "$REPO_AGENT/query_agent.py" ]]; then
  :
elif [[ -f /data/pdf-scaner/backups/wave2-agent/query_agent.py ]]; then
  cp -a /data/pdf-scaner/backups/wave2-agent/. "$HOME/homelab/agent/"
fi

cd "$HOME/homelab/agent"
python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q -U pip
pip install -q -r requirements.txt

export QDRANT_URL="${QDRANT_URL:-http://192.168.1.107:6333}"
export OLLAMA_MODEL="${OLLAMA_MODEL:-llama3.2:1b}"
export OLLAMA_EMBED_MODEL="${OLLAMA_EMBED_MODEL:-nomic-embed-text}"
# Reader key from ~/homelab/.env via agent loader

echo "== agent smoke =="
python query_agent.py "wave1demo" || python query_agent.py "判別式"

date -u +%Y-%m-%dT%H:%M:%SZ | tee /data/pdf-scaner/backups/wave1-scripts/WAVE2_B_DONE
echo "OK: Wave2 B-side smoke complete"
