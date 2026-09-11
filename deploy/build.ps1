# Builds a standalone FOMA.exe with PyInstaller.
# Requires: pip install pyinstaller  (and the project already pip install -e'd)

param(
    [ValidateSet("onfile", "onedir")]
    [string]$Mode = "onedir"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$dist = Join-Path $root "dist"

Push-Location $root
try {
    if ($Mode -eq "onfile") {
        $env:FOMA_ONEFILE = "1"
    } else {
        $env:FOMA_ONEFILE = "0"
    }
    & ".venv\Scripts\pyinstaller.exe" --clean --noconfirm --distpath $dist deploy\foma.spec
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }
} finally {
    Pop-Location
}

Write-Host ""
Write-Host "Artifacts:"
Get-ChildItem -Recurse $dist | Select-Object FullName | ForEach-Object { Write-Host "  $($_.FullName)" }
Write-Host ""
Write-Host "Distribute the whole '$dist' folder; run FOMA.exe from it. UIA + fallback deps are bundled."