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
# Note: Probe tries IPv4 then falls back to dual-stack/IPv6 (VPS egress may be IPv6-only).

[CmdletBinding(PositionalBinding = $false)]
param(
    [string]$ProxyUrl = "http://100.64.70.2:8080",
    [switch]$SkipProbe,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$CodexArgs
)

$ErrorActionPreference = "Stop"

function Invoke-ProxyCurl {
    param(
        [string]$Url,
        [string[]]$IpArgs
    )

    $outFile = [System.IO.Path]::GetTempFileName()
    $errFile = [System.IO.Path]::GetTempFileName()
    try {
        $argList = @()
        if ($IpArgs) { $argList += $IpArgs }
        $argList += @(
            "-sS", "--connect-timeout", "8", "--max-time", "15",
            "--proxy", $Url, "https://ifconfig.me"
        )

        $proc = Start-Process -FilePath "curl.exe" `
            -ArgumentList $argList `
            -NoNewWindow -Wait -PassThru `
            -RedirectStandardOutput $outFile `
            -RedirectStandardError $errFile

        $egress = (Get-Content -Raw -ErrorAction SilentlyContinue $outFile)
        if ($null -eq $egress) { $egress = "" }
        $egress = $egress.Trim()
        $err = (Get-Content -Raw -ErrorAction SilentlyContinue $errFile)
        if ($null -eq $err) { $err = "" }
        $err = $err.Trim()

        return [pscustomobject]@{
            ExitCode = $proc.ExitCode
            Egress   = $egress
            Stderr   = $err
        }
    } finally {
        Remove-Item -Force -ErrorAction SilentlyContinue $outFile, $errFile
    }
}

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

    # Prefer IPv4, but many VPS/WARP paths only return IPv6 (seen: 2a09:bac5:...).
    $attempts = @(
        @{ Label = "IPv4 (-4)"; Args = @("-4") },
        @{ Label = "dual-stack/IPv6"; Args = @() }
    )

    $details = @()
    foreach ($a in $attempts) {
        $r = Invoke-ProxyCurl -Url $Url -IpArgs $a.Args
        $details += "$($a.Label): exit=$($r.ExitCode) body='$($r.Egress)' stderr='$($r.Stderr)'"
        if ($r.ExitCode -eq 0 -and $r.Egress) {
            Write-Host "Proxy OK via $($a.Label); egress: $($r.Egress)"
            return $r.Egress
        }
    }

    Write-Host ($details -join "`n")
    throw "proxy probe failed"
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
  3) IPv4-only probe failed but IPv6 works — re-test without -4:
       curl.exe -sS --proxy $ProxyUrl https://ifconfig.me
  4) Wrong IP/port — confirm ``tailscale status`` still shows 100.64.70.2

Manual checks on PC-A:
  tailscale status
  curl.exe -4 -sS --connect-timeout 8 --proxy $ProxyUrl https://ifconfig.me
  curl.exe -sS --connect-timeout 8 --proxy $ProxyUrl https://ifconfig.me
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
