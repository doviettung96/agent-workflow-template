param(
    [Parameter(Mandatory = $true)][string]$RepoPath,
    [Parameter(Mandatory = $true)][string]$Prefix,
    [ValidateSet("generic", "game-re")][string]$Profile = "generic",
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

Write-Host "Repo:    $RepoPath"
Write-Host "Prefix:  $Prefix"
Write-Host "Profile: $Profile"

Push-Location $RepoPath
try {
    br init --prefix $Prefix --no-db
    Get-ChildItem -Path ".beads" -Filter "beads.db*" -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
    br config set issue_prefix $Prefix --no-db
    br agents --add --force --no-db
} finally {
    Pop-Location
}

& (Join-Path $PSScriptRoot "scaffold-repo-files.ps1") -RepoPath $RepoPath -Prefix $Prefix -Profile $Profile -TemplateRoot $TemplateRoot
python (Join-Path $TemplateRoot "scripts\shared\ensure_stage1_beads.py") $RepoPath --profile $Profile
Write-Host "Bootstrap complete."
