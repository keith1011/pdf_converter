#!/bin/bash
# One-shot Wave 1 B-side: SSH key already installed OR run install-pc-a-key first.
# Then: ufw + backup + restore drill + optional apply new qdrant env.
# Usage on B:
#   bash /data/pdf-scaner/backups/wave1-scripts/wave1-on-b.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# Prefer repo scripts if mounted at ~/homelab/scripts
REPO_SCRIPTS="${REPO_SCRIPTS:-$HOME/homelab/scripts}"
if [[ -d "$REPO_SCRIPTS" ]]; then
  SCRIPT_DIR="$REPO_SCRIPTS"
fi

A_LAN_IP="${A_LAN_IP:-192.168.1.104}"
A_TAILSCALE_IP="${A_TAILSCALE_IP:-100.91.139.115}"

echo "== 0) ensure PC-A key =="
if [[ -f /data/pdf-scaner/backups/ssh-bootstrap/install-pc-a-key.sh ]]; then
  bash /data/pdf-scaner/backups/ssh-bootstrap/install-pc-a-key.sh || true
fi

echo "== 1) ufw harden =="
sudo A_LAN_IP="$A_LAN_IP" A_TAILSCALE_IP="$A_TAILSCALE_IP" bash "$SCRIPT_DIR/ufw-harden.sh"

echo "== 2) backup recovery point =="
bash "$SCRIPT_DIR/backup-recovery-point.sh"

echo "== 3) restore drill =="
bash "$SCRIPT_DIR/restore-drill.sh"

if [[ -f /data/pdf-scaner/backups/wave1-scripts/qdrant.env.new ]]; then
  echo "== 4) apply rotated qdrant keys =="
  bash "$SCRIPT_DIR/apply-qdrant-env.sh" /data/pdf-scaner/backups/wave1-scripts/qdrant.env.new
  # Signal for A that keys changed
  date -u +%Y-%m-%dT%H:%M:%SZ > /data/pdf-scaner/backups/wave1-scripts/KEYS_ROTATED
fi

date -u +%Y-%m-%dT%H:%M:%SZ > /data/pdf-scaner/backups/wave1-scripts/WAVE1_B_DONE
echo "OK: Wave1 B-side complete. Flag: WAVE1_B_DONE"
