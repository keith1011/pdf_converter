# Launch Codex CLI via Japan VPS HTTP proxy (Tailscale gost).
# Usage:
#   .\scripts\codex-jp-proxy.ps1
#   .\scripts\codex-jp-proxy.ps1 --version
#   .\scripts\codex-jp-proxy.ps1 -SkipProbe
#   .\scripts\codex-jp-proxy.ps1 -ProxyUrl http://100.64.70.2:8080
#
# Requires: Tailscale up; VPS gost listening on http://100.64.70.2:8080
#
# Note: PositionalBinding=$false so `--version` goes to codex, NOT -ProxyUrl.

[CmdletBinding(PositionalBinding = $false)]
param(
    [string]$ProxyUrl = "http://100.64.70.2:8080",
    [switch]$SkipProbe,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$CodexArgs
)

$ErrorActionPreference = "Stop"

function Test-JpProxy {
    param([string]$Url)

    Write-Host "Probing proxy $Url ..."

    $tailscale = Get-Command tailscale -ErrorAction SilentlyContinue
    if ($tailscale) {
        $ts = & tailscale status --json 2>$null | ConvertFrom-Json -ErrorAction SilentlyContinue
        if ($ts -and $ts.BackendState -and $ts.BackendState -ne "Running") {
            Write-Warning "Tailscale BackendState=$($ts.BackendState) (expected Running)"
        }
    }

    $outFile = [System.IO.Path]::GetTempFileName()
    $errFile = [System.IO.Path]::GetTempFileName()
    try {
        $proc = Start-Process -FilePath "curl.exe" -ArgumentList @(
            "-4", "-sS", "--connect-timeout", "8", "--max-time", "15",
            "--proxy", $Url, "https://ifconfig.me"
        ) -NoNewWindow -Wait -PassThru -RedirectStandardOutput $outFile -RedirectStandardError $errFile

        $egress = (Get-Content -Raw -ErrorAction SilentlyContinue $outFile).Trim()
        $err = (Get-Content -Raw -ErrorAction SilentlyContinue $errFile).Trim()

        if ($proc.ExitCode -ne 0 -or -not $egress) {
            Write-Host "curl exit=$($proc.ExitCode)"
            if ($err) { Write-Host "curl stderr: $err" }
            throw "proxy probe failed"
        }

        Write-Host "Proxy OK; egress IPv4: $egress"
        return $egress
    } finally {
        Remove-Item -Force -ErrorAction SilentlyContinue $outFile, $errFile
    }
}

if (-not $SkipProbe) {
    try {
        [void](Test-JpProxy -Url $ProxyUrl)
    } catch {
        Write-Error @"
Proxy probe failed for $ProxyUrl.

Likely causes (most common first):
  1) VPS gost stopped (SSH window closed) — on VPS run:
       gost -L http://`$(tailscale ip -4):8080
  2) Tailscale down on PC-A — check tray / ``tailscale status``
  3) Wrong IP/port — confirm ``tailscale status`` still shows 100.64.70.2

Manual checks on PC-A:
  tailscale status
  curl.exe -4 -sS --connect-timeout 8 --proxy $ProxyUrl https://ifconfig.me
  ping 100.64.70.2
"@
        exit 1
    }
}

$env:HTTP_PROXY = $ProxyUrl
$env:HTTPS_PROXY = $ProxyUrl
$env:NO_PROXY = "localhost,127.0.0.1,::1,192.168.0.0/16,10.0.0.0/8,100.64.0.0/10"
# Prefer HTTP; do not force SOCKS (Codex Windows is flaky on socks5).
Remove-Item Env:ALL_PROXY -ErrorAction SilentlyContinue
Remove-Item Env:all_proxy -ErrorAction SilentlyContinue

$codex = Get-Command codex -ErrorAction SilentlyContinue
if (-not $codex) {
    Write-Error "codex not found on PATH. Install Codex CLI first, then re-run this script."
    exit 1
}

Write-Host "Starting: codex $($CodexArgs -join ' ')"
Write-Host "HTTP(S)_PROXY=$ProxyUrl"
& codex @CodexArgs
exit $LASTEXITCODE
