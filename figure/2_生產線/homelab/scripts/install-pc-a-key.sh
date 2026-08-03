#!/bin/bash
# Install PC-A SSH pubkey from Samba bootstrap path.
# Run once on B: bash /data/pdf-scaner/backups/ssh-bootstrap/install-pc-a-key.sh
set -euo pipefail
PUB="${1:-/data/pdf-scaner/backups/ssh-bootstrap/pc-a.pub}"
test -f "$PUB"
mkdir -p "$HOME/.ssh"
chmod 700 "$HOME/.ssh"
touch "$HOME/.ssh/authorized_keys"
chmod 600 "$HOME/.ssh/authorized_keys"
if ! grep -qxF "$(cat "$PUB")" "$HOME/.ssh/authorized_keys" 2>/dev/null; then
  cat "$PUB" >> "$HOME/.ssh/authorized_keys"
fi
echo "OK: PC-A pubkey installed for $(whoami)@$(hostname)"
