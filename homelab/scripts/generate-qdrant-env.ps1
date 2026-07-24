# Generate new Qdrant writer/reader keys onto Samba for B apply-qdrant-env.sh
# Does NOT print key material. Does NOT update mcp.json (do that after B restarts).
$ErrorActionPreference = 'Stop'
function New-HexKey([int]$n = 32) {
  $buf = New-Object byte[] $n
  $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
  try { $rng.GetBytes($buf) } finally { $rng.Dispose() }
  -join ($buf | ForEach-Object { '{0:x2}' -f $_ })
}
$writer = New-HexKey 32
$reader = New-HexKey 32
if ($writer -eq $reader) { throw 'writer/reader collision' }
$dstDir = 'Z:\backups\wave1-scripts'
New-Item -ItemType Directory -Force -Path $dstDir, "$env:USERPROFILE\.homelab" | Out-Null
$lines = @(
  'B_LAN_IP=192.168.1.107'
  "QDRANT__SERVICE__API_KEY=$writer"
  "QDRANT__SERVICE__READ_ONLY_API_KEY=$reader"
  'A_LAN_IP=192.168.1.104'
  'A_TAILSCALE_IP=100.91.139.115'
)
$path = Join-Path $dstDir 'qdrant.env.new'
$lines | Set-Content -Path $path -Encoding Ascii
Copy-Item $path "$env:USERPROFILE\.homelab\qdrant.env.new" -Force
# Local A-side env snippets (not git)
@(
  "QDRANT_URL=http://192.168.1.107:6333"
  "QDRANT_WRITER_KEY=$writer"
  "QDRANT_READER_KEY=$reader"
) | Set-Content "$env:USERPROFILE\.homelab\qdrant.a.env" -Encoding Ascii
Write-Output "OK wrote $path and %USERPROFILE%\.homelab\qdrant*.env (keys not echoed)"
