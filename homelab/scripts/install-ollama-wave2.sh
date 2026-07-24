#!/bin/bash
# Wave 2: install Ollama on PC-B, pull a small model, keep systemd DISABLED (not on boot).
# Usage: bash install-ollama-wave2.sh
# Design: VRAM ≤4GB; start manually: sudo systemctl start ollama
set -euo pipefail

MODEL="${OLLAMA_MODEL:-llama3.2:1b}"
EMBED_MODEL="${OLLAMA_EMBED_MODEL:-nomic-embed-text}"

if ! command -v ollama >/dev/null 2>&1; then
  echo "== installing ollama =="
  curl -fsSL https://ollama.com/install.sh | sh
else
  echo "ollama already installed: $(command -v ollama)"
fi

# Do NOT enable on boot (Wave 2 success criterion)
if command -v systemctl >/dev/null 2>&1; then
  sudo systemctl disable ollama 2>/dev/null || true
  sudo systemctl stop ollama 2>/dev/null || true
  echo "systemd: ollama disabled for boot (start manually when needed)"
fi

echo "== start ollama for model pull =="
# Prefer user service / background if systemd start needs password
if sudo -n systemctl start ollama 2>/dev/null; then
  :
elif systemctl --user start ollama 2>/dev/null; then
  :
else
  # Fallback: run daemon in background for this session
  if ! pgrep -x ollama >/dev/null 2>&1; then
    nohup ollama serve >/tmp/ollama-serve.log 2>&1 &
    sleep 2
  fi
fi

# Wait for API
for i in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
curl -fsS http://127.0.0.1:11434/api/tags >/dev/null

echo "== pull chat model: $MODEL =="
ollama pull "$MODEL"
echo "== pull embed model: $EMBED_MODEL =="
ollama pull "$EMBED_MODEL"

echo "== smoke generate =="
curl -fsS http://127.0.0.1:11434/api/generate \
  -H 'Content-Type: application/json' \
  -d "{\"model\":\"$MODEL\",\"prompt\":\"Reply with exactly: OK\",\"stream\":false}" \
  | head -c 400
echo

echo "== smoke embed =="
curl -fsS http://127.0.0.1:11434/api/embeddings \
  -H 'Content-Type: application/json' \
  -d "{\"model\":\"$EMBED_MODEL\",\"prompt\":\"test\"}" \
  | head -c 200
echo

# Stop again so it is not left as always-on unless user wants it
if sudo -n systemctl stop ollama 2>/dev/null; then
  echo "stopped ollama via systemd (boot still disabled)"
elif pgrep -x ollama >/dev/null 2>&1; then
  echo "NOTE: ollama still running in this session; stop with: pkill ollama  OR  sudo systemctl stop ollama"
fi

echo "OK: Wave2 Ollama installed; chat=$MODEL embed=$EMBED_MODEL; boot=disabled"
echo "Start later: sudo systemctl start ollama   # or: ollama serve"
echo "Agent env: OLLAMA_MODEL=$MODEL OLLAMA_EMBED_MODEL=$EMBED_MODEL"
