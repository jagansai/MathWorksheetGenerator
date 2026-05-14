# setup.ps1 — One-time prerequisite installer for Math Worksheet Generator
#
# Run this ONCE on any new PC before building or running the app:
#
#   Right-click this file > "Run with PowerShell"
#   — or —
#   Open PowerShell in the project root and run:
#       .\scripts\setup.ps1
#
# What it does:
#   1. Verifies Python 3.9+ is installed  (shows download link if not)
#   2. Upgrades pip to the latest version
#   3. Installs all Python dependencies listed in requirements.txt
#   4. Installs PyInstaller (needed to build the .exe)
#   5. Runs a quick sanity-check to confirm everything worked

[CmdletBinding()]
param()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
function Write-Step($msg) { Write-Host "`n>> $msg" -ForegroundColor Cyan }
function Write-OK($msg)   { Write-Host "   OK  $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "   WARN $msg" -ForegroundColor Yellow }
function Write-Fail {
    param($msg)
    Write-Host "`n   ERROR: $msg" -ForegroundColor Red
    Write-Host ''
    Pause
    exit 1
}

$ScriptDir   = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

Push-Location $ProjectRoot

Write-Host ''
Write-Host '============================================================' -ForegroundColor Magenta
Write-Host '   Math Worksheet Generator — Setup' -ForegroundColor Magenta
Write-Host '============================================================' -ForegroundColor Magenta

# ---------------------------------------------------------------------------
# 1. Check PowerShell execution policy (common blocker for novice users)
# ---------------------------------------------------------------------------
Write-Step 'Checking PowerShell execution policy'
$policy = Get-ExecutionPolicy -Scope CurrentUser
if ($policy -eq 'Restricted') {
    Write-Warn 'Scripts are blocked by execution policy. Attempting to fix...'
    Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned -Force
    Write-OK 'Execution policy set to RemoteSigned for current user.'
} else {
    Write-OK "Execution policy: $policy"
}

# ---------------------------------------------------------------------------
# 2. Locate Python
# ---------------------------------------------------------------------------
Write-Step 'Checking Python installation'

$pythonCmd = $null
foreach ($candidate in @('python', 'python3', 'py')) {
    $ver = & $candidate --version 2>&1
    if ($LASTEXITCODE -eq 0) {
        $pythonCmd = $candidate
        break
    }
}

if (-not $pythonCmd) {
    Write-Host ''
    Write-Host '   Python was NOT found on this computer.' -ForegroundColor Red
    Write-Host ''
    Write-Host '   Please install Python 3.9 or newer from:' -ForegroundColor Yellow
    Write-Host '       https://www.python.org/downloads/' -ForegroundColor Yellow
    Write-Host ''
    Write-Host '   IMPORTANT — during installation:' -ForegroundColor Yellow
    Write-Host '     * Check "Add Python to PATH"  <-- this box MUST be ticked' -ForegroundColor Yellow
    Write-Host '     * Click "Install Now"' -ForegroundColor Yellow
    Write-Host ''
    Write-Host '   After Python is installed, run this script again.' -ForegroundColor Yellow
    Write-Host ''
    Pause
    exit 1
}

# Verify minimum version (3.9)
$rawVer  = & $pythonCmd --version 2>&1   # e.g. "Python 3.11.4"
$verNums = ($rawVer -replace 'Python\s*', '').Trim().Split('.')
[int]$major = $verNums[0]
[int]$minor = $verNums[1]

if ($major -lt 3 -or ($major -eq 3 -and $minor -lt 9)) {
    Write-Fail "Python 3.9+ is required, but found $rawVer. Please upgrade at https://www.python.org/downloads/"
}
Write-OK "$rawVer  (command: $pythonCmd)"

# ---------------------------------------------------------------------------
# 3. Upgrade pip
# ---------------------------------------------------------------------------
Write-Step 'Upgrading pip'
& $pythonCmd -m pip install --upgrade pip --quiet
if ($LASTEXITCODE -ne 0) {
    Write-Warn 'pip upgrade failed — continuing with existing pip version.'
} else {
    $pipVer = & $pythonCmd -m pip --version 2>&1
    Write-OK $pipVer
}

# ---------------------------------------------------------------------------
# 4. Install project requirements
# ---------------------------------------------------------------------------
Write-Step 'Installing project requirements  (requirements.txt)'
Write-Host '   This may take a few minutes on the first run...' -ForegroundColor Gray

& $pythonCmd -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    Write-Fail 'Failed to install project requirements. See errors above.'
}
Write-OK 'All project requirements installed.'

# ---------------------------------------------------------------------------
# 5. Install PyInstaller
# ---------------------------------------------------------------------------
Write-Step 'Installing PyInstaller  (needed to build the .exe)'
& $pythonCmd -m pip install pyinstaller --quiet
if ($LASTEXITCODE -ne 0) {
    Write-Fail 'Failed to install PyInstaller. See errors above.'
}
$pyiVer = & $pythonCmd -m PyInstaller --version 2>&1
Write-OK "PyInstaller $pyiVer"

# ---------------------------------------------------------------------------
# 6. Sanity-check imports
# ---------------------------------------------------------------------------
Write-Step 'Verifying key imports'

$checks = @(
    @{ module = 'PyQt6';       label = 'PyQt6 (UI framework)' },
    @{ module = 'openai';      label = 'openai (AI service)' },
    @{ module = 'fpdf';        label = 'fpdf2 (PDF generation)' },
    @{ module = 'pdfplumber';  label = 'pdfplumber (PDF reading)' },
    @{ module = 'dotenv';      label = 'python-dotenv (config)' },
    @{ module = 'PyInstaller'; label = 'PyInstaller (build tool)' }
)

$allOk = $true
foreach ($c in $checks) {
    $result = & $pythonCmd -c "import $($c.module)" 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-OK $c.label
    } else {
        Write-Host "   FAIL  $($c.label)" -ForegroundColor Red
        Write-Host "         $result" -ForegroundColor Red
        $allOk = $false
    }
}

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
Write-Host ''
Write-Host '============================================================' -ForegroundColor Magenta
if ($allOk) {
    Write-Host '   Setup complete! All prerequisites are installed.' -ForegroundColor Green
    Write-Host ''
    Write-Host '   Next steps:' -ForegroundColor Cyan
    Write-Host '     * To run the app:       .\scripts\run.ps1' -ForegroundColor White
    Write-Host '     * To build an .exe:     .\scripts\build_exe.ps1' -ForegroundColor White
} else {
    Write-Host '   Setup finished with errors (see above).' -ForegroundColor Red
    Write-Host '   Fix the reported issues and run this script again.' -ForegroundColor Yellow
}
Write-Host '============================================================' -ForegroundColor Magenta
Write-Host ''

Pop-Location
Pause
