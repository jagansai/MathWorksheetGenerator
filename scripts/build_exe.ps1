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
# 0. Git: pull latest if working tree is clean
# ---------------------------------------------------------------------------
Write-Step 'Checking for local changes'
$gitStatus = git status --porcelain 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host '   Not a git repo or git not found — skipping pull.' -ForegroundColor Yellow
} elseif ([string]::IsNullOrWhiteSpace($gitStatus)) {
    Write-OK 'Working tree clean — pulling latest from develop.'
    git pull origin develop
    if ($LASTEXITCODE -ne 0) { Write-Fail 'git pull failed.' }
    Write-OK 'Pull complete.'
} else {
    Write-Host '   Local changes detected — skipping pull, building from current state.' -ForegroundColor Yellow
    Write-Host ($gitStatus -split "`n" | ForEach-Object { "      $_" } | Out-String).TrimEnd()
}

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
# Use "python -m pip" so the correct pip is always chosen regardless of PATH.
python -m pip install -r requirements.txt --quiet
if ($LASTEXITCODE -ne 0) { Write-Fail 'pip install -r requirements.txt failed.' }
Write-OK 'Runtime dependencies ready.'

# ---------------------------------------------------------------------------
# 3. Ensure PyInstaller is available
# ---------------------------------------------------------------------------
Write-Step 'Checking PyInstaller'
# Use "python -m PyInstaller" — avoids the common issue where the pyinstaller
# console script is installed to Python\Scripts\ but that folder is not in PATH.
python -m PyInstaller --version 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host '   PyInstaller not found — installing...' -ForegroundColor Yellow
    python -m pip install pyinstaller --quiet
    if ($LASTEXITCODE -ne 0) { Write-Fail 'Could not install PyInstaller.' }
}
Write-OK "PyInstaller $(python -m PyInstaller --version 2>&1)"

# ---------------------------------------------------------------------------
# 3b. Stash .env from previous dist so the API key survives the clean step
# ---------------------------------------------------------------------------
$outDir      = Join-Path $DistDir $AppName
$envInDist   = Join-Path $outDir '.env'
$envStash    = Join-Path ([System.IO.Path]::GetTempPath()) "${AppName}_env_stash"
$envStashed  = $false

if (-not $OneFile -and (Test-Path $envInDist)) {
    Copy-Item -Path $envInDist -Destination $envStash -Force
    $envStashed = $true
    Write-Host '   .env found in dist — stashed to temp before clean.' -ForegroundColor Yellow
}

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
    Remove-Item -Recurse -Force $BuildDir                        -ErrorAction SilentlyContinue
    Remove-Item -Force "$AppName.spec"                          -ErrorAction SilentlyContinue
    Write-OK 'Previous build artifacts removed.'
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
    '--paths',          '.',               # ensure project root is on sys.path during analysis
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

& python -m PyInstaller @pyiArgs

if ($LASTEXITCODE -ne 0) { Write-Fail 'PyInstaller reported errors. See output above.' }

# ---------------------------------------------------------------------------
# 7. Copy config and create logs folder next to the executable
# ---------------------------------------------------------------------------
Write-Step 'Copying runtime files'

if (-not $OneFile) {
    # config\ must live beside the .exe so ConfigManager can find and write it
    $configDst = Join-Path $outDir 'config'
    New-Item -ItemType Directory -Force -Path $configDst | Out-Null
    Copy-Item -Path (Join-Path $ProjectRoot 'config\config.json') -Destination $configDst -Force
    Write-OK "config\config.json  →  $configDst"

    # Create an empty logs\ folder so the logger can write on first run
    $logsDst = Join-Path $outDir 'logs'
    New-Item -ItemType Directory -Force -Path $logsDst | Out-Null
    Write-OK "logs\  created at $logsDst"

    # Restore stashed .env (preserves API key from previous install)
    if ($envStashed) {
        Copy-Item -Path $envStash -Destination (Join-Path $outDir '.env') -Force
        Remove-Item -Force $envStash -ErrorAction SilentlyContinue
        Write-OK '.env restored from stash — API key preserved.'
    }
}
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
Write-Host '   config\config.json is placed beside the exe and is editable by users.' -ForegroundColor Yellow
Write-Host '   Settings changed at runtime (File > Settings) are saved back there.' -ForegroundColor Yellow
Write-Host ''

Pop-Location
