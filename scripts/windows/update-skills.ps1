param(
    [Parameter(Mandatory = $true)][string]$RepoPath,
    [string]$TemplateRoot = (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent)
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $RepoPath)) {
    throw "RepoPath does not exist: $RepoPath"
}

$skillsSource = Join-Path $TemplateRoot "skills"

# Codex skills
New-Item -ItemType Directory -Force -Path (Join-Path $RepoPath ".codex\skills") | Out-Null
Get-ChildItem $skillsSource -Directory | ForEach-Object {
    $destination = Join-Path $RepoPath ".codex\skills\$($_.Name)"
    Copy-Item -Recurse -Force $_.FullName $destination
    Write-Host "Updated Codex skill: $($_.Name)"
}

# Claude skills
New-Item -ItemType Directory -Force -Path (Join-Path $RepoPath ".claude\skills") | Out-Null
Get-ChildItem $skillsSource -Directory | ForEach-Object {
    $destination = Join-Path $RepoPath ".claude\skills\$($_.Name)"
    Copy-Item -Recurse -Force $_.FullName $destination
    Write-Host "Updated Claude skill: $($_.Name)"
}

Write-Host "Skills synced to $RepoPath"
