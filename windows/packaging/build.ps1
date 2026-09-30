# Builds dist\360Smart\360Smart.exe and dist\360SmartSetup.exe on Windows.
# Requirements: Python 3.11+ (only on the build machine), Inno Setup 6 (https://jrsoftware.org/isdl.php).
# Usage (from the windows\ folder):  powershell -ExecutionPolicy Bypass -File packaging\build.ps1
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

if (-not (Test-Path .buildvenv)) { python -m venv .buildvenv }
.\.buildvenv\Scripts\python.exe -m pip install --upgrade pip
.\.buildvenv\Scripts\python.exe -m pip install ".[windows]" "pyinstaller>=6.10"

.\.buildvenv\Scripts\pyinstaller.exe packaging\smart360.spec --noconfirm --clean --distpath dist --workpath build

# smoke test the frozen app before packaging it
& dist\360Smart\360Smart.exe --self-test --demo --data-dir "$env:TEMP\360smart-build-selftest"
if ($LASTEXITCODE -ne 0) { throw "Self-test of the frozen app failed ($LASTEXITCODE)" }

$iscc = @("${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe", "$env:ProgramFiles\Inno Setup 6\ISCC.exe") |
    Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) { throw "Inno Setup 6 not found - install it from https://jrsoftware.org/isdl.php" }
& $iscc packaging\installer.iss
Write-Host "Done: dist\360SmartSetup.exe"
