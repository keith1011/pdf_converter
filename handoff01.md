# Handoff 01 — homeserver（PC-B Linux）現況

**Date:** 2026-07-29  
**Scope:** 僅 **homeserver / PC-B** 上仍在用的安裝與設定。  
**不含：** 已刪除／停用項；日本 VPS、WireGuard、gost、WARP、ProxyBridge、PC-A OCR 細節。

權威契約：`homelab/DATA_PLANE.md`（Wave 2 green）。密鑰勿貼進 chat／commit。

---

## 1. 機器身分

| 項 | 值 |
|----|-----|
| Hostname | `homeserver` |
| OS | Ubuntu Server 24.04（SATA 系統碟；Windows 留 M.2） |
| User | `keith`（日常 SSH／服務帳號） |
| 硬體角色 | 5600X + GTX 1660 SUPER + 32GB — **資料真相**，非教師大模型主機 |
| LAN | `192.168.1.107` |
| Tailscale | `100.101.145.120` |
| 對端 A LAN | `192.168.1.104`（ufw 允許來源） |

---

## 2. 遠端存取（SSH）

**仍在用：**

- OpenSSH server
- **金鑰登入 only**（`PasswordAuthentication no`、`PermitRootLogin no`、`AllowUsers keith`）
- fail2ban（SSH 防護）
- 授權金鑰：A／C 等使用 `id_ed25519_homeserver`（或等價 ed25519）寫入 `~keith/.ssh/authorized_keys`
- 連線：
  - LAN：`ssh -i … keith@192.168.1.107`
  - Tailscale：`ssh -i … keith@100.101.145.120`（建議 Host 別名 `homeserver-ts`）

**不做：** 密碼登入、root SSH、把 writer `.env` 拷到筆電 C。

---

## 3. 網路／防火牆

**仍在用：**

- **Tailscale**（mesh；給外出 SSH／管理）。homeserver **不是**日常 Exit Node 用途（出口在別處）。
- **ufw** 啟用：預設 deny incoming、allow outgoing
- 腳本／規則來源：`homelab/scripts/ufw-harden.sh`（副本也在 `/data/pdf-scaner/backups/wave1-scripts/`）

| 服務 | 埠 | 允許來源（概念） |
|------|-----|------------------|
| SSH | 22 | 管理（OpenSSH） |
| Samba | 137–139, 445 | A LAN `192.168.1.104`（+ 可選 A Tailscale） |
| Qdrant | 6333, 6334 | 同上 |

驗證：`sudo ufw status verbose`

---

## 4. 資料平面路徑

```text
/data/pdf-scaner/
  jobs/.incoming/          # publish 暫存
  jobs/<job_id>/           # 權威完成件 + DONE.json
  backups/qdrant/
  backups/jobs/
  backups/recovery_points/
  backups/ssh-bootstrap/
  backups/wave1-scripts/   # 含 ufw／Wave2 完成旗標等
```

**契約：** 原子 publish（`.incoming` → 校驗 → `DONE.json` → `jobs/`）；ingest **只掃** `jobs/`。  
詳見 repo `homelab/DATA_PLANE.md`。

---

## 5. Samba

**仍在用：**

- 分享名對應 B 上 `/data/pdf-scaner`
- PC-A 常映射為 `Z:` → `\\192.168.1.107\pdf-scaner`
- 供 OCR／jobs 檔案平面；寫入 jobs 須走 publish／DONE，勿手改破壞契約

---

## 6. Qdrant（Docker）

**仍在用：**

| 項 | 值 |
|----|-----|
| Compose | repo `homelab/docker-compose.yml`（B 上對應 `~/homelab`／部署目錄） |
| Image | `qdrant/qdrant:v1.13.2` |
| 容器名 | `qdrant` |
| Bind | **僅** `${B_LAN_IP}:6333/6334`（非 `0.0.0.0`） |
| 記憶體上限 | compose `mem_limit: 4g` |
| 重啟 | `unless-stopped` |
| 密鑰 | B `~/homelab/.env`：`QDRANT__SERVICE__API_KEY`（writer）、`QDRANT__SERVICE__READ_ONLY_API_KEY`（reader）、`B_LAN_IP` |
| Collection | `exam_segments_v1`（768-d Cosine；embed 與 A ingest／nomic 對齊） |
| 寫入 | **僅** PC-A ingest CLI（writer key） |
| 讀取 | A Cursor／Codex MCP reader；B 上 Wave2 agent reader |

Wave 1 已做：金鑰輪替、reader upsert→403 neg-test、RP／restore-drill。  
**Compose 故意不含 Ollama**（見下一節）。

常用檢查：

```bash
curl -sS http://192.168.1.107:6333/readyz
# 在 B 上亦可用 LAN IP
```

---

## 7. Wave 2 — Ollama + 唯讀 agent（session-only）

**仍在用（按需開，非開機常駐）：**

| 項 | 值 |
|----|-----|
| 完成旗標 | `/data/pdf-scaner/backups/wave1-scripts/WAVE2_B_DONE` |
| Ollama | **Userspace** `~/opt/ollama` + `~/bin/ollama`（約 v0.32.3） |
| 原因 | 系統路徑安裝曾缺 `llama-server`，改 userspace |
| 開機 | **不** enable `ollama.service`；要跑時手動 `ollama serve` |
| GPU | 1660 SUPER，CUDA 已驗證於 ollama log |
| 模型 | `llama3.2:1b`；`nomic-embed-text` |
| Agent | `~/homelab/agent/query_agent.py`（uv venv；Qdrant **reader**；jobs allowlist 唯讀） |
| 腳本 | repo `homelab/scripts/wave2-*.sh` 等 |

啟動摘要：

```bash
export PATH="$HOME/bin:$HOME/opt/ollama/bin:$PATH"
export OLLAMA_LIBRARY_PATH="$HOME/opt/ollama/lib/ollama"
ollama serve    # 終端 session；Ctrl-C / pkill 停止
cd ~/homelab/agent && . .venv/bin/activate
python query_agent.py "wave1demo"
```

**不是**教師 Chat／常駐推理服務。

---

## 8. 備份／復原（仍適用）

- 腳本：`homelab/scripts/backup-recovery-point.sh`、`restore-drill.sh`
- 已驗證 RP 例：`20260723T152007Z`（jobs + Qdrant snapshot；restore-drill dry-run PASS）
- 規則：jobs 與 Qdrant **同一 RP_ID** 一起還，勿混日期

---

## 9. 與 A／C 的分工（B 視角）

| 誰 | 對 B 做什麼 |
|----|-------------|
| PC-A | LAN 主客戶端：Samba `Z:`、Qdrant writer ingest、MCP reader、Cursor／OCR |
| PC-C | Tailscale SSH 到 B（金鑰已／可寫入 `authorized_keys`）；**不**當 Qdrant writer |
| B | 檔案＋向量權威；可選 session Ollama agent |

A↔B：**同交換機 LAN** 為資料面首選；外出管理用 Tailscale。

---

## 10. 下一位 agent 速查

```bash
# 身分／網
hostname; ip -br a; tailscale ip -4

# 防火牆
sudo ufw status verbose

# Qdrant
docker ps --filter name=qdrant
curl -sS http://127.0.0.1:6333/readyz || curl -sS http://192.168.1.107:6333/readyz

# 資料根
ls /data/pdf-scaner/jobs | head
test -f /data/pdf-scaner/backups/wave1-scripts/WAVE2_B_DONE && cat /data/pdf-scaner/backups/wave1-scripts/WAVE2_B_DONE

# Ollama（若本次需要）
which ollama; pgrep -a ollama || echo 'ollama not running (expected if session-off)'
```

**勿做：** 在 B 上再裝第二套題庫向量庫（Chroma／Cognee／Mengram）；勿把 Qdrant 綁 `0.0.0.0`；勿開機常駐大模型；勿在 chat 貼 key。

---

## 11. 相關 repo 路徑

| 路徑 | 用途 |
|------|------|
| `homelab/DATA_PLANE.md` | 契約與 Wave 狀態 |
| `homelab/docker-compose.yml` | Qdrant only |
| `homelab/scripts/` | ufw、backup、Wave1/2、金鑰套用等 |
| `handoff.md` | 產品總 handoff（含 OCR）；本檔只鎖 B |

**本檔角色：** homeserver 運維／接手下一位 Homelab agent 的單一入口。
