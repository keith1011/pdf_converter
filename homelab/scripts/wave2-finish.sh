#!/bin/bash
# Wave 2 finish — assume ollama binary + NVIDIA already OK. No reinstall.
# Usage: bash ~/homelab/scripts/wave2-finish.sh
set -euo pipefail

CHAT_MODEL="${OLLAMA_MODEL:-llama3.2:1b}"
EMBED_MODEL="${OLLAMA_EMBED_MODEL:-nomic-embed-text}"
AGENT_DIR="${HOME}/homelab/agent"

# Prefer userspace install if present (fixes broken /usr/local missing llama-server)
if [[ -x "${HOME}/opt/ollama/bin/ollama" ]]; then
  export PATH="${HOME}/bin:${HOME}/opt/ollama/bin:${PATH}"
  export OLLAMA_LIBRARY_PATH="${HOME}/opt/ollama/lib/ollama${OLLAMA_LIBRARY_PATH:+:$OLLAMA_LIBRARY_PATH}"
fi

if ! command -v ollama >/dev/null 2>&1; then
  echo "ollama missing" >&2
  exit 1
fi
if ! command -v nvidia-smi >/dev/null 2>&1; then
  echo "nvidia-smi missing" >&2
  exit 1
fi
nvidia-smi -L
echo "using ollama: $(command -v ollama) ($(ollama --version 2>/dev/null || true))"

# Prefer systemd if available; else background serve
# Wave 2: never enable on boot
if systemctl list-unit-files 2>/dev/null | grep -q '^ollama\.service'; then
  sudo -n systemctl start ollama 2>/dev/null || true
  sudo -n systemctl disable ollama 2>/dev/null || true
fi

if ! curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
  echo "== starting ollama serve (user session) =="
  # Kill broken system daemon if any
  pkill -f '[o]llama serve' 2>/dev/null || true
  sleep 1
  nohup env PATH="$PATH" OLLAMA_LIBRARY_PATH="${OLLAMA_LIBRARY_PATH:-}" \
    ollama serve >/tmp/ollama-serve.log 2>&1 &
  sleep 2
fi

for _ in $(seq 1 60); do
  if curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
curl -fsS http://127.0.0.1:11434/api/tags >/dev/null

echo "== pull $CHAT_MODEL =="
ollama pull "$CHAT_MODEL"
echo "== pull $EMBED_MODEL =="
ollama pull "$EMBED_MODEL"
ollama list

echo "== smoke generate =="
curl -fsS http://127.0.0.1:11434/api/generate \
  -H 'Content-Type: application/json' \
  -d "{\"model\":\"$CHAT_MODEL\",\"prompt\":\"Reply with exactly: OK\",\"stream\":false}" \
  | head -c 400
echo

mkdir -p "$AGENT_DIR"
if [[ -f /data/pdf-scaner/backups/wave2-agent/query_agent.py ]]; then
  cp -a /data/pdf-scaner/backups/wave2-agent/. "$AGENT_DIR/"
fi
cd "$AGENT_DIR"
test -f query_agent.py

# Prefer uv (no sudo); Ubuntu often lacks python3-venv / ensurepip
export PATH="${HOME}/.local/bin:${PATH}"
if command -v uv >/dev/null 2>&1; then
  echo "== agent env via uv =="
  uv venv .venv
  # shellcheck disable=SC1091
  source .venv/bin/activate
  uv pip install -r requirements.txt
elif python3 -m venv .venv 2>/tmp/wave2-venv.err; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
  pip install -q -U pip
  pip install -q -r requirements.txt
else
  echo "WARN: no uv and python3-venv missing; agent runs stdlib-only (MatchText fallback)" >&2
  cat /tmp/wave2-venv.err >&2 || true
  rm -rf .venv
fi

export QDRANT_URL="${QDRANT_URL:-http://192.168.1.107:6333}"
export OLLAMA_MODEL="$CHAT_MODEL"
export OLLAMA_EMBED_MODEL="$EMBED_MODEL"

echo "== agent smoke =="
PY=python3
if [[ -x .venv/bin/python ]]; then
  PY=.venv/bin/python
fi
"$PY" query_agent.py "wave1demo" || "$PY" query_agent.py "判別式"

date -u +%Y-%m-%dT%H:%M:%SZ | tee /data/pdf-scaner/backups/wave1-scripts/WAVE2_B_DONE
echo "OK: Wave2 finish complete (boot: keep ollama OFF via no systemd enable; serve is session-only)"
echo "Later start: ollama serve   OR   sudo systemctl start ollama && sudo systemctl disable ollama"
