param(
    [Parameter(Mandatory = $true)][string]$RepoPath,
    [string]$TemplateRoot = (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent)
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $RepoPath)) {
    throw "RepoPath does not exist: $RepoPath"
}

$workflowSource = Join-Path $TemplateRoot "templates\\BEADS_WORKFLOW.md"
$codexSkillSource = Join-Path $TemplateRoot "templates\\.codex\\skills\\build-and-test"
$skillsSource = Join-Path $TemplateRoot "skills"
$agentsSnippet = Join-Path $TemplateRoot "templates\\AGENTS.snippet.md"
$claudeSnippet = Join-Path $TemplateRoot "templates\\CLAUDE.snippet.md"

Copy-Item -Force $workflowSource (Join-Path $RepoPath "BEADS_WORKFLOW.md")
Write-Host "Copied BEADS_WORKFLOW.md"

# Ensure .beads/dolt/ is tracked by git (bd init ignores it by default)
$beadsGitignore = Join-Path $RepoPath ".beads\\.gitignore"
if (Test-Path $beadsGitignore) {
    $content = Get-Content $beadsGitignore -Raw
    if ($content -match '(?m)^dolt/$') {
        $content = $content -replace '(?m)^# Dolt database \(managed by Dolt, not git\)\r?\n', ''
        $content = $content -replace '(?m)^dolt/\r?\n', ''
        Set-Content -Path $beadsGitignore -Value $content.TrimEnd()
        Write-Host "Removed dolt/ from .beads/.gitignore (tracked by git for worktree support)"
    }
}

# Codex skills: copy all skills + build-and-test into .codex/skills/
New-Item -ItemType Directory -Force -Path (Join-Path $RepoPath ".codex\\skills") | Out-Null
Copy-Item -Recurse -Force $codexSkillSource (Join-Path $RepoPath ".codex\\skills\\build-and-test")
Write-Host "Copied Codex build-and-test skill"

Get-ChildItem $skillsSource -Directory | ForEach-Object {
    $destination = Join-Path $RepoPath ".codex\\skills\\$($_.Name)"
    Copy-Item -Recurse -Force $_.FullName $destination
    Write-Host "Copied Codex skill: $($_.Name)"
}

# Claude skills: copy all skills into .claude/skills/
New-Item -ItemType Directory -Force -Path (Join-Path $RepoPath ".claude\\skills") | Out-Null
Get-ChildItem $skillsSource -Directory | ForEach-Object {
    $destination = Join-Path $RepoPath ".claude\\skills\\$($_.Name)"
    Copy-Item -Recurse -Force $_.FullName $destination
    Write-Host "Copied Claude skill: $($_.Name)"
}

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
