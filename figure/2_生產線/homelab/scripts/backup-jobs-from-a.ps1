# Wave 1 A-side: pack jobs from Samba Z: into a recovery-point layout.
# Does not need SSH. Pair with B-side qdrant snapshot when SSH is available.
$ErrorActionPreference = 'Stop'
$ShareRoot = if ($env:SHARE_ROOT) { $env:SHARE_ROOT } else { 'Z:\' }
$RpId = if ($env:RP_ID) { $env:RP_ID } else { (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ') }
$JobsSrc = Join-Path $ShareRoot 'jobs'
$JobsDst = Join-Path $ShareRoot "backups\jobs\$RpId"
$RpDir = Join-Path $ShareRoot 'backups\recovery_points'
New-Item -ItemType Directory -Force -Path $JobsDst, $RpDir | Out-Null
$tar = Join-Path $JobsDst 'jobs.tar.gz'
# Prefer tar.exe (Windows 10+)
Push-Location $JobsSrc
try {
  # Exclude .incoming
  & tar.exe -czf $tar --exclude='.incoming' .
} finally {
  Pop-Location
}
if (-not (Test-Path $tar)) { throw "tar failed: $tar" }
$doneCount = (& tar.exe -tzf $tar | Select-String '/DONE.json$' | Measure-Object).Count
$manifest = @{
  rp_id = $RpId
  created_at = (Get-Date).ToUniversalTime().ToString('o')
  jobs_path = $tar.Replace('\','/')
  jobs_done_count = $doneCount
  note = 'A-side jobs pack via Samba; add matching qdrant snapshot under backups/qdrant/<RP_ID>/ on B'
  collection = 'exam_segments_v1'
} | ConvertTo-Json
$rpFile = Join-Path $RpDir "$RpId.json"
Set-Content -Path $rpFile -Value $manifest -Encoding utf8
Write-Output "OK RP_ID=$RpId DONE_in_tar=$doneCount manifest=$rpFile"
