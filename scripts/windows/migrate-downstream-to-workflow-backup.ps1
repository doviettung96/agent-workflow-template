param(
    [Parameter(Mandatory = $true)][string]$RepoPath,
    [string]$BackupRepo,
    [string]$ProjectName,
    [ValidateSet("", "generic", "game-re")][string]$Profile = "",
    [string]$TemplateRoot = (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent)
)

$ErrorActionPreference = "Stop"

function Find-Python {
    foreach ($candidate in @("py", "python", "python3")) {
        $command = Get-Command $candidate -ErrorAction SilentlyContinue
        if ($command) {
            return $candidate
        }
    }
    throw "Python is required for migrate-downstream-to-workflow-backup.ps1"
}

& (Join-Path $PSScriptRoot "check-prereqs.ps1")

$updateArgs = @{
    RepoPath = $RepoPath
    TemplateRoot = $TemplateRoot
}
if ($Profile) {
    $updateArgs.Profile = $Profile
}
& (Join-Path $PSScriptRoot "update-skills.ps1") @updateArgs

$python = Find-Python
$scriptPath = Join-Path $TemplateRoot "scripts\shared\migrate_downstream_to_workflow_backup.py"
$argsList = @("--repo", $RepoPath)
if ($BackupRepo) {
    $argsList += @("--backup-repo", $BackupRepo)
}
if ($ProjectName) {
    $argsList += @("--project-name", $ProjectName)
}

if ($python -eq "py") {
    & py -3 $scriptPath @argsList
} else {
    & $python $scriptPath @argsList
}
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Migrated workflow files in $RepoPath to local-only plus backup mirror sync"
