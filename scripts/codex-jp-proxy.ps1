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

if (-not $SkipProbe) {
    Write-Host "Probing proxy $ProxyUrl ..."
    try {
        $egress = & curl.exe -4 -s --connect-timeout 5 --proxy $ProxyUrl "https://ifconfig.me"
        if (-not $egress) { throw "empty response" }
        Write-Host "Proxy OK; egress IPv4: $egress"
    } catch {
        Write-Error @"
Proxy probe failed for $ProxyUrl.
On VPS: gost -L http://`$(tailscale ip -4):8080
Or: curl.exe -4 -s --proxy $ProxyUrl https://ifconfig.me
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
