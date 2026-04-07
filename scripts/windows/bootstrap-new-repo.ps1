param(
    [Parameter(Mandatory = $true)][string]$RepoPath,
    [Parameter(Mandatory = $true)][string]$Prefix,
    [string]$TemplateRoot = (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent)
)

$ErrorActionPreference = "Stop"

& (Join-Path $PSScriptRoot "check-prereqs.ps1")

if (-not (Test-Path $RepoPath)) {
    New-Item -ItemType Directory -Path $RepoPath | Out-Null
}

if (-not (Test-Path (Join-Path $RepoPath ".git"))) {
    git -C $RepoPath init | Out-Null
    Write-Host "Initialized git repository"
}

Write-Host "Repo:   $RepoPath"
Write-Host "Prefix: $Prefix"

Push-Location $RepoPath
try {
    bd init -p $Prefix --server --skip-agents --skip-hooks
    bd setup codex
} finally {
    Pop-Location
}

& (Join-Path $PSScriptRoot "scaffold-repo-files.ps1") -RepoPath $RepoPath -Prefix $Prefix -TemplateRoot $TemplateRoot
python (Join-Path $TemplateRoot "scripts\shared\ensure_stage1_beads.py") $RepoPath
Write-Host "Bootstrap complete."
