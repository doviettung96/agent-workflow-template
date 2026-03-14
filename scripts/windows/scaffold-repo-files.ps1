param(
    [Parameter(Mandatory = $true)][string]$RepoPath,
    [string]$TemplateRoot = (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent)
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $RepoPath)) {
    throw "RepoPath does not exist: $RepoPath"
}

$workflowSource = Join-Path $TemplateRoot "templates\\BEADS_WORKFLOW.md"
$agentsSnippet = Join-Path $TemplateRoot "templates\\AGENTS.snippet.md"
$claudeSnippet = Join-Path $TemplateRoot "templates\\CLAUDE.snippet.md"

Copy-Item -Force $workflowSource (Join-Path $RepoPath "BEADS_WORKFLOW.md")
Write-Host "Copied BEADS_WORKFLOW.md"

function Add-Snippet {
    param(
        [Parameter(Mandatory = $true)][string]$TargetPath,
        [Parameter(Mandatory = $true)][string]$SnippetPath,
        [Parameter(Mandatory = $true)][string]$Sentinel
    )

    $snippet = Get-Content $SnippetPath -Raw
    if (Test-Path $TargetPath) {
        $content = Get-Content $TargetPath -Raw
        if ($content -match '<!-- BEGIN BEADS INTEGRATION -->' -and $content -match '<!-- END BEADS INTEGRATION -->') {
            Write-Host "Beads-managed block detected in $TargetPath; appending only outside managed content."
        }
        if ($content.Contains($Sentinel)) {
            Write-Host "Snippet already present in $TargetPath"
            return
        }
        Add-Content -Path $TargetPath -Value ("`r`n`r`n" + $snippet)
        Write-Host "Appended snippet to $TargetPath"
        return
    }

    Set-Content -Path $TargetPath -Value $snippet
    Write-Host "Created $TargetPath"
}

Add-Snippet -TargetPath (Join-Path $RepoPath "AGENTS.md") -SnippetPath $agentsSnippet -Sentinel "BEADS_WORKFLOW.md"
Add-Snippet -TargetPath (Join-Path $RepoPath "CLAUDE.md") -SnippetPath $claudeSnippet -Sentinel "Uses `bd` (beads/Dolt)."
