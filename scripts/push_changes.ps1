#Requires -Version 5.1
<#
.SYNOPSIS
    Stage, commit, and push all changes to the current branch, respecting .gitignore.

.PARAMETER Message
    Commit message.  You will be prompted if not supplied.

.PARAMETER Branch
    Target remote branch.  Defaults to the current local branch.

.EXAMPLE
    .\scripts\push_changes.ps1
    .\scripts\push_changes.ps1 -Message "Add Biology handler"
#>
[CmdletBinding()]
param(
    [string] $Message,
    [string] $Branch
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# ── Locate repo root ────────────────────────────────────────────────────────
$RepoRoot = git -C $PSScriptRoot rev-parse --show-toplevel 2>$null
if (-not $RepoRoot) {
    Write-Error 'Not inside a git repository.'
    exit 1
}
Set-Location $RepoRoot

# ── Resolve branch ──────────────────────────────────────────────────────────
if (-not $Branch) {
    $Branch = git rev-parse --abbrev-ref HEAD
}

# ── Show what will be staged ─────────────────────────────────────────────────
Write-Host "`nCurrent status:" -ForegroundColor Cyan
git status --short
Write-Host ''

# ── Stage all tracked modifications + new untracked files (respects .gitignore)
git add --all

$staged = git diff --cached --name-only
if (-not $staged) {
    Write-Host 'Nothing to commit — working tree is clean.' -ForegroundColor Yellow
    exit 0
}

Write-Host 'Files to be committed:' -ForegroundColor Cyan
$staged | ForEach-Object { Write-Host "  $_" }
Write-Host ''

# ── Commit message ────────────────────────────────────────────────────────────
if (-not $Message) {
    $Message = Read-Host 'Commit message'
}
if (-not $Message.Trim()) {
    Write-Error 'Commit message cannot be empty.'
    exit 1
}

# ── Commit ────────────────────────────────────────────────────────────────────
git commit -m $Message
Write-Host "`nCommit created." -ForegroundColor Green

# ── Push ──────────────────────────────────────────────────────────────────────
Write-Host "Pushing to origin/$Branch ..." -ForegroundColor Cyan
git push origin $Branch
Write-Host "`nDone — changes pushed to origin/$Branch." -ForegroundColor Green
