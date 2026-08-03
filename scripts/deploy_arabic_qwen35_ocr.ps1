# Deploy Arabic-Qwen3.5-OCR-v4 into an isolated venv (transformers 5.x).
# Does not modify main .venv / DSE trunk.
param(
    [switch]$SkipSmoke
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Venv = Join-Path $Root ".venv-arabic-ocr"
$Req = Join-Path $Root "requirements-arabic-qwen35-ocr.txt"
$Py = Join-Path $Venv "Scripts\python.exe"
$TorchIndex = "https://download.pytorch.org/whl/cu126"

Write-Host "[deploy] root=$Root"
Write-Host "[deploy] NOTE: Arabic OCR specialty (Qwen3.5-0.8B) — not CJK/DSE trunk."
Write-Host "[deploy] Isolated venv (transformers>=5.3 vs trunk <5)."

if (-not (Test-Path $Py)) {
    Write-Host "[deploy] Creating $Venv ..."
    uv venv $Venv --python 3.12
}

Write-Host "[deploy] Installing torch (cu126) ..."
# Force CUDA build — default PyPI torch is often CPU-only on Windows.
uv pip uninstall --python $Py torch torchvision 2>$null
uv pip install torch torchvision --python $Py --index-url $TorchIndex

Write-Host "[deploy] Installing transformers 5.x + OCR deps ..."
uv pip install -r $Req --python $Py
# Re-assert CUDA torch in case a dep pulled CPU wheels.
uv pip install torch torchvision --python $Py --index-url $TorchIndex --reinstall-package torch --reinstall-package torchvision

if (-not $SkipSmoke) {
    Write-Host "[deploy] Running smoke ..."
    & $Py (Join-Path $Root "scripts\smoke_arabic_qwen35_ocr.py")
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
Write-Host "[deploy] Done. Python: $Py"
