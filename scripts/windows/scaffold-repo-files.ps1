param(
    [Parameter(Mandatory = $true)][string]$RepoPath,
    [string]$Prefix,
    [ValidateSet("", "generic", "game-re")][string]$Profile = "",
    [string]$TemplateRoot = (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent)
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $RepoPath)) {
    throw "RepoPath does not exist: $RepoPath"
}

# Resolve effective profile: CLI flag > persisted profile.json > "generic" default.
$profileFile = Join-Path $RepoPath ".beads\workflow\profile.json"
$effectiveProfile = $Profile
if (-not $effectiveProfile) {
    if (Test-Path $profileFile) {
        try {
            $effectiveProfile = (Get-Content $profileFile -Raw | ConvertFrom-Json).profile
        } catch {
            $effectiveProfile = ""
        }
    }
}
if (-not $effectiveProfile) { $effectiveProfile = "generic" }

# Skills that live in shared skills/ but are profile-gated (not copied to generic repos).
$profileGatedSkills = @("game-action-harness")

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
$posixStatusScript = Join-Path $TemplateRoot "scripts\posix\workflow-status.sh"
$posixAgentMailScript = Join-Path $TemplateRoot "scripts\posix\agent-mail.sh"
$sharedAgentMailScript = Join-Path $TemplateRoot "scripts\shared\agent_mail.py"
$sharedManageInstructionsScript = Join-Path $TemplateRoot "scripts\shared\manage_instructions.py"
$sharedTargetRuntimeScript = Join-Path $TemplateRoot "scripts\shared\target_runtime.py"

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
if (Test-Path $workflowStateSource) {
    Get-ChildItem -Path $workflowStateSource -File | ForEach-Object {
        $destination = Join-Path $workflowDestination $_.Name
        if (-not (Test-Path $destination)) {
            Copy-Item -Force $_.FullName $destination
        }
    }
    Write-Host "Seeded missing .beads/workflow/*"
} else {
    Write-Host "No .beads/workflow seed files in template; skipped"
}

New-Item -ItemType Directory -Force -Path (Join-Path $RepoPath ".codex\skills") | Out-Null
if (-not (Test-Path (Join-Path $RepoPath ".codex\skills\build-and-test"))) {
    Copy-Item -Recurse -Force $codexBuildSkillSource (Join-Path $RepoPath ".codex\skills\build-and-test")
    Write-Host "Copied Codex build-and-test skill"
} else {
    Write-Host "Preserved existing Codex build-and-test skill"
}

Get-ChildItem $skillsSource -Directory | ForEach-Object {
    if ($profileGatedSkills -contains $_.Name -and $effectiveProfile -ne "game-re") {
        Write-Host "Skipped Codex skill (profile=$effectiveProfile): $($_.Name)"
        return
    }
    $destination = Join-Path $RepoPath ".codex\skills\$($_.Name)"
    Remove-Item -Recurse -Force $destination -ErrorAction SilentlyContinue
    Copy-Item -Recurse -Force $_.FullName $destination
    Write-Host "Copied Codex skill: $($_.Name)"
}
Get-ChildItem (Join-Path $TemplateRoot "templates\.codex\skills") -Directory -ErrorAction SilentlyContinue | ForEach-Object {
    if ($_.Name -ne "build-and-test") {
        $destination = Join-Path $RepoPath ".codex\skills\$($_.Name)"
        Remove-Item -Recurse -Force $destination -ErrorAction SilentlyContinue
        Copy-Item -Recurse -Force $_.FullName $destination
        Write-Host "Copied Codex provider skill: $($_.Name)"
    }
}
Remove-Item -Recurse -Force (Join-Path $RepoPath ".codex\skills\start-epic-worktree") -ErrorAction SilentlyContinue

New-Item -ItemType Directory -Force -Path (Join-Path $RepoPath ".claude\skills") | Out-Null
if (-not (Test-Path (Join-Path $RepoPath ".claude\skills\build-and-test"))) {
    Copy-Item -Recurse -Force $codexBuildSkillSource (Join-Path $RepoPath ".claude\skills\build-and-test")
    Write-Host "Copied Claude build-and-test skill"
} else {
    Write-Host "Preserved existing Claude build-and-test skill"
}

Get-ChildItem $skillsSource -Directory | ForEach-Object {
    if ($profileGatedSkills -contains $_.Name -and $effectiveProfile -ne "game-re") {
        Write-Host "Skipped Claude skill (profile=$effectiveProfile): $($_.Name)"
        return
    }
    $destination = Join-Path $RepoPath ".claude\skills\$($_.Name)"
    Remove-Item -Recurse -Force $destination -ErrorAction SilentlyContinue
    Copy-Item -Recurse -Force $_.FullName $destination
    Write-Host "Copied Claude skill: $($_.Name)"
}
Get-ChildItem (Join-Path $TemplateRoot "templates\.claude\skills") -Directory -ErrorAction SilentlyContinue | ForEach-Object {
    if ($_.Name -ne "build-and-test") {
        $destination = Join-Path $RepoPath ".claude\skills\$($_.Name)"
        Remove-Item -Recurse -Force $destination -ErrorAction SilentlyContinue
        Copy-Item -Recurse -Force $_.FullName $destination
        Write-Host "Copied Claude provider skill: $($_.Name)"
    }
}
Remove-Item -Recurse -Force (Join-Path $RepoPath ".claude\skills\start-epic-worktree") -ErrorAction SilentlyContinue

New-Item -ItemType Directory -Force -Path (Join-Path $RepoPath "scripts\windows") | Out-Null
Copy-Item -Force $windowsStatusScript (Join-Path $RepoPath "scripts\windows\workflow-status.ps1")
Copy-Item -Force $windowsAgentMailScript (Join-Path $RepoPath "scripts\windows\agent-mail.ps1")
Remove-Item -Force (Join-Path $RepoPath "scripts\windows\shared-beads.ps1") -ErrorAction SilentlyContinue
Remove-Item -Force (Join-Path $RepoPath "scripts\windows\start-epic-worktree.ps1") -ErrorAction SilentlyContinue
Write-Host "Copied scripts/windows/*"

New-Item -ItemType Directory -Force -Path (Join-Path $RepoPath "scripts\posix") | Out-Null
Copy-Item -Force $posixStatusScript (Join-Path $RepoPath "scripts\posix\workflow-status.sh")
Copy-Item -Force $posixAgentMailScript (Join-Path $RepoPath "scripts\posix\agent-mail.sh")
Remove-Item -Force (Join-Path $RepoPath "scripts\posix\shared-beads.sh") -ErrorAction SilentlyContinue
Remove-Item -Force (Join-Path $RepoPath "scripts\posix\start-epic-worktree.sh") -ErrorAction SilentlyContinue
Write-Host "Copied scripts/posix/*"

New-Item -ItemType Directory -Force -Path (Join-Path $RepoPath "scripts\shared") | Out-Null
Copy-Item -Force $sharedAgentMailScript (Join-Path $RepoPath "scripts\shared\agent_mail.py")
Copy-Item -Force $sharedManageInstructionsScript (Join-Path $RepoPath "scripts\shared\manage_instructions.py")
Copy-Item -Force (Join-Path $TemplateRoot "scripts\shared\run_plan_critic.py") (Join-Path $RepoPath "scripts\shared\run_plan_critic.py")
Copy-Item -Force $sharedTargetRuntimeScript (Join-Path $RepoPath "scripts\shared\target_runtime.py")
Remove-Item -Force (Join-Path $RepoPath "scripts\shared\shared_beads.py") -ErrorAction SilentlyContinue
Remove-Item -Force (Join-Path $RepoPath "scripts\shared\start_epic_worktree.py") -ErrorAction SilentlyContinue
Write-Host "Copied scripts/shared/*"

# Profile-gated: harness runtime installs only for game-re repos.
if ($effectiveProfile -eq "game-re") {
    $harnessSrc = Join-Path $TemplateRoot "scripts\shared\harness.py"
    $harnessBackendsSrc = Join-Path $TemplateRoot "scripts\shared\harness_backends"
    $harnessBackendsDst = Join-Path $RepoPath "scripts\shared\harness_backends"
    Copy-Item -Force $harnessSrc (Join-Path $RepoPath "scripts\shared\harness.py")
    New-Item -ItemType Directory -Force -Path $harnessBackendsDst | Out-Null
    Get-ChildItem $harnessBackendsSrc -File | ForEach-Object {
        Copy-Item -Force $_.FullName (Join-Path $harnessBackendsDst $_.Name)
    }
    Write-Host "Copied scripts/shared/harness.py and harness_backends/ (profile=game-re)"
}

# Persist the effective profile so subsequent runs without -Profile stay consistent.
New-Item -ItemType Directory -Force -Path (Join-Path $RepoPath ".beads\workflow") | Out-Null
$profileJson = @{ version = 1; profile = $effectiveProfile } | ConvertTo-Json -Compress
[System.IO.File]::WriteAllText($profileFile, $profileJson, (New-Object System.Text.UTF8Encoding($false)))
Write-Host "Persisted profile=$effectiveProfile to .beads/workflow/profile.json"

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
