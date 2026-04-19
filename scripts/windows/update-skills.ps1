param(
    [Parameter(Mandatory = $true)][string]$RepoPath,
    [ValidateSet("", "generic", "game-re")][string]$Profile = "",
    [string]$TemplateRoot = (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent)
)

$ErrorActionPreference = "Stop"

& (Join-Path $PSScriptRoot "check-prereqs.ps1")
& (Join-Path $PSScriptRoot "scaffold-repo-files.ps1") -RepoPath $RepoPath -Profile $Profile -TemplateRoot $TemplateRoot

# Re-run stage-1 bead ensurance so profile=game-re gains its catalog bead idempotently.
$profileArg = $Profile
if (-not $profileArg) {
    $profileFile = Join-Path $RepoPath ".beads\workflow\profile.json"
    if (Test-Path $profileFile) {
        $profileArg = (Get-Content $profileFile -Raw | ConvertFrom-Json).profile
    }
}
if (-not $profileArg) { $profileArg = "generic" }
python (Join-Path $TemplateRoot "scripts\shared\ensure_stage1_beads.py") $RepoPath --profile $profileArg

Write-Host "Skills synced to $RepoPath (profile=$profileArg)"
