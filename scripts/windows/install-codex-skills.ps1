param(
    [string]$TemplateRoot = (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent),
    [string]$CodexHome = (Join-Path $env:USERPROFILE ".codex"),
    [switch]$Force
)

$ErrorActionPreference = "Stop"

$sourceRoot = Join-Path $TemplateRoot "skills"
$destRoot = Join-Path $CodexHome "skills"

if (-not (Test-Path $sourceRoot)) {
    throw "Missing skills directory: $sourceRoot"
}

New-Item -ItemType Directory -Force -Path $destRoot | Out-Null

Get-ChildItem $sourceRoot -Directory | ForEach-Object {
    $destination = Join-Path $destRoot $_.Name
    if ((Test-Path $destination) -and -not $Force) {
        Write-Warning "Skipping existing skill: $destination"
        return
    }
    Copy-Item -Recurse -Force $_.FullName $destination
    Write-Host "Installed $($_.Name) to $destination"
}

Write-Host "Restart Codex to pick up new skills."
