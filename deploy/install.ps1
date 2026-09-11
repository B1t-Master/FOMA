# Installs FOMA as a silent, on-logon background task using Windows Task Scheduler.
# Uses pythonw.exe so no console window appears. Idempotent.

param(
    [string]$Venv = "$PSScriptRoot\..\.venv",
    [string]$TaskName = "FOMA",
    [string]$Config = "$PSScriptRoot\..\config.toml"
)

$ErrorActionPreference = "Stop"

$pythonw = Join-Path $Venv "Scripts\pythonw.exe"
if (-not (Test-Path -LiteralPath $pythonw)) {
    Write-Error "pythonw.exe not found at $pythonw. Create the venv first: python -m venv .venv"
}

$workDir = Split-Path -Parent $PSScriptRoot
# Task Scheduler needs a quoted command that survives as a single /TR value.
$tr = "`"$pythonw`" -m foma --config `"$Config`""

# Prefer the register-trigger form so the task points at the right session user.
$registerArgs = @(
    "/Create",
    "/TN", $TaskName,
    "/TR", $tr,
    "/SC", "ONLOGON",
    "/RL", "LIMITED",
    "/F"
)

& schtasks.exe $registerArgs
if ($LASTEXITCODE -ne 0) {
    cmd /c "schtasks /Create /TN `"$TaskName`" /TR `"$tr`" /SC ONLOGON /RL LIMITED /F"
}

Write-Host "FOMA autostart installed. It will launch silently at next sign-in (or run:"
Write-Host "  schtasks /Run /TN `"$TaskName`""