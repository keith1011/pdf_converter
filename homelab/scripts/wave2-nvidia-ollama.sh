#!/bin/bash
# Wave 2 on B — NVIDIA driver (1660 Super) + Ollama (GPU) + read-only agent.
# Requires sudo. Ollama systemd remains DISABLED for boot (start manually).
#
# Usage:
#   bash ~/homelab/scripts/wave2-nvidia-ollama.sh          # phase auto
#   bash ~/homelab/scripts/wave2-nvidia-ollama.sh drivers  # install drivers only → reboot
#   bash ~/homelab/scripts/wave2-nvidia-ollama.sh ollama   # after reboot: ollama+models+agent
set -euo pipefail

PHASE="${1:-auto}"
CHAT_MODEL="${OLLAMA_MODEL:-llama3.2:1b}"
EMBED_MODEL="${OLLAMA_EMBED_MODEL:-nomic-embed-text}"
AGENT_DIR="${HOME}/homelab/agent"

need_sudo() {
  if [[ "$(id -u)" -eq 0 ]]; then
    return 0
  fi
  sudo -v
}

install_drivers() {
  need_sudo
  export DEBIAN_FRONTEND=noninteractive
  echo "== apt update =="
  sudo apt-get update -qq
  echo "== install ubuntu-drivers-common + recommended NVIDIA =="
  sudo apt-get install -y ubuntu-drivers-common build-essential
  echo "== recommended drivers =="
  ubuntu-drivers devices || true
  sudo ubuntu-drivers autoinstall
  echo
  echo "OK: NVIDIA driver packages installed."
  echo ">>> REBOOT REQUIRED: sudo reboot"
  echo ">>> After reboot, in Cursor terminal run:"
  echo "    ssh -t -i \$env:USERPROFILE\\.ssh\\id_ed25519_homeserver keith@192.168.1.107 \"bash ~/homelab/scripts/wave2-nvidia-ollama.sh ollama\""
  date -u +%Y-%m-%dT%H:%M:%SZ | tee /data/pdf-scaner/backups/wave1-scripts/WAVE2_DRIVERS_INSTALLED || true
}

verify_gpu() {
  if ! command -v nvidia-smi >/dev/null 2>&1; then
    echo "nvidia-smi missing — drivers not active (reboot needed?)" >&2
    return 1
  fi
  nvidia-smi
}

install_ollama_and_agent() {
  need_sudo
  verify_gpu

  if ! command -v ollama >/dev/null 2>&1; then
    echo "== install ollama =="
    curl -fsSL https://ollama.com/install.sh | sh
  else
    echo "ollama present: $(command -v ollama)"
  fi

  sudo systemctl disable ollama 2>/dev/null || true
  sudo systemctl start ollama 2>/dev/null || sudo systemctl restart ollama
  sudo systemctl disable ollama 2>/dev/null || true

  echo "== wait for ollama API =="
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

  echo "== smoke generate =="
  curl -fsS http://127.0.0.1:11434/api/generate \
    -H 'Content-Type: application/json' \
    -d "{\"model\":\"$CHAT_MODEL\",\"prompt\":\"Reply with exactly: OK\",\"stream\":false}" \
    | head -c 300
  echo

  echo "== agent venv =="
  mkdir -p "$AGENT_DIR"
  if [[ -f /data/pdf-scaner/backups/wave2-agent/query_agent.py ]]; then
    cp -a /data/pdf-scaner/backups/wave2-agent/. "$AGENT_DIR/"
  fi
  cd "$AGENT_DIR"
  python3 -m venv .venv
  # shellcheck disable=SC1091
  source .venv/bin/activate
  pip install -q -U pip
  pip install -q -r requirements.txt

  export QDRANT_URL="${QDRANT_URL:-http://192.168.1.107:6333}"
  export OLLAMA_MODEL="$CHAT_MODEL"
  export OLLAMA_EMBED_MODEL="$EMBED_MODEL"

  echo "== agent smoke =="
  python query_agent.py "wave1demo" || python query_agent.py "判別式"

  date -u +%Y-%m-%dT%H:%M:%SZ | tee /data/pdf-scaner/backups/wave1-scripts/WAVE2_B_DONE
  echo
  echo "OK: Wave2 complete — GPU + Ollama + agent."
  echo "Boot: ollama DISABLED. Start: sudo systemctl start ollama"
}

case "$PHASE" in
  drivers) install_drivers ;;
  ollama) install_ollama_and_agent ;;
  auto)
    if command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi >/dev/null 2>&1; then
      install_ollama_and_agent
    else
      install_drivers
    fi
    ;;
  *) echo "usage: $0 [auto|drivers|ollama]" >&2; exit 2 ;;
esac
