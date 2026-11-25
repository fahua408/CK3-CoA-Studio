$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Version = "1.0.0"
$AppName = "CK3-CoA-Studio"
$PythonExe = if (Test-Path "$Root\.venv\Scripts\python.exe") { "$Root\.venv\Scripts\python.exe" } else { "python" }

Write-Host "==> Using Python: $PythonExe" -ForegroundColor Cyan

# Ensure icon exists
& $PythonExe -c "from pathlib import Path; from src.core.image_ops import generate_app_icons; generate_app_icons(Path('assets'))"

# Clean previous build artifacts
Remove-Item -Recurse -Force -ErrorAction SilentlyContinue "$Root\build", "$Root\dist", "$Root\release"
New-Item -ItemType Directory -Force "$Root\release" | Out-Null

Write-Host "==> Building $AppName standalone folder with PyInstaller..." -ForegroundColor Cyan
& $PythonExe -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --onedir `
    --name $AppName `
    --icon "$Root\assets\app_icon.ico" `
    --add-data "$Root\assets;assets" `
    --paths "$Root" `
    "$Root\src\main.py"

$DistAppDir = "$Root\dist\$AppName"
if (-not (Test-Path "$DistAppDir\$AppName.exe")) {
    throw "PyInstaller build failed: $DistAppDir\$AppName.exe not found."
}

$PortableZip = "$Root\release\$AppName-v$Version-win64-portable.zip"
Write-Host "==> Creating Portable ZIP: $PortableZip" -ForegroundColor Cyan
Compress-Archive -Path "$DistAppDir\*" -DestinationPath $PortableZip -CompressionLevel Optimal

# Copy payload into build temp for GUI Setup Wizard executable
$PayloadZip = "$Root\build\app_payload.zip"
Copy-Item $PortableZip $PayloadZip -Force

Write-Host "==> Building GUI Setup Installer (.exe)..." -ForegroundColor Cyan
& $PythonExe -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --onefile `
    --name "$AppName-Setup-v$Version" `
    --distpath "$Root\release" `
    --workpath "$Root\build\setup_work" `
    --specpath "$Root\build" `
    --icon "$Root\assets\app_icon.ico" `
    --add-data "$PayloadZip;." `
    --add-data "$Root\assets\app_icon.ico;." `
    "$Root\packaging\installer_stub.py"

# Optional: also build Inno Setup installer if ISCC.exe is installed
$IsccPath = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if (Test-Path $IsccPath) {
    Write-Host "==> Found Inno Setup, building Inno installer..." -ForegroundColor Cyan
    & $IsccPath "$Root\packaging\installer.iss"
}

Write-Host "`n==> Release build complete! Output files in $Root\release:" -ForegroundColor Green
Get-ChildItem "$Root\release" | Select-Object Name, Length
