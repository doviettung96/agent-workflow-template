param(
    [Parameter(Mandatory = $true)][string]$RepoPath,
    [string]$TemplateRoot = (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent)
)

$ErrorActionPreference = "Stop"

& (Join-Path $PSScriptRoot "check-prereqs.ps1")
& (Join-Path $PSScriptRoot "scaffold-repo-files.ps1") -RepoPath $RepoPath -TemplateRoot $TemplateRoot
Write-Host "Skills synced to $RepoPath"
