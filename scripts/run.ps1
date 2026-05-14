# Run Math Worksheet Generator in development mode
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

New-Item -ItemType Directory -Force -Path "$ProjectRoot\logs" | Out-Null

Push-Location $ProjectRoot
python main.py
Pop-Location
