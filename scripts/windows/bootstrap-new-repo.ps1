param(
    [Parameter(Mandatory = $true)][string]$RepoPath,
    [Parameter(Mandatory = $true)][string]$Prefix,
    [string]$TemplateRoot = (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent)
)

$ErrorActionPreference = "Stop"

& (Join-Path $PSScriptRoot "check-prereqs.ps1")

Write-Host "Repo:   $RepoPath"
Write-Host "Prefix: $Prefix"

Push-Location $RepoPath
try {
    bd init -p $Prefix --server --non-interactive --role maintainer --skip-agents --skip-hooks
    bd setup codex
    bd setup claude --check
} finally {
    Pop-Location
}

& (Join-Path $PSScriptRoot "scaffold-repo-files.ps1") -RepoPath $RepoPath -Prefix $Prefix -TemplateRoot $TemplateRoot
Write-Host "Bootstrap complete."
