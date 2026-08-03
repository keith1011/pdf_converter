# After B writes WAVE1_B_DONE / KEYS_ROTATED, finish Wave 1 on A.
# Loads %USERPROFILE%\.homelab\qdrant.a.env (never prints secrets).
$ErrorActionPreference = 'Stop'
$Repo = 'C:\Users\a1217\OneDrive\桌面\aiworkplace\pdf scaner'
if (-not (Test-Path (Join-Path $Repo '2_生產線\homelab\ingest\ingest.py'))) {
  # Fallback: scripts live at <repo>/homelab/scripts
  $Repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
}
$envFile = Join-Path $env:USERPROFILE '.homelab\qdrant.a.env'
if (-not (Test-Path $envFile)) { throw "missing $envFile — run generate-qdrant-env.ps1 first" }

Get-Content $envFile | ForEach-Object {
  if ($_ -match '^\s*#' -or $_ -notmatch '=') { return }
  $k, $v = $_.Split('=', 2)
  Set-Item -Path "Env:$k" -Value $v
}
if (-not $env:QDRANT_WRITER_KEY -or -not $env:QDRANT_READER_KEY) {
  throw 'qdrant.a.env missing QDRANT_WRITER_KEY or QDRANT_READER_KEY'
}

# Persist writer for future ingest (User scope)
[Environment]::SetEnvironmentVariable('QDRANT_WRITER_KEY', $env:QDRANT_WRITER_KEY, 'User')
[Environment]::SetEnvironmentVariable('QDRANT_URL', $env:QDRANT_URL, 'User')
[Environment]::SetEnvironmentVariable('QDRANT_READER_KEY', $env:QDRANT_READER_KEY, 'User')

# Update MCP reader key in mcp.json
$mcpPath = Join-Path $env:USERPROFILE '.cursor\mcp.json'
$mcp = Get-Content $mcpPath -Raw | ConvertFrom-Json
$server = $null
if ($mcp.mcpServers.'user-qdrant') { $server = $mcp.mcpServers.'user-qdrant' }
elseif ($mcp.mcpServers.qdrant) { $server = $mcp.mcpServers.qdrant }
else { throw 'no qdrant server in mcp.json' }
if (-not $server.env) { $server | Add-Member -NotePropertyName env -NotePropertyValue ([pscustomobject]@{}) }
$server.env | Add-Member -NotePropertyName QDRANT_URL -NotePropertyValue $env:QDRANT_URL -Force
$server.env | Add-Member -NotePropertyName QDRANT_API_KEY -NotePropertyValue $env:QDRANT_READER_KEY -Force
$server.env | Add-Member -NotePropertyName QDRANT_READ_ONLY -NotePropertyValue 'true' -Force
$mcp | ConvertTo-Json -Depth 20 | Set-Content $mcpPath -Encoding utf8
Write-Output 'OK updated mcp.json reader (reload MCP in Cursor)'

$py = Join-Path $Repo '.venv\Scripts\python.exe'
& $py (Join-Path $Repo '2_生產線\homelab\scripts\reader_neg_test.py')
if ($LASTEXITCODE -ne 0) { throw "reader_neg_test failed: $LASTEXITCODE" }

# Ingest second doc if present
$demo = Get-ChildItem 'Z:\jobs' -Directory | Where-Object { $_.Name -like '*-wave1demo' } | Sort-Object Name | Select-Object -Last 1
if ($demo) {
  Write-Output "ingest $($demo.FullName)"
  & $py (Join-Path $Repo '2_生產線\homelab\ingest\ingest.py') --job-dir $demo.FullName
  if ($LASTEXITCODE -ne 0) { throw "ingest failed: $LASTEXITCODE" }
  Write-Output 'idempotent re-ingest'
  & $py (Join-Path $Repo '2_生產線\homelab\ingest\ingest.py') --job-dir $demo.FullName
  if ($LASTEXITCODE -ne 0) { throw "re-ingest failed: $LASTEXITCODE" }
} else {
  Write-Output 'WARN: no *-wave1demo job on Z:'
}

Write-Output 'OK Wave1 A-side finish'
