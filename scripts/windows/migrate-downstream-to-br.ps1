param(
    [Parameter(Mandatory = $true)][string]$RepoPath,
    [string]$Prefix,
    [string]$TemplateRoot = (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent)
)

$ErrorActionPreference = "Stop"

function Test-Command {
    param([Parameter(Mandatory = $true)][string]$Name)
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Get-PythonCommand {
    foreach ($cmd in @("py", "python", "python3")) {
        if (Test-Command -Name $cmd) {
            return $cmd
        }
    }
    throw "Python is required for migration"
}

function Get-RepoPrefix {
    param(
        [Parameter(Mandatory = $true)][string]$RepoPath,
        [string]$ExplicitPrefix
    )

    if ($ExplicitPrefix) {
        return $ExplicitPrefix
    }

    $whereOutput = $null
    try {
        Push-Location $RepoPath
        try {
            $whereOutput = bd where
        } finally {
            Pop-Location
        }
    } catch {
        $whereOutput = $null
    }

    if ($whereOutput) {
        $match = $whereOutput | Select-String -Pattern '^\s*prefix:\s*(.+)$' | Select-Object -First 1
        if ($match) {
            return $match.Matches[0].Groups[1].Value.Trim()
        }
    }

    $configPath = Join-Path $RepoPath ".beads\config.yaml"
    if (Test-Path $configPath) {
        $match = Select-String -Path $configPath -Pattern '^\s*issue[-_]prefix:\s*"?([^"#]+)"?' | Select-Object -First 1
        if ($match) {
            return $match.Matches[0].Groups[1].Value.Trim()
        }
    }

    return (Split-Path $RepoPath -Leaf).ToLowerInvariant()
}

foreach ($cmd in @("git", "br", "bd")) {
    if (-not (Test-Command -Name $cmd)) {
        throw "Missing required command: $cmd"
    }
}

$null = Get-PythonCommand

if (-not (Test-Path $RepoPath)) {
    throw "RepoPath does not exist: $RepoPath"
}

$beadsDir = Join-Path $RepoPath ".beads"
if (-not (Test-Path $beadsDir)) {
    throw "Repo does not contain .beads/: $RepoPath"
}

$resolvedPrefix = Get-RepoPrefix -RepoPath $RepoPath -ExplicitPrefix $Prefix
$tempDir = Join-Path ([System.IO.Path]::GetTempPath()) ("bd-to-br-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force -Path $tempDir | Out-Null
$exportPath = Join-Path $tempDir "issues.jsonl"

try {
    Write-Host "Exporting existing bd issue state from $RepoPath"
    Push-Location $RepoPath
    try {
        bd export -o $exportPath
        br init --force --prefix $resolvedPrefix
    } finally {
        Pop-Location
    }

    Copy-Item -Force $exportPath (Join-Path $beadsDir "issues.jsonl")

    Remove-Item -Recurse -Force (Join-Path $beadsDir "dolt") -ErrorAction SilentlyContinue
    Remove-Item -Recurse -Force (Join-Path $beadsDir "hooks") -ErrorAction SilentlyContinue
    Remove-Item -Recurse -Force (Join-Path $beadsDir "backup") -ErrorAction SilentlyContinue
    foreach ($name in @(".local_version", "dolt-access.lock", "dolt-server.lock", "dolt-server.log", "dolt-server.pid", "dolt-server.port", "redirect")) {
        Remove-Item -Force (Join-Path $beadsDir $name) -ErrorAction SilentlyContinue
    }

    & (Join-Path $PSScriptRoot "scaffold-repo-files.ps1") -RepoPath $RepoPath -Prefix $resolvedPrefix -TemplateRoot $TemplateRoot

    Write-Host "Smoke-checking migrated repo with br list --json"
    Push-Location $RepoPath
    try {
        br list --json | Out-Null
    } finally {
        Pop-Location
    }

    Write-Host "Migration complete for $RepoPath"
} finally {
    Remove-Item -Recurse -Force $tempDir -ErrorAction SilentlyContinue
}
