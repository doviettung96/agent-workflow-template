param(
    [Parameter(Mandatory = $true)][string]$RepoPath,
    [Parameter(Mandatory = $true)][string]$Prefix,
    [switch]$RunSetup,
    [string]$TemplateRoot = (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent)
)

$ErrorActionPreference = "Stop"

& (Join-Path $PSScriptRoot "check-prereqs.ps1")

Write-Host "Repo:   $RepoPath"
Write-Host "Prefix: $Prefix"

$commands = @(
    "bd init -p $Prefix",
    "bd setup codex",
    "bd setup claude --check"
)

if ($RunSetup) {
    Push-Location $RepoPath
    try {
        bd init -p $Prefix
        bd setup codex
        bd setup claude --check
    } finally {
        Pop-Location
    }
} else {
    Write-Host ("Dry run. Commands to execute in {0}:" -f $RepoPath)
    $commands | ForEach-Object { Write-Host "  $_" }
}

& (Join-Path $PSScriptRoot "scaffold-repo-files.ps1") -RepoPath $RepoPath -TemplateRoot $TemplateRoot
Write-Host "Bootstrap complete."
