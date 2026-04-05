param(
    [Parameter(Mandatory = $true)][string]$RepoPath,
    [string]$Prefix,
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
    throw "Python is required for migrate-downstream-to-bd.ps1 but was not found on PATH."
}

& (Join-Path $PSScriptRoot "check-prereqs.ps1")

$python = Find-Python
$scriptPath = Join-Path $TemplateRoot "scripts\shared\migrate_br_to_bd.py"
$argsList = @("--repo", $RepoPath)
if ($Prefix) {
    $argsList += @("--prefix", $Prefix)
}

if ($python -eq "py") {
    & py -3 $scriptPath @argsList
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} else {
    & $python $scriptPath @argsList
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

& (Join-Path $PSScriptRoot "scaffold-repo-files.ps1") -RepoPath $RepoPath -Prefix $Prefix -TemplateRoot $TemplateRoot

Push-Location $RepoPath
try {
    bd list --json | Out-Null
} finally {
    Pop-Location
}

Write-Host "Migrated $RepoPath to bd/local Dolt"
