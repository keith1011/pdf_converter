# Data plane contract (Wave 0–1)

Status: **Wave 1 green** (2026-07-23). Wave 2 (Ollama / B agent) stays **closed**.

## Endpoints

| Item | Value |
|------|--------|
| Host | `homeserver` / user `keith` |
| A LAN | `192.168.1.104` |
| B LAN | `192.168.1.107` |
| Qdrant (from A LAN) | `http://192.168.1.107:6333` |
| SSH (LAN) | `ssh -i ~/.ssh/id_ed25519_homeserver keith@192.168.1.107` |
| SSH (Tailscale) | `ssh -i ~/.ssh/id_ed25519_homeserver keith@100.101.145.120` |
| Writer / reader keys | B `~/homelab/.env` + A `%USERPROFILE%\.homelab\qdrant.a.env` — never commit |
| Collection (Wave 1) | `exam_segments_v1` (768-dim, Cosine, nomic-embed-text on A) |

## Paths on B

```
/data/pdf-scaner/
  jobs/.incoming/     # staging before atomic publish
  jobs/<job_id>/      # authoritative completed jobs + DONE.json
  backups/qdrant/
  backups/jobs/
  backups/recovery_points/
  backups/ssh-bootstrap/
  backups/wave1-scripts/
```

## Writers / readers

| Actor | Host | Qdrant |
|-------|------|--------|
| ingest CLI | A | writer key (`QDRANT_WRITER_KEY`) |
| Cursor `user-qdrant` MCP | A | reader key only |
| B Ollama agent | B (Wave 2+) | reader key; default OFF — **not started** |

## Topology

- A↔B: **LAN** (same switch)
- C→A: RustDesk; Cursor on A
- Tailscale: A+B for remote ops

## Firewall (B `ufw`) — allowed sources

Default: **deny incoming**, allow outgoing. `ENABLED=yes` (verified 2026-07-23).

| Service | Port | Allowed sources |
|---------|------|-----------------|
| SSH | 22 | OpenSSH app (management) |
| Samba | 137–139, 445 | A LAN `192.168.1.104` (+ optional A Tailscale) |
| Qdrant | 6333, 6334 | A LAN `192.168.1.104` (+ optional A Tailscale) |

Docker compose binds Qdrant to `${B_LAN_IP}:6333` (not `0.0.0.0`). Host `ufw` is still required.

```bash
sudo A_LAN_IP=192.168.1.104 A_TAILSCALE_IP=100.91.139.115 \
  bash /data/pdf-scaner/backups/wave1-scripts/ufw-harden.sh
sudo ufw status verbose
```

## Backup + restore drill

Scripts: `homelab/scripts/backup-recovery-point.sh`, `restore-drill.sh`.

Verified RP: **`20260723T152007Z`**
- jobs tar with **2× DONE.json** (`123` + `wave1demo`)
- full + collection snapshots under `backups/qdrant/20260723T152007Z/`
- restore-drill dry-run **PASS**

Rule: restore the **same** `RP_ID` for jobs + Qdrant together — never mix dates.

## Reader / writer key checklist

- [x] Rotated both keys in B `~/homelab/.env`; compose recreated
- [x] A MCP reader updated (`~/.cursor/mcp.json`); ingest via `QDRANT_WRITER_KEY` User env
- [x] Neg-test PASS: reader upsert/delete → **403**; writer upsert+delete OK

```powershell
$env:QDRANT_URL = "http://192.168.1.107:6333"
# keys from %USERPROFILE%\.homelab\qdrant.a.env — do not paste into chat/git
.\.venv\Scripts\python.exe homelab\scripts\reader_neg_test.py
```

## Wave 1 acceptance

- [x] SSH A→B with `id_ed25519_homeserver`
- [x] `ufw` enabled; Samba/Qdrant limited to A LAN (+ optional Tailscale)
- [x] RP `20260723T152007Z` + restore-drill logged
- [x] Reader neg-test PASS; keys rotated
- [x] ≥2 `doc_id` ingested (`123`=827, `wave1demo`=8, total **835**); re-ingest idempotent
- [x] This file Status → Wave 1 green; Wave 2 closed
