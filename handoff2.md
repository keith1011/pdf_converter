# Handoff 2 — Japan VPS egress for ChatGPT Windows / Codex（給 Codex agent）

**Date:** 2026-07-28  
**Audience:** next **Codex / ChatGPT Windows** helper agent on **PC-A**（`C:\Users\a1217`）  
**Scope:** 只讓 **ChatGPT Windows 內建 Codex**、**Codex CLI**（＋可選瀏覽器）走日本 VPS；其餘流量直連。  
**Not in scope:** P-ocr OCR pipeline、Homelab Wave、Qdrant、改 repo 產品碼（除非使用者明確要求把本文件再整理進 docs）。

Do **not** invent state. Prefer this file + live `curl` / `ssh` 檢查。勿貼 SSH key、WARP license、密碼進 chat／commit。

---

## 1. Goal（使用者鎖定）

| Want | Do |
|------|-----|
| 只有 ChatGPT Windows／裡頭的 Codex 走日本 | HTTP 代理經 Tailscale → VPS `gost` |
| **Codex CLI** 也走日本 | 同一 `HTTP_PROXY`／`HTTPS_PROXY`（見 §5.4、`scripts/codex-jp-proxy.ps1`） |
| 可選：瀏覽器部分流量走日本 | 同一 HTTP 代理或本機 SOCKS |
| Homelab / Samba / 一般上網 | **直連**（不要開 Tailscale Exit Node） |

**不要用：** `tailscale set --exit-node=...`（整機出站）。  
**不要用：** 只設 `ALL_PROXY=socks5://...` 開 ChatGPT／CLI（Windows Codex 對 SOCKS 不穩；要 **HTTP** 代理）。

---

## 2. Topology（已選定）

```
PC-A (Windows)
  ChatGPT.exe / Desktop Codex  ─┐
  Codex CLI (`codex`)          ─┼─HTTP_PROXY──►  http://100.64.70.2:8080
                                              │
                                         Tailscale
                                              │
                                         Japan VPS
                                         gost -L http://<ts-ipv4>:8080
                                              │
                                         VPS WAN / IPv6 egress
                                              ▼
                                         Internet
```

| 節點 | 角色 | 已知值 |
|------|------|--------|
| PC-A | ChatGPT Windows + Codex CLI；設行程／shell 級 `HTTP_PROXY` | User `a1217` |
| Japan VPS | Tailscale 節點 + `gost` HTTP 代理 | Tailscale IPv4 **`100.64.70.2`**（hostname 曾見 `VM126A68275163C82`） |
| PC-B Homelab | 無關本 lane；維持直連 | LAN `192.168.1.107` / TS `100.101.145.120` |

另：VPS 曾裝過 Tailscale Exit Node（整機方案）；**本目標改用 per-app HTTP**，Exit Node 應保持關閉。

---

## 3. Current status（2026-07-28）

### Done

- [x] Japan VPS + Tailscale 可達；Exit Node 曾驗證（含 `--exit-node-allow-lan-access`），後改為 **不要**用 Exit Node 做分流。
- [x] 決定分流模型：VPS 上 **gost HTTP**，只綁 Tailscale IP；ChatGPT 用 **HTTP** 而非 SOCKS。
- [x] VPS 上已能跑 `gost`（勿用 `apt install gost` 那個 0.1.2 假包；用 GitHub **go-gost** 二進位）。
- [x] PC-A 驗證代理通：
  ```powershell
  curl.exe -s --proxy http://100.64.70.2:8080 https://ifconfig.me
  ```
  曾回傳 IPv6：`2a09:bac5:4436:dc::16:174`（出口活著；可能偏 CF／WARP IPv6 段，以實測為準）。

### In progress / next（Codex agent 接著做）

- [ ] 確認 VPS 上 `gost` **仍在跑**（見 §4）。
- [ ] **完全退出** ChatGPT 後，用行程級 HTTP 代理啟動（見 §5）。
- [ ] **Codex CLI**：用 §5.4 或 `.\scripts\codex-jp-proxy.ps1` 啟動並實測。
- [ ] 在 ChatGPT／Codex 內做一次真實請求，確認能連；必要時對照直連 IP。
- [ ] （可選）瀏覽器 SwitchyOmega → HTTP `100.64.70.2:8080`。
- [ ] （可選）把 VPS `gost` 做成 systemd，避免 SSH 視窗關掉就停。

### Explicitly deferred / avoid

- Cloudflare WARP **full tunnel** 與 Tailscale／SSH 並用（曾斷 SSH；需 VNC `warp-cli disconnect`）。
- WARP proxy mode chaining 當 Exit Node 出站（Exit Node 不會自動吃 Socks）。
- 繞過服務地區／帳號封鎖的「變家用 IP」幻想；本文件只做 **技術出口路由**。

---

## 4. 確認 gost 還在跑

### 從 PC-A（最快）

```powershell
curl.exe -4 -s --connect-timeout 5 --proxy http://100.64.70.2:8080 https://ifconfig.me
```

- 有印 IP → 8080 通。  
- 失敗／逾時 → gost 停了或防火牆／Tailscale 斷了。

直連對照：

```powershell
curl.exe -4 -s https://ifconfig.me
```

### 在 VPS 上

```bash
ssh root@100.64.70.2   # 或既有使用者／金鑰
ps aux | grep '[g]ost'
ss -lntp | grep 8080
```

重開（前景；視窗要留著）：

```bash
gost -L http://$(tailscale ip -4):8080
```

若 `gost: command not found`：重新放 GitHub 二進位到 `/usr/local/bin/gost`（**不要** `apt install gost`）。

---

## 5. 用代理啟動 ChatGPT Windows／Codex

### 5.1 不裝額外程式（先試）

1. 系統匣也把 ChatGPT **完全退出**。  
2. VPS `gost` 確認存活（§4）。  
3. PC-A PowerShell：

```powershell
$env:HTTP_PROXY  = "http://100.64.70.2:8080"
$env:HTTPS_PROXY = "http://100.64.70.2:8080"
$env:NO_PROXY    = "localhost,127.0.0.1,::1"

# Store 包名可能隨版本變；打不開就改找 ChatGPT.exe 真實路徑
Start-Process "shell:AppsFolder\OpenAI.ChatGPT-Desktop_2p2nqsd0c76g0!ChatGPT"
```

找路徑：開始選單 → ChatGPT → 右鍵 → 打開檔案位置 → 對捷徑再「打開檔案位置」，然後：

```powershell
Start-Process "C:\完整路徑\ChatGPT.exe"
```

（必須在**同一個**已設好 `$env:HTTP_*` 的視窗裡啟動。）

### 5.2 可選：裝 launcher

若 Store 啟動不吃環境變數：  
https://github.com/gaopengbin/chatgpt-proxy-launcher  

- Host: `100.64.70.2`  
- Port: `8080`  
- 協定：**HTTP**（不要填 SOCKS）

### 5.3 已知坑

| 現象 | 處理 |
|------|------|
| SOCKS 不穩／Reconnecting | 改 HTTP `8080`；不要只設 `ALL_PROXY=socks5://` |
| 從開始選單開 ChatGPT 像沒走代理 | 必須用帶 env 的 `Start-Process` 或 launcher |
| `cd /tmp` 在 PowerShell 失敗 | `/tmp` 是 **Linux VPS** 路徑；本機不要跑 VPS 安裝指令 |
| Exit Node 一開 Homelab／整機異常 | `tailscale set --exit-node=` 清掉 |

### 5.4 Codex CLI（同一代理）

CLI 吃環境變數 `HTTP_PROXY` / `HTTPS_PROXY`（**HTTP**，不要 SOCKS）。`config.toml` 沒有獨立 proxy 鍵時以 env 為準。

**一次性（目前這個 PowerShell 視窗）：**

```powershell
# 1) gost 還活著
curl.exe -4 -s --proxy http://100.64.70.2:8080 https://ifconfig.me
# 若 -4 失敗，改不加 -4（出口可能只有 IPv6）
curl.exe -s --proxy http://100.64.70.2:8080 https://ifconfig.me

# 2) 設代理（勿設 ALL_PROXY=socks5）
$env:HTTP_PROXY  = "http://100.64.70.2:8080"
$env:HTTPS_PROXY = "http://100.64.70.2:8080"
$env:NO_PROXY    = "localhost,127.0.0.1,::1,192.168.0.0/16,10.0.0.0/8,100.64.0.0/10"
Remove-Item Env:ALL_PROXY -ErrorAction SilentlyContinue

# 3) 確認 CLI 在 PATH
codex --version

# 4) 啟動
codex
```

**用 repo 腳本（備援）：** `.\scripts\codex-jp-proxy.ps1`（probe 會先試 IPv4 再 dual-stack）。

### 5.5 用應用程式代替腳本（建議）

VPS 上 **gost 仍要開**；下面只取代 PC-A 的 PowerShell 啟動方式。

| 方案 | 適合 | 怎麼設（你的代理） | 備註 |
|------|------|-------------------|------|
| **[chatgpt-proxy-launcher](https://github.com/gaopengbin/chatgpt-proxy-launcher)** | ChatGPT Windows／裡頭 Codex | Host `100.64.70.2`，Port `8080`，**HTTP** | 專為 Desktop；行程級 `HTTP_PROXY`；勿填 SOCKS |
| **[Proxifier](https://www.proxifier.com/)**（付費） | Desktop **＋** `codex.exe` CLI | Profile → Proxy：HTTP `100.64.70.2:8080`；Rules：只對 `ChatGPT.exe` / `codex.exe` Action=該 proxy；其餘 Direct；保留 Localhost Direct | 不靠 env，較不易「腳本突然掛」；試用可先驗證 |
| Clash Verge / Mihomo 等 | 進階規則分流 | 上游指到 `100.64.70.2:8080` 或本機再轉；用 **process** 規則只匹配 ChatGPT／codex | 設定較重；SOCKS／TUN 對 Codex 曾不穩，優先 HTTP |

**推薦路徑（少折騰）：**

1. Desktop → 裝 **chatgpt-proxy-launcher**，代理 `100.64.70.2:8080`（HTTP）。  
2. 若也要 CLI 穩定、不想養 ps1 → 用 **Proxifier** 規則綁 `codex.exe`（同一 HTTP proxy）。  
3. `scripts/codex-jp-proxy.ps1` 留作備援，不必當日常入口。

Proxifier 規則骨架：

1. Proxy Servers → Add → Type **HTTPS/HTTP**，Address `100.64.70.2`，Port `8080`  
2. Proxification Rules（由上到下）：  
   - Localhost → **Direct**（預設保留）  
   - `ChatGPT.exe`; `codex.exe` → **你的 Japan proxy**  
   - Default → **Direct**  
3. 不要開「整機都走 proxy」。

關掉該 App／規則 = 恢復直連；**不要**開 Tailscale Exit Node。

---

## 6. （可選）VPS 常駐 gost — systemd 草稿

僅在使用者要「重開機／斷 SSH 仍可用」時做：

```ini
# /etc/systemd/system/gost-ts-http.service
[Unit]
Description=gost HTTP proxy on Tailscale IP
After=network-online.target tailscaled.service
Wants=network-online.target

[Service]
ExecStart=/usr/local/bin/gost -L http://100.64.70.2:8080
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now gost-ts-http.service
sudo systemctl status gost-ts-http.service
```

**安全：** 只綁 `100.64.70.2`（或 `$(tailscale ip -4)`），不要 `-L http://0.0.0.0:8080` 暴露到公網。

---

## 7. 對照：曾考慮但未採用的方案

| 方案 | 結論 |
|------|------|
| Tailscale Exit Node 整機 | 能用，但不是「只有 Codex」 |
| PC-A：`ssh -D 1080` + 本機 gost HTTP→SOCKS | 可行；目前改成代理直接在 VPS，少一跳 |
| 原文 iecho.cc：WARP proxy + V2Ray/SS outbound | 已改寫成 Tailscale 思維；本 lane 不跑 SS/V2Ray |
| WARP full tunnel on VPS | 易斷 SSH；與 Exit Node 衝突 |

參考對話脈絡文章（指令已過時）：  
https://iecho.cc/posts/apply-cloudflare-warp-for-v2ray-shadowsocks-outbound-connections  

現行 `warp-cli` 若以後要碰：`registration new` / `mode set proxy` / `proxy port`；全隧道前先 `tunnel ip add` 排除客戶端 IP 與 `100.64.0.0/10`。

---

## 8. Definition of done（本 handoff）

1. PC-A：`curl --proxy http://100.64.70.2:8080` 穩定回出口 IP。  
2. 不開 Exit Node。  
3. ChatGPT Windows／Desktop Codex 經 `HTTP_PROXY` 或 launcher 啟動後可正常對話。  
4. **Codex CLI** 在設好 `HTTP_PROXY`／`HTTPS_PROXY`（或 `scripts/codex-jp-proxy.ps1`）後可正常跑。  
5. 瀏覽器／系統其餘流量未被迫走日本（抽樣直連 `ifconfig.me` 與代理結果不同即可）。  

---

## 9. 給 Codex agent 的第一動

1. 跑 §4 的 `curl.exe -4 ... --proxy http://100.64.70.2:8080`。  
2. 不通 → SSH 進 VPS 重開 `gost`（或做 §6 systemd）。  
3. 通 → §5 Desktop；§5.4／`scripts/codex-jp-proxy.ps1` 跑 CLI。  
4. 回報：代理 IPv4、Desktop／CLI 是否都吃到代理、還缺不缺 launcher／systemd。

**P-ocr / `handoff.md`：** 那是產品主 handoff；本檔是 **網路 egress 支線**。兩邊不要互相覆蓋狀態。
