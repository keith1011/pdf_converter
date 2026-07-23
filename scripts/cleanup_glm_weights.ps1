<#
.SYNOPSIS
    Lists or removes the Hugging Face cache entry for GLM-4.6V-Flash.

.DESCRIPTION
    The script is a dry run unless -Confirm is passed. It targets only
    zai-org/GLM-4.6V-Flash, never the full Hugging Face cache.
#>
[CmdletBinding()]
param(
    [switch]$Confirm
)

$modelId = "zai-org/GLM-4.6V-Flash"
$cacheRoot = if ($env:HF_HUB_CACHE) {
    $env:HF_HUB_CACHE
} elseif ($env:HF_HOME) {
    Join-Path $env:HF_HOME "hub"
} else {
    Join-Path $env:USERPROFILE ".cache\huggingface\hub"
}

$modelCachePath = Join-Path $cacheRoot "models--zai-org--GLM-4.6V-Flash"

if (-not (Test-Path -LiteralPath $modelCachePath)) {
    Write-Host "No cached weights found for $modelId."
    Write-Host "Target path: $modelCachePath"
    exit 0
}

if (-not $Confirm) {
    Write-Host "Dry run: would delete cached weights for $modelId only:"
    Write-Host "  $modelCachePath"
    Write-Host "Run with -Confirm to delete this path."
    exit 0
}

Write-Host "Deleting cached weights for $modelId only:"
Write-Host "  $modelCachePath"
Remove-Item -LiteralPath $modelCachePath -Recurse -Force
Write-Host "Deleted $modelCachePath"
