# Build Math Worksheet Generator as a standalone executable.
#
# Usage:
#   .\scripts\build_exe.ps1            # onedir bundle (faster startup — recommended)
#   .\scripts\build_exe.ps1 -OneFile   # single .exe (slower cold start, easier to share)
#   .\scripts\build_exe.ps1 -Clean     # force-delete previous build artifacts first

[CmdletBinding()]
param(
    [switch]$Clean,
    [switch]$OneFile
)

$AppName    = 'MathWorksheetGenerator'
$ScriptDir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
$DistDir    = Join-Path $ProjectRoot 'dist'
$BuildDir   = Join-Path $ProjectRoot 'build'

Push-Location $ProjectRoot

function Write-Step($msg) { Write-Host "`n>> $msg" -ForegroundColor Cyan }
function Write-OK($msg)   { Write-Host "   OK  $msg" -ForegroundColor Green }
function Write-Fail($msg) { Write-Host "   ERR $msg" -ForegroundColor Red; Pop-Location; exit 1 }

# ---------------------------------------------------------------------------
# 1. Python check
# ---------------------------------------------------------------------------
Write-Step 'Checking Python'
$pyVer = python --version 2>&1
if ($LASTEXITCODE -ne 0) { Write-Fail 'Python not found in PATH.' }
Write-OK $pyVer

# ---------------------------------------------------------------------------
# 2. Install / upgrade all runtime dependencies
# ---------------------------------------------------------------------------
Write-Step 'Installing runtime requirements'
pip install -r requirements.txt --quiet
if ($LASTEXITCODE -ne 0) { Write-Fail 'pip install -r requirements.txt failed.' }
Write-OK 'Runtime dependencies ready.'

# ---------------------------------------------------------------------------
# 3. Ensure PyInstaller is available
# ---------------------------------------------------------------------------
Write-Step 'Checking PyInstaller'
pyinstaller --version 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host '   PyInstaller not found — installing...' -ForegroundColor Yellow
    pip install pyinstaller --quiet
    if ($LASTEXITCODE -ne 0) { Write-Fail 'Could not install PyInstaller.' }
}
Write-OK "PyInstaller $(pyinstaller --version 2>&1)"

# ---------------------------------------------------------------------------
# 4. Clean previous artifacts (always clean onedir target; full clean if -Clean)
# ---------------------------------------------------------------------------
Write-Step 'Cleaning old artifacts'
if ($Clean) {
    Remove-Item -Recurse -Force $BuildDir        -ErrorAction SilentlyContinue
    Remove-Item -Recurse -Force $DistDir         -ErrorAction SilentlyContinue
    Remove-Item -Force "$AppName.spec"           -ErrorAction SilentlyContinue
    Write-OK 'Full clean done.'
} else {
    Remove-Item -Recurse -Force (Join-Path $DistDir $AppName) -ErrorAction SilentlyContinue
    Remove-Item -Force "$AppName.spec"                        -ErrorAction SilentlyContinue
    Write-OK 'Previous build target removed.'
}

# ---------------------------------------------------------------------------
# 5. Assemble PyInstaller arguments
# ---------------------------------------------------------------------------
$mode = if ($OneFile) { '--onefile' } else { '--onedir' }
Write-Step "Building — mode: $mode"

$pyiArgs = @(
    $mode,
    '--name',           $AppName,
    '--windowed',                          # no console window
    '--noconfirm',
    '--add-data',       "config;config",   # bundle config/ folder
    '--add-data',       "logs/.gitkeep;logs",  # create logs/ dir in the bundle
    '--add-data',       "assets;assets",   # app icon and other assets
    '--icon',           "assets/icon.ico", # embed icon in the .exe file
    '--collect-all',    'pdfplumber',      # includes pdfplumber's own data files
    '--collect-all',    'pdfminer',        # pdfminer.six codec data
    '--collect-all',    'pypdfium2',       # native binaries for PDF rendering
    '--collect-all',    'fpdf',            # font metrics .pkl files (required for text layout)
    '--copy-metadata',  'fpdf2',           # lets importlib.resources find font data when frozen
    '--hidden-import',  'PyQt6.sip',
    '--hidden-import',  'openai',
    '--hidden-import',  'dotenv',
    'main.py'
)

& pyinstaller @pyiArgs

if ($LASTEXITCODE -ne 0) { Write-Fail 'PyInstaller reported errors. See output above.' }

# ---------------------------------------------------------------------------
# 6. Locate and report the output
# ---------------------------------------------------------------------------
Write-Step 'Build complete'

$exePath = if ($OneFile) {
    Join-Path $DistDir "$AppName.exe"
} else {
    Join-Path $DistDir "$AppName\$AppName.exe"
}

if (Test-Path $exePath) {
    $size = [math]::Round((Get-Item $exePath).Length / 1MB, 1)
    Write-OK "Executable : $exePath  ($($size) MB)"
} else {
    Write-Host "   Output folder: $(Join-Path $DistDir $AppName)" -ForegroundColor Yellow
}

Write-Host ''
Write-Host '   NOTE: config\config.json is bundled as a read-only default.' -ForegroundColor Yellow
Write-Host '         Users can override settings at runtime via File > Settings.' -ForegroundColor Yellow
Write-Host ''

Pop-Location
