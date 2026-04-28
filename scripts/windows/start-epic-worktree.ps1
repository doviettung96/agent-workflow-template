param(
    [Parameter(Mandatory = $true)][string]$EpicId,
    [string]$WorktreePath = "",
    [string]$Branch = "",
    [string]$BaseRef = "HEAD",
    [string]$RepoPath = "."
)

$ErrorActionPreference = "Stop"

function Find-Python {
    foreach ($candidate in @("py", "python", "python3")) {
        $command = Get-Command $candidate -ErrorAction SilentlyContinue
        if ($command) {
            return $candidate
        }
    }
    throw "Python is required for start-epic-worktree.ps1"
}

$python = Find-Python
$scriptPath = Join-Path $PSScriptRoot "..\shared\start_epic_worktree.py"
$argsList = @("--source-repo", $RepoPath, "--epic-id", $EpicId, "--base-ref", $BaseRef)
if ($WorktreePath) {
    $argsList += @("--worktree-path", $WorktreePath)
}
if ($Branch) {
    $argsList += @("--branch", $Branch)
}

if ($python -eq "py") {
    & py -3 $scriptPath @argsList
} else {
    & $python $scriptPath @argsList
}
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
