# Run once on PC-B (Ubuntu) — Homelab Wave 1

From B console / RustDesk / any existing SSH session:

```bash
bash /data/pdf-scaner/backups/ssh-bootstrap/install-pc-a-key.sh
bash /data/pdf-scaner/backups/wave1-scripts/wave1-on-b.sh
```

That will:
1. Install PC-A's SSH pubkey
2. Apply ufw (SSH + Samba/Qdrant from A LAN)
3. Create a recovery point + restore drill
4. If `qdrant.env.new` is present, rotate Qdrant keys and write `KEYS_ROTATED`

After step 1 alone, from PC-A you can:

```powershell
ssh -i $env:USERPROFILE\.ssh\id_ed25519_homeserver keith@192.168.1.107
```

Agent will poll for `Z:\backups\wave1-scripts\WAVE1_B_DONE`.
