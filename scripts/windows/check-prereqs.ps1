param(
    [switch]$RequireCodex
)

$ErrorActionPreference = "Stop"

function Test-Command {
    param([Parameter(Mandatory = $true)][string]$Name)
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

$missing = @()
foreach ($cmd in @("git", "bd", "dolt")) {
    if (-not (Test-Command -Name $cmd)) {
        $missing += $cmd
    }
}

if ($RequireCodex -and -not (Test-Command -Name "codex")) {
    Write-Warning "codex is not on PATH"
}

if (-not (Test-Command -Name "py") -and -not (Test-Command -Name "python") -and -not (Test-Command -Name "python3")) {
    $missing += "python"
}

if ($missing.Count -gt 0) {
    Write-Error ("Missing required commands: " + ($missing -join ", "))
}

Write-Host "Required commands found: git, bd, dolt, python"
