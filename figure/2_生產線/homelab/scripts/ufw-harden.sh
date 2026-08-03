#!/bin/bash
# Wave 1: ufw harden on PC-B — allow SSH, Samba, Qdrant only from A LAN (+ optional Tailscale).
# Usage: sudo A_LAN_IP=192.168.1.104 A_TAILSCALE_IP=100.91.139.115 bash ufw-harden.sh
set -euo pipefail

A_LAN_IP="${A_LAN_IP:?set A_LAN_IP to PC-A LAN address}"
A_TAILSCALE_IP="${A_TAILSCALE_IP:-}"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "run as root: sudo A_LAN_IP=... bash $0" >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq ufw

ufw --force reset
ufw default deny incoming
ufw default allow outgoing

# SSH from anywhere on LAN/tailnet management — keep reachable for recovery
ufw allow OpenSSH
# Or lock SSH to A only (uncomment to tighten further):
# ufw allow from "$A_LAN_IP" to any port 22 proto tcp
# [[ -n "$A_TAILSCALE_IP" ]] && ufw allow from "$A_TAILSCALE_IP" to any port 22 proto tcp

# Samba (137-139, 445)
ufw allow from "$A_LAN_IP" to any app Samba
[[ -n "$A_TAILSCALE_IP" ]] && ufw allow from "$A_TAILSCALE_IP" to any app Samba

# Qdrant HTTP/gRPC
ufw allow from "$A_LAN_IP" to any port 6333 proto tcp
ufw allow from "$A_LAN_IP" to any port 6334 proto tcp
[[ -n "$A_TAILSCALE_IP" ]] && ufw allow from "$A_TAILSCALE_IP" to any port 6333 proto tcp
[[ -n "$A_TAILSCALE_IP" ]] && ufw allow from "$A_TAILSCALE_IP" to any port 6334 proto tcp

# Localhost / docker bridge still local; compose already binds B_LAN_IP

ufw --force enable
ufw status verbose
echo "OK: ufw active; Qdrant/Samba limited to A_LAN_IP=$A_LAN_IP${A_TAILSCALE_IP:+ and A_TAILSCALE_IP=$A_TAILSCALE_IP}"
