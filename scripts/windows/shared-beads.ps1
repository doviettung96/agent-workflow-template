param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ArgsList
)

$ErrorActionPreference = "Stop"

function Find-Python {
    foreach ($candidate in @("py", "python", "python3")) {
        $command = Get-Command $candidate -ErrorAction SilentlyContinue
        if ($command) {
            return $candidate
        }
    }
    throw "Python is required for shared-beads.ps1 but was not found on PATH."
}

$python = Find-Python
$scriptPath = Join-Path (Split-Path $PSScriptRoot -Parent) "shared\shared_beads.py"

if ($python -eq "py") {
    & py -3 $scriptPath @ArgsList
    exit $LASTEXITCODE
}

& $python $scriptPath @ArgsList
exit $LASTEXITCODE
