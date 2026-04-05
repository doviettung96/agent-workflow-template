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

function Get-RepoPrefix {
    param(
        [Parameter(Mandatory = $true)][string]$RepoPath,
        [string]$ExplicitPrefix
    )

    if ($ExplicitPrefix) {
        return $ExplicitPrefix
    }

    $configPath = Join-Path $RepoPath ".beads\config.yaml"
    if (Test-Path $configPath) {
        $match = Select-String -Path $configPath -Pattern '^\s*issue_prefix:\s*"?([^"#]+)"?' | Select-Object -First 1
        if ($match) {
            return $match.Matches[0].Groups[1].Value.Trim()
        }
    }

    return (Split-Path $RepoPath -Leaf).ToLowerInvariant()
}

function Write-BrConfig {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$ResolvedPrefix
    )

    @"
# Beads Project Configuration
issue_prefix: $ResolvedPrefix
no-db: false
"@ | Set-Content -Path $Path -Encoding UTF8
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
$windowsSharedBeadsScript = Join-Path $TemplateRoot "scripts\windows\shared-beads.ps1"
$windowsStartEpicWorktreeScript = Join-Path $TemplateRoot "scripts\windows\start-epic-worktree.ps1"
$posixStatusScript = Join-Path $TemplateRoot "scripts\posix\workflow-status.sh"
$posixAgentMailScript = Join-Path $TemplateRoot "scripts\posix\agent-mail.sh"
$posixSharedBeadsScript = Join-Path $TemplateRoot "scripts\posix\shared-beads.sh"
$posixStartEpicWorktreeScript = Join-Path $TemplateRoot "scripts\posix\start-epic-worktree.sh"
$sharedAgentMailScript = Join-Path $TemplateRoot "scripts\shared\agent_mail.py"
$sharedBeadsScript = Join-Path $TemplateRoot "scripts\shared\shared_beads.py"
$sharedStartEpicWorktreeScript = Join-Path $TemplateRoot "scripts\shared\start_epic_worktree.py"
$sharedManageInstructionsScript = Join-Path $TemplateRoot "scripts\shared\manage_instructions.py"
$resolvedPrefix = Get-RepoPrefix -RepoPath $RepoPath -ExplicitPrefix $Prefix

Copy-Item -Force $workflowSource (Join-Path $RepoPath "BEADS_WORKFLOW.md")
Write-Host "Copied BEADS_WORKFLOW.md"

$beadsDir = Join-Path $RepoPath ".beads"
if (Test-Path $beadsDir) {
    Copy-Item -Force (Join-Path $TemplateRoot "templates\PRIME.md") (Join-Path $beadsDir "PRIME.md")
    Copy-Item -Force (Join-Path $TemplateRoot "templates\.beads\.gitignore") (Join-Path $beadsDir ".gitignore")
    Copy-Item -Force (Join-Path $TemplateRoot "templates\.beads\metadata.json") (Join-Path $beadsDir "metadata.json")
    Copy-Item -Force (Join-Path $TemplateRoot "templates\.beads\README.md") (Join-Path $beadsDir "README.md")
    Write-BrConfig -Path (Join-Path $beadsDir "config.yaml") -ResolvedPrefix $resolvedPrefix
    if (-not (Test-Path (Join-Path $beadsDir "issues.jsonl"))) {
        Set-Content -Path (Join-Path $beadsDir "issues.jsonl") -Value "" -Encoding UTF8
    }
    Write-Host "Copied .beads/PRIME.md"
    Write-Host "Copied .beads/.gitignore"
    Write-Host "Copied .beads/metadata.json"
    Write-Host "Copied .beads/README.md"
    Write-Host "Updated .beads/config.yaml"

    $workflowDestination = Join-Path $beadsDir "workflow"
    New-Item -ItemType Directory -Force -Path $workflowDestination | Out-Null
    Get-ChildItem -Path $workflowStateSource -File | ForEach-Object {
        $destination = Join-Path $workflowDestination $_.Name
        if (-not (Test-Path $destination)) {
            Copy-Item -Force $_.FullName $destination
        }
    }
    Write-Host "Seeded missing .beads/workflow/*"
}

New-Item -ItemType Directory -Force -Path (Join-Path $RepoPath ".codex\skills") | Out-Null
Remove-Item -Recurse -Force (Join-Path $RepoPath ".codex\skills\build-and-test") -ErrorAction SilentlyContinue
Copy-Item -Recurse -Force $codexBuildSkillSource (Join-Path $RepoPath ".codex\skills\build-and-test")
Write-Host "Copied Codex build-and-test skill"

Get-ChildItem $skillsSource -Directory | ForEach-Object {
    $destination = Join-Path $RepoPath ".codex\skills\$($_.Name)"
    Remove-Item -Recurse -Force $destination -ErrorAction SilentlyContinue
    Copy-Item -Recurse -Force $_.FullName $destination
    Write-Host "Copied Codex skill: $($_.Name)"
}

New-Item -ItemType Directory -Force -Path (Join-Path $RepoPath ".claude\skills") | Out-Null
Get-ChildItem $skillsSource -Directory | ForEach-Object {
    $destination = Join-Path $RepoPath ".claude\skills\$($_.Name)"
    Remove-Item -Recurse -Force $destination -ErrorAction SilentlyContinue
    Copy-Item -Recurse -Force $_.FullName $destination
    Write-Host "Copied Claude skill: $($_.Name)"
}

New-Item -ItemType Directory -Force -Path (Join-Path $RepoPath "scripts\windows") | Out-Null
Copy-Item -Force $windowsStatusScript (Join-Path $RepoPath "scripts\windows\workflow-status.ps1")
Write-Host "Copied scripts/windows/workflow-status.ps1"
Copy-Item -Force $windowsAgentMailScript (Join-Path $RepoPath "scripts\windows\agent-mail.ps1")
Write-Host "Copied scripts/windows/agent-mail.ps1"
Copy-Item -Force $windowsSharedBeadsScript (Join-Path $RepoPath "scripts\windows\shared-beads.ps1")
Write-Host "Copied scripts/windows/shared-beads.ps1"
Copy-Item -Force $windowsStartEpicWorktreeScript (Join-Path $RepoPath "scripts\windows\start-epic-worktree.ps1")
Write-Host "Copied scripts/windows/start-epic-worktree.ps1"

New-Item -ItemType Directory -Force -Path (Join-Path $RepoPath "scripts\posix") | Out-Null
Copy-Item -Force $posixStatusScript (Join-Path $RepoPath "scripts\posix\workflow-status.sh")
Write-Host "Copied scripts/posix/workflow-status.sh"
Copy-Item -Force $posixAgentMailScript (Join-Path $RepoPath "scripts\posix\agent-mail.sh")
Write-Host "Copied scripts/posix/agent-mail.sh"
Copy-Item -Force $posixSharedBeadsScript (Join-Path $RepoPath "scripts\posix\shared-beads.sh")
Write-Host "Copied scripts/posix/shared-beads.sh"
Copy-Item -Force $posixStartEpicWorktreeScript (Join-Path $RepoPath "scripts\posix\start-epic-worktree.sh")
Write-Host "Copied scripts/posix/start-epic-worktree.sh"

New-Item -ItemType Directory -Force -Path (Join-Path $RepoPath "scripts\shared") | Out-Null
Copy-Item -Force $sharedAgentMailScript (Join-Path $RepoPath "scripts\shared\agent_mail.py")
Copy-Item -Force $sharedBeadsScript (Join-Path $RepoPath "scripts\shared\shared_beads.py")
Copy-Item -Force $sharedStartEpicWorktreeScript (Join-Path $RepoPath "scripts\shared\start_epic_worktree.py")
Copy-Item -Force $sharedManageInstructionsScript (Join-Path $RepoPath "scripts\shared\manage_instructions.py")
Write-Host "Copied scripts/shared/agent_mail.py"
Write-Host "Copied scripts/shared/shared_beads.py"
Write-Host "Copied scripts/shared/start_epic_worktree.py"
Write-Host "Copied scripts/shared/manage_instructions.py"

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

$sharedBeadsDestination = Join-Path $RepoPath "scripts\windows\shared-beads.ps1"
& $sharedBeadsDestination --repo $RepoPath attach | Out-Null
Write-Host "Attached checkout to shared live Beads store"
