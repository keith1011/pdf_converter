# Homelab — Wave 0（PC-B 資料平面）

對齊 design：`~/.gstack/projects/pdf-scaner/a1217-main-design-20260722-210437.md`

## OS 選擇

| 選項 | 結論 |
|------|------|
| **Ubuntu Server 24.04 LTS** | 首選（文件齊） |
| **Debian 12 (Bookworm) netinst** | **Ubuntu 安裝程式在 Storage probing 崩潰時的正式退路** — Docker/Samba/Qdrant 一樣 OK |
| Ubuntu 22.04.5 Server | 次選退路（較舊 installer，偶可避開 24.04 探測 bug） |
| Desktop 版 / Proxmox / CasaOS | Wave 0 不建議 |

### 若 Ubuntu 在「讀取硬體／磁碟分區（Storage probing）」直接崩潰

先做硬體側（常比換發行版更有效）：
1. BIOS：**SATA Mode = AHCI**（不要 RAID / Intel RST / VMD）
2. 安裝時 **只留目標系統碟 + 安裝 USB**；其餘 SATA/NVMe/外接碟全拔
3. 關掉 Secure Boot 再試一次
4. 仍崩 → 改裝 **Debian 12 netinst**（下面）

**Debian 12 下載：** https://www.debian.org/CD/netinst/ （選 `amd64` netinst ISO）

Debian 安裝要點（對齊 Wave 0）：
- 語言／地區隨意；網路可先有線（之後再裝 Docker）
- 軟體選取：勾 **SSH server**；**不要**桌面環境
- 分區：整碟 Guided 或手動留大空間給之後的 `/data`（可先全在 `/`，之後再掛第二顆 SATA）
- 裝完：`sudo apt update && sudo apt install -y ca-certificates curl`

Docker on Debian 12（官方 repo，與 Ubuntu 類似）：
```bash
sudo apt update
sudo apt install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian bookworm stable" | sudo tee /etc/apt/sources.list.d/docker.list
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
sudo usermod -aG docker "$USER"
```

其餘（`/data/pdf-scaner`、`.env`、`docker compose up`）與 Ubuntu 相同，見下方清單。

## 拓撲提醒

```
C (辦公室筆電) --RustDesk--> A (Windows + Cursor + OCR)
                              |
                         同一交換機 LAN
                              |
                              B (Ubuntu Server + Qdrant)
```

煙測從 **A** 打 B 的 **LAN IP**，不是公網。

## Wave 0 清單（照順序）

### 在 B 上（實體／鍵盤／USB 開機）

1. [ ] 用 Rufus / balenaEtcher 把 24.04 Server ISO 寫進 USB
2. [ ] 安裝 Ubuntu Server 24.04 LTS；記下使用者與主機名（建議 `pdf-b`）
3. [ ] 登入後：`ip -br a` → 記下 **LAN IP**（例如 `192.168.x.y`）
4. [ ] `sudo apt update && sudo apt upgrade -y`
5. [ ] 安裝 Docker（見下方指令）
6. [ ] 建立目錄：`sudo mkdir -p /data/pdf-scaner/{jobs/.incoming,backups/qdrant,backups/jobs,backups/recovery_points} && sudo chown -R $USER:$USER /data/pdf-scaner`
7. [ ] 把本目錄 `homelab/` 拷到 B（U 盤、`scp`、或之後 Samba）
8. [ ] 複製 `.env.example` → `.env`，填 `B_LAN_IP` 與兩個 API key
9. [ ] `docker compose up -d`；`curl http://127.0.0.1:6333/readyz`（若只綁 LAN IP，改 curl 該 IP）
10. [ ] （可選同週末）裝 Tailscale：`curl -fsSL https://tailscale.com/install.sh | sh && sudo tailscale up`

### 在 A 上（Windows）

1. [ ] `ping <B_LAN_IP>`
2. [ ] `curl http://<B_LAN_IP>:6333/readyz` → 應看到 ok
3. [ ] Samba 先可暫緩到下一步；Wave 0 最低完成線是 **readyz**

**Wave 0 完成定義：** 從 A `curl http://<B-LAN-IP>:6333/readyz` 成功。不要裝 Chat / SearXNG / Ollama。

## Docker 安裝（B / Ubuntu 24.04）

```bash
sudo apt update
sudo apt install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo \"$VERSION_CODENAME\") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
sudo usermod -aG docker "$USER"
# 重新登入後才免 sudo
```

## 產生 API key（在 B 或 A）

```bash
# Linux / Git Bash
openssl rand -hex 32
# 跑兩次：一次當 writer，一次當 reader（必須不同）
```

## 啟動 Qdrant

```bash
cd ~/homelab   # 或你放置的路徑
cp .env.example .env
nano .env      # 填 B_LAN_IP 與 keys
docker compose up -d
docker compose ps
curl -s "http://${B_LAN_IP}:6333/readyz"
```

## Wave 1 — publish + ingest (A)

```powershell
cd "C:\Users\a1217\OneDrive\桌面\aiworkplace\pdf scaner"
.\.venv\Scripts\pip.exe install -r homelab\ingest\requirements.txt

# 1) Publish OCR outputs to Samba Z:
.\.venv\Scripts\python.exe homelab\ingest\publish.py --doc-id 123 --source-dir output --share-root Z:\

# 2) Ingest (use WRITER key, not reader)
$env:QDRANT_WRITER_KEY = "<paste-writer-key>"
.\.venv\Scripts\python.exe homelab\ingest\ingest.py --job-dir Z:\jobs\<job_id_from_publish>
```

## Wave 1 — B firewall / backup / keys

Full contract: [`DATA_PLANE.md`](DATA_PLANE.md). Scripts: [`scripts/`](scripts/).

On B (once), after A synced scripts to `Z:\backups\`:

```bash
bash /data/pdf-scaner/backups/ssh-bootstrap/install-pc-a-key.sh
bash /data/pdf-scaner/backups/wave1-scripts/wave1-on-b.sh
```

From A after key install:

```powershell
ssh -i $env:USERPROFILE\.ssh\id_ed25519_homeserver keith@192.168.1.107
```

**Do not start Wave 2** (Ollama / B agent) until Wave 1 gates in `DATA_PLANE.md` are green.