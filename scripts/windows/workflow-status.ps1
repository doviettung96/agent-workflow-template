param(
    [string]$RepoPath = "."
)

$ErrorActionPreference = "Stop"

function Read-JsonFile {
    param([Parameter(Mandatory = $true)][string]$Path)
    if (-not (Test-Path $Path)) {
        return $null
    }

    try {
        return (Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json)
    } catch {
        Write-Warning "Failed to parse JSON: $Path"
        return $null
    }
}

function Get-ValueOrDefault {
    param(
        [Parameter(Mandatory = $false)]$Value,
        [Parameter(Mandatory = $true)][string]$Default
    )

    if ($null -eq $Value) {
        return $Default
    }

    $text = [string]$Value
    if ([string]::IsNullOrWhiteSpace($text)) {
        return $Default
    }

    return $Value
}

$repoRoot = (Resolve-Path $RepoPath).Path
$workflowRoot = Join-Path $repoRoot ".beads\workflow"
$statePath = Join-Path $workflowRoot "state.json"
$handoffPath = Join-Path $workflowRoot "HANDOFF.json"
$summaryPath = Join-Path $workflowRoot "STATE.md"
$agentMailScript = Join-Path $repoRoot "scripts\windows\agent-mail.ps1"

Write-Host ("Repo: {0}" -f $repoRoot)

$state = Read-JsonFile -Path $statePath
$handoff = Read-JsonFile -Path $handoffPath

if (-not (Test-Path $workflowRoot)) {
    Write-Host "Workflow state: not scaffolded in this worktree"
} elseif ($state -eq $null) {
    Write-Host "state.json: missing or invalid"
} else {
    Write-Host ("Mode: {0}" -f (Get-ValueOrDefault -Value $state.mode -Default "unknown"))
    Write-Host ("Epic: {0}" -f (Get-ValueOrDefault -Value $state.epic_id -Default "none"))
    Write-Host ("Branch: {0}" -f (Get-ValueOrDefault -Value $state.branch -Default "unknown"))
    Write-Host ("Worktree: {0}" -f (Get-ValueOrDefault -Value $state.worktree_path -Default $repoRoot))
    Write-Host ("Coordinator: {0}" -f (Get-ValueOrDefault -Value $state.coordinator -Default "none"))

    $workers = @($state.workers)
    if ($workers.Count -eq 0) {
        Write-Host "Workers: none"
    } else {
        Write-Host "Workers:"
        foreach ($worker in $workers) {
            $line = "- {0}" -f (Get-ValueOrDefault -Value $worker.name -Default "unnamed")
            if ($worker.status) {
                $line += " [" + $worker.status + "]"
            }
            if ($worker.bead_id) {
                $line += " bead=" + $worker.bead_id
            }
            Write-Host $line
        }
    }

    $reservations = @($state.reservations)
    if ($reservations.Count -eq 0) {
        Write-Host "Local reservations: none"
    } else {
        Write-Host "Local reservations:"
        foreach ($reservation in $reservations) {
            $line = "- {0}" -f (Get-ValueOrDefault -Value $reservation.path -Default "unknown-path")
            if ($reservation.owner) {
                $line += " owner=" + $reservation.owner
            }
            if ($reservation.bead_id) {
                $line += " bead=" + $reservation.bead_id
            }
            Write-Host $line
        }
    }

    $blockers = @($state.blockers)
    if ($blockers.Count -eq 0) {
        Write-Host "Blockers: none"
    } else {
        Write-Host "Blockers:"
        foreach ($blocker in $blockers) {
            if ($blocker -is [string]) {
                Write-Host ("- {0}" -f $blocker)
                continue
            }

            $line = "- {0}" -f (Get-ValueOrDefault -Value $blocker.summary -Default "unspecified blocker")
            if ($blocker.bead_id) {
                $line += " bead=" + $blocker.bead_id
            }
            Write-Host $line
        }
    }

    Write-Host ("Last action: {0}" -f (Get-ValueOrDefault -Value $state.last_action -Default "none"))
    Write-Host ("Next action: {0}" -f (Get-ValueOrDefault -Value $state.next_action -Default "none"))
}

if (Test-Path $summaryPath) {
    Write-Host "STATE.md: present"
} else {
    Write-Host "STATE.md: missing"
}

$hasHandoff = $false
if ($handoff) {
    if ($handoff.role -or $handoff.bead_id -or $handoff.summary -or (($handoff.status) -and ($handoff.status -ne "idle"))) {
        $hasHandoff = $true
    }
}

if (-not $hasHandoff) {
    Write-Host "Handoff: none"
} else {
    Write-Host ("Handoff role: {0}" -f (Get-ValueOrDefault -Value $handoff.role -Default "unknown"))
    Write-Host ("Handoff bead: {0}" -f (Get-ValueOrDefault -Value $handoff.bead_id -Default "none"))
    Write-Host ("Handoff next action: {0}" -f (Get-ValueOrDefault -Value $handoff.next_action -Default "none"))
}

if ((Get-Command br -ErrorAction SilentlyContinue) -and $state -and $state.epic_id) {
    $previousRustLog = $env:RUST_LOG
    try {
        $env:RUST_LOG = "error"
        $readyRaw = br ready --parent $state.epic_id --json
        $ready = @($readyRaw | ConvertFrom-Json)
        if ($ready.Count -eq 0) {
            Write-Host "Ready descendants: none"
        } else {
            Write-Host "Ready descendants:"
            foreach ($item in $ready) {
                $line = "- {0}" -f (Get-ValueOrDefault -Value $item.id -Default "unknown-id")
                if ($item.title) {
                    $line += ": " + $item.title
                }
                Write-Host $line
            }
        }
    } catch {
        Write-Warning "Failed to inspect ready descendants for the active epic."
    } finally {
        if ($null -eq $previousRustLog) {
            Remove-Item Env:\RUST_LOG -ErrorAction SilentlyContinue
        } else {
            $env:RUST_LOG = $previousRustLog
        }
    }
} else {
    Write-Host "Ready descendants: skipped"
}

if (Test-Path $agentMailScript) {
    try {
        $mailRaw = & $agentMailScript --repo $repoRoot status
        $mail = $mailRaw | ConvertFrom-Json
        if ($mail.ok) {
            Write-Host ("Shared control plane: {0}" -f (Get-ValueOrDefault -Value $mail.root -Default "unknown"))
            Write-Host ("Git common dir: {0}" -f (Get-ValueOrDefault -Value $mail.git_common_dir -Default "unknown"))
            Write-Host ("Agent Mail threads: {0}" -f (Get-ValueOrDefault -Value $mail.thread_count -Default "0"))

            $locks = @($mail.epic_locks)
            if ($locks.Count -eq 0) {
                Write-Host "Shared epic locks: none"
            } else {
                Write-Host "Shared epic locks:"
                foreach ($lock in $locks) {
                    $line = "- epic=" + (Get-ValueOrDefault -Value $lock.epic_id -Default "unknown")
                    $line += " owner=" + (Get-ValueOrDefault -Value $lock.owner -Default "unknown")
                    Write-Host $line
                }
            }

            $mailReservations = @($mail.reservations)
            if ($mailReservations.Count -eq 0) {
                Write-Host "Shared reservations: none"
            } else {
                Write-Host "Shared reservations:"
                foreach ($reservation in $mailReservations) {
                    $line = "- {0}" -f (Get-ValueOrDefault -Value $reservation.path -Default "unknown-path")
                    $line += " owner=" + (Get-ValueOrDefault -Value $reservation.owner -Default "unknown")
                    if ($reservation.bead_id) {
                        $line += " bead=" + $reservation.bead_id
                    }
                    Write-Host $line
                }
            }
        } else {
            Write-Host "Shared control plane: unavailable"
        }
    } catch {
        Write-Warning "Failed to inspect Agent Mail state."
    }
} else {
    Write-Host "Shared control plane: unavailable"
}
