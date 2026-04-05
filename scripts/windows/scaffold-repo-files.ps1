param(
    [Parameter(Mandatory = $true)][string]$RepoPath,
    [string]$Prefix,
    [string]$TemplateRoot = (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent)
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $RepoPath)) {
    throw "RepoPath does not exist: $RepoPath"
}

function Get-PythonCommand {
    foreach ($cmd in @("py", "python", "python3")) {
        $resolved = Get-Command $cmd -ErrorAction SilentlyContinue
        if ($resolved) {
            return $cmd
        }
    }
    throw "Python is required for scaffold-repo-files.ps1"
}

$pythonCmd = Get-PythonCommand
$workflowSource = Join-Path $TemplateRoot "templates\BEADS_WORKFLOW.md"
$workflowStateSource = Join-Path $TemplateRoot "templates\.beads\workflow"
$troubleshootingSource = Join-Path $TemplateRoot "docs\TROUBLESHOOTING.md"
$codexBuildSkillSource = Join-Path $TemplateRoot "templates\.codex\skills\build-and-test"
$skillsSource = Join-Path $TemplateRoot "skills"
$agentsSnippet = Join-Path $TemplateRoot "templates\AGENTS.snippet.md"
$claudeSnippet = Join-Path $TemplateRoot "templates\CLAUDE.snippet.md"
$windowsStatusScript = Join-Path $TemplateRoot "scripts\windows\workflow-status.ps1"
$windowsAgentMailScript = Join-Path $TemplateRoot "scripts\windows\agent-mail.ps1"
$windowsStartEpicWorktreeScript = Join-Path $TemplateRoot "scripts\windows\start-epic-worktree.ps1"
$posixStatusScript = Join-Path $TemplateRoot "scripts\posix\workflow-status.sh"
$posixAgentMailScript = Join-Path $TemplateRoot "scripts\posix\agent-mail.sh"
$posixStartEpicWorktreeScript = Join-Path $TemplateRoot "scripts\posix\start-epic-worktree.sh"
$sharedAgentMailScript = Join-Path $TemplateRoot "scripts\shared\agent_mail.py"
$sharedStartEpicWorktreeScript = Join-Path $TemplateRoot "scripts\shared\start_epic_worktree.py"
$sharedManageInstructionsScript = Join-Path $TemplateRoot "scripts\shared\manage_instructions.py"

Copy-Item -Force $workflowSource (Join-Path $RepoPath "BEADS_WORKFLOW.md")
Write-Host "Copied BEADS_WORKFLOW.md"

$beadsDir = Join-Path $RepoPath ".beads"
New-Item -ItemType Directory -Force -Path $beadsDir | Out-Null
Copy-Item -Force (Join-Path $TemplateRoot "templates\PRIME.md") (Join-Path $beadsDir "PRIME.md")
Copy-Item -Force (Join-Path $TemplateRoot "templates\.beads\.gitignore") (Join-Path $beadsDir ".gitignore")
Copy-Item -Force (Join-Path $TemplateRoot "templates\.beads\README.md") (Join-Path $beadsDir "README.md")
Write-Host "Copied .beads/PRIME.md"
Write-Host "Copied .beads/.gitignore"
Write-Host "Copied .beads/README.md"

$workflowDestination = Join-Path $beadsDir "workflow"
New-Item -ItemType Directory -Force -Path $workflowDestination | Out-Null
Get-ChildItem -Path $workflowStateSource -File | ForEach-Object {
    $destination = Join-Path $workflowDestination $_.Name
    if (-not (Test-Path $destination)) {
        Copy-Item -Force $_.FullName $destination
    }
}
Write-Host "Seeded missing .beads/workflow/*"

New-Item -ItemType Directory -Force -Path (Join-Path $RepoPath ".codex\skills") | Out-Null
if (-not (Test-Path (Join-Path $RepoPath ".codex\skills\build-and-test"))) {
    Copy-Item -Recurse -Force $codexBuildSkillSource (Join-Path $RepoPath ".codex\skills\build-and-test")
    Write-Host "Copied Codex build-and-test skill"
} else {
    Write-Host "Preserved existing Codex build-and-test skill"
}

Get-ChildItem $skillsSource -Directory | ForEach-Object {
    $destination = Join-Path $RepoPath ".codex\skills\$($_.Name)"
    Remove-Item -Recurse -Force $destination -ErrorAction SilentlyContinue
    Copy-Item -Recurse -Force $_.FullName $destination
    Write-Host "Copied Codex skill: $($_.Name)"
}

New-Item -ItemType Directory -Force -Path (Join-Path $RepoPath ".claude\skills") | Out-Null
if (-not (Test-Path (Join-Path $RepoPath ".claude\skills\build-and-test"))) {
    Copy-Item -Recurse -Force $codexBuildSkillSource (Join-Path $RepoPath ".claude\skills\build-and-test")
    Write-Host "Copied Claude build-and-test skill"
} else {
    Write-Host "Preserved existing Claude build-and-test skill"
}

Get-ChildItem $skillsSource -Directory | ForEach-Object {
    $destination = Join-Path $RepoPath ".claude\skills\$($_.Name)"
    Remove-Item -Recurse -Force $destination -ErrorAction SilentlyContinue
    Copy-Item -Recurse -Force $_.FullName $destination
    Write-Host "Copied Claude skill: $($_.Name)"
}

New-Item -ItemType Directory -Force -Path (Join-Path $RepoPath "scripts\windows") | Out-Null
Copy-Item -Force $windowsStatusScript (Join-Path $RepoPath "scripts\windows\workflow-status.ps1")
Copy-Item -Force $windowsAgentMailScript (Join-Path $RepoPath "scripts\windows\agent-mail.ps1")
Copy-Item -Force $windowsStartEpicWorktreeScript (Join-Path $RepoPath "scripts\windows\start-epic-worktree.ps1")
Remove-Item -Force (Join-Path $RepoPath "scripts\windows\shared-beads.ps1") -ErrorAction SilentlyContinue
Write-Host "Copied scripts/windows/*"

New-Item -ItemType Directory -Force -Path (Join-Path $RepoPath "scripts\posix") | Out-Null
Copy-Item -Force $posixStatusScript (Join-Path $RepoPath "scripts\posix\workflow-status.sh")
Copy-Item -Force $posixAgentMailScript (Join-Path $RepoPath "scripts\posix\agent-mail.sh")
Copy-Item -Force $posixStartEpicWorktreeScript (Join-Path $RepoPath "scripts\posix\start-epic-worktree.sh")
Remove-Item -Force (Join-Path $RepoPath "scripts\posix\shared-beads.sh") -ErrorAction SilentlyContinue
Write-Host "Copied scripts/posix/*"

New-Item -ItemType Directory -Force -Path (Join-Path $RepoPath "scripts\shared") | Out-Null
Copy-Item -Force $sharedAgentMailScript (Join-Path $RepoPath "scripts\shared\agent_mail.py")
Copy-Item -Force $sharedStartEpicWorktreeScript (Join-Path $RepoPath "scripts\shared\start_epic_worktree.py")
Copy-Item -Force $sharedManageInstructionsScript (Join-Path $RepoPath "scripts\shared\manage_instructions.py")
Remove-Item -Force (Join-Path $RepoPath "scripts\shared\shared_beads.py") -ErrorAction SilentlyContinue
Write-Host "Copied scripts/shared/*"

New-Item -ItemType Directory -Force -Path (Join-Path $RepoPath "docs") | Out-Null
Copy-Item -Force $troubleshootingSource (Join-Path $RepoPath "docs\TROUBLESHOOTING.md")
Write-Host "Copied docs/TROUBLESHOOTING.md"

if ($pythonCmd -eq "py") {
    & py -3 $sharedManageInstructionsScript (Join-Path $RepoPath "AGENTS.md") $agentsSnippet
    & py -3 $sharedManageInstructionsScript (Join-Path $RepoPath "CLAUDE.md") $claudeSnippet
} else {
    & $pythonCmd $sharedManageInstructionsScript (Join-Path $RepoPath "AGENTS.md") $agentsSnippet
    & $pythonCmd $sharedManageInstructionsScript (Join-Path $RepoPath "CLAUDE.md") $claudeSnippet
}
Write-Host "Updated AGENTS.md managed block"
Write-Host "Updated CLAUDE.md managed block"
