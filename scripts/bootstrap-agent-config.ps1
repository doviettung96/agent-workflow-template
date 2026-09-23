<#
.SYNOPSIS
  Distribute the global agent guidelines (this repo's AGENTS.md) and init LESSONS.md.

  Requires either Developer Mode ON or an elevated shell (symlink creation). With
  Developer Mode on, run from a normal, non-elevated shell.

.DESCRIPTION
  The repo's AGENTS.md is the single source of truth for general guidelines. This script
  symlinks the global instruction files to it and initializes lessons stores. Projects
  need no link: Claude Code and Codex both read a project's AGENTS.md as is. It NEVER
  creates or edits a project's own AGENTS.md - that is the project's responsibility.

  Symlinks need an elevated shell on Windows unless Developer Mode is on.

.EXAMPLE
  # Once per machine:
  Start-Process powershell -Verb RunAs -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File','D:\Projects\game-reverse\agent-workflow-template\scripts\bootstrap-agent-config.ps1','-Global'

.EXAMPLE
  # Per project:
  ... '-File','...\bootstrap-agent-config.ps1','-ProjectPath','D:\Projects\foo'
#>
param(
  [switch]$Global,
  [string]$ProjectPath
)
$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
$master   = Join-Path $repoRoot 'AGENTS.md'
if (-not (Test-Path -LiteralPath $master)) { throw "Master AGENTS.md not found: $master" }

if (-not $Global -and -not $ProjectPath) {
  throw "Nothing to do. Pass -Global and/or -ProjectPath <repo>."
}

$lessonsTemplate = @'
# Lessons Learned

Gotchas worth never hitting twice. Read before debugging (grep by error text or tag);
append after resolving a non-obvious error. One atomic entry each, newest on top.

Format:
```
### <one-line title>
- Date: YYYY-MM-DD
- Symptom: what was observed (paste the actual error text)
- Root cause: why it really happened
- Rule: what to do - and what never to do again
- Tags: #build #windows #flaky #async ...
```

---

<!-- Add lessons below this line -->
'@

function New-Symlink([string]$Link, [string]$Target) {
  $dir = Split-Path -Parent $Link
  if ($dir -and -not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Force $dir | Out-Null }
  if (Test-Path -LiteralPath $Link) { Remove-Item -LiteralPath $Link -Force }
  New-Item -ItemType SymbolicLink -Path $Link -Target $Target | Out-Null
  Write-Host "  linked  $Link  ->  $Target"
}

function New-LessonsIfMissing([string]$Path) {
  if (Test-Path -LiteralPath $Path) { Write-Host "  kept    $Path (exists)"; return }
  $dir = Split-Path -Parent $Path
  if ($dir -and -not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Force $dir | Out-Null }
  Set-Content -LiteralPath $Path -Value $lessonsTemplate -Encoding utf8
  Write-Host "  created $Path"
}

if ($Global) {
  Write-Host "Global setup:"
  # Each agent's global instruction file links straight to the master. Add more agents here.
  $globalLinks = @(
    (Join-Path $HOME '.claude\CLAUDE.md'),  # Claude Code
    (Join-Path $HOME '.codex\AGENTS.md')    # Codex
    # (Join-Path $HOME '.gemini\GEMINI.md') # example: another agent
  )
  foreach ($link in $globalLinks) { New-Symlink $link $master }
  New-LessonsIfMissing (Join-Path $HOME '.agents\LESSONS.md')
}

if ($ProjectPath) {
  $proj = [System.IO.Path]::GetFullPath($ProjectPath)
  if (-not (Test-Path -LiteralPath $proj)) { throw "Project path not found: $proj" }
  Write-Host "Project setup: $proj"
  New-LessonsIfMissing (Join-Path $proj 'LESSONS.md')
  # Claude Code reads a project's AGENTS.md natively, but only when no CLAUDE.md sits next
  # to it: a CLAUDE.md shadows AGENTS.md. So a CLAUDE.md -> AGENTS.md link is redundant;
  # remove the ones older versions of this script created, and flag a real CLAUDE.md.
  $projClaude = Join-Path $proj 'CLAUDE.md'
  $item = Get-Item -LiteralPath $projClaude -Force -ErrorAction SilentlyContinue
  if ($item -and $item.LinkType -eq 'SymbolicLink' -and $item.Target -eq 'AGENTS.md') {
    Remove-Item -LiteralPath $projClaude -Force
    Write-Host "  removed $projClaude (obsolete link; Claude Code reads AGENTS.md)"
  } elseif ($item) {
    Write-Host "  WARN    $projClaude exists and shadows AGENTS.md for Claude Code."
    Write-Host "          Fold its content into AGENTS.md and delete it."
  }
}

Write-Host "Done."
