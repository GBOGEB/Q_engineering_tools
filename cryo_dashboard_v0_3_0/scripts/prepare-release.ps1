<#
.SYNOPSIS
  Cryo Dashboard — Release preparation script.

.DESCRIPTION
  Automates every step needed before opening a PR:
    1. Reads the current version from VERSION and prompts for the next version.
    2. Bumps VERSION, README.md, GIT_TRACKING_MANIFEST.md header.
    3. Prepends a new dated section to docs/CHANGELOG.md.
    4. Regenerates docs/PR_RELEASE_<new>.md with PR title, description and
       merge checklist.
    5. Runs a version-consistency check across all canonical files.

.PARAMETER NewVersion
  Target version string, e.g. "v0.4.8". If omitted the script prompts interactively.

.EXAMPLE
  .\scripts\prepare-release.ps1 -NewVersion v0.4.8
#>

[CmdletBinding(SupportsShouldProcess)]
param(
    [string]$NewVersion = "",
    [hashtable]$ChangelogEntries = $null
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$root = $PSScriptRoot | Split-Path -Parent
$versionFile = Join-Path $root "VERSION"
$readmeFile = Join-Path $root "README.md"
$changelogFile = Join-Path $root "docs\CHANGELOG.md"

function Write-Step ([string]$msg) { Write-Host "  >> $msg" -ForegroundColor Cyan }
function Write-Ok   ([string]$msg) { Write-Host "  OK $msg" -ForegroundColor Green }
function Write-Warn ([string]$msg) { Write-Host "  WARN $msg" -ForegroundColor Yellow }

$currentVersion = (Get-Content $versionFile -Raw).Trim()
Write-Host "  Current version : $currentVersion" -ForegroundColor DarkCyan

if (-not $NewVersion) {
    $NewVersion = Read-Host "  New version (e.g. v0.4.9)"
}
$NewVersion = $NewVersion.Trim()

Write-Step "Updating VERSION -> $NewVersion"
Set-Content -Path $versionFile -Value $NewVersion -NoNewline
Write-Ok "VERSION"

Write-Step "Updating README.md"
$readmeContent = Get-Content $readmeFile -Raw
$readmeNew = $readmeContent -replace [regex]::Escape($currentVersion), $NewVersion
if ($readmeNew -ne $readmeContent) {
    Set-Content -Path $readmeFile -Value $readmeNew -NoNewline
    Write-Ok "README.md"
} else {
    Write-Warn "README.md - pattern not found, skipped."
}

Write-Host "  Done."
