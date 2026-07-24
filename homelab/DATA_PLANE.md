# Data plane contract (Wave 0–2)

Status: **Wave 2 green** (2026-07-24). Wave 1 remains green underneath.

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
| B Ollama agent | B (Wave 2) | reader key; **session-only** `ollama serve` (not on boot) |

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
- [x] This file Status → Wave 1 green; Wave 2 closed (superseded by Wave 2 section below)

## Wave 2 (B Ollama + read-only agent)

**Done flag:** `/data/pdf-scaner/backups/wave1-scripts/WAVE2_B_DONE` (`2026-07-23T22:44:15Z`)

| Item | Value |
|------|--------|
| GPU | GTX 1660 SUPER (CUDA OK in ollama log) |
| Ollama install | **Userspace** `~/opt/ollama` + `~/bin/ollama` (v0.32.3) — system `/usr/local` was incomplete (missing `llama-server`) |
| Boot | **OFF** — no `ollama.service` enabled; start with `ollama serve` in a session |
| Chat model | `llama3.2:1b` (≤4GB VRAM budget) |
| Embed model | `nomic-embed-text` (768-d, matches `exam_segments_v1`) |
| Agent | `~/homelab/agent/query_agent.py` (uv venv; Qdrant **reader**; jobs allowlist read-only) |

### Start / stop (B)

```bash
export PATH="$HOME/bin:$HOME/opt/ollama/bin:$PATH"
export OLLAMA_LIBRARY_PATH="$HOME/opt/ollama/lib/ollama"
ollama serve   # session only; Ctrl-C or pkill ollama to stop
cd ~/homelab/agent && . .venv/bin/activate
python query_agent.py "wave1demo"
```

Scripts: `homelab/scripts/wave2-ollama-userspace.sh`, `wave2-finish.sh`.

### Wave 2 acceptance

- [x] Ollama API generate smoke → `OK.`
- [x] Agent: reader upsert probe **PASS** (403); hits from `wave1demo`; answer returned
- [x] Not enabled on boot (`systemctl is-enabled ollama` → not-found)
- [x] Out of scope still closed: teacher Chat UI, SearXNG, Grafana, 7B+ on B, MCP gateway

### Compose note

`homelab/docker-compose.yml` stays **Qdrant-only**. Do **not** add an always-on Ollama service. Optional later profile may document userspace start only.
