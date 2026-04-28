param(
    [Parameter(Mandatory = $true)][string]$RepoPath,
    [string]$Prefix,
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
    throw "Python is required for migrate-downstream-to-br.ps1 but was not found on PATH."
}

& (Join-Path $PSScriptRoot "check-prereqs.ps1")
if (-not (Get-Command bd -ErrorAction SilentlyContinue)) {
    throw "bd is required for migrate-downstream-to-br.ps1 but was not found on PATH."
}

$python = Find-Python
$scriptPath = Join-Path $TemplateRoot "scripts\shared\migrate_bd_to_br.py"
$dedupePath = Join-Path $TemplateRoot "scripts\shared\dedupe_stage1_beads.py"
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

$updateArgs = @{ RepoPath = $RepoPath; TemplateRoot = $TemplateRoot }
if ($Profile) {
    $updateArgs.Profile = $Profile
}
& (Join-Path $PSScriptRoot "update-skills.ps1") @updateArgs

if ($python -eq "py") {
    & py -3 $dedupePath --repo $RepoPath
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} else {
    & $python $dedupePath --repo $RepoPath
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

Push-Location $RepoPath
try {
    br list --json --no-db | Out-Null
} finally {
    Pop-Location
}

Write-Host "Migrated $RepoPath to br --no-db"
