# Removes the FOMA on-logon scheduled task. Idempotent.

param(
    [string]$TaskName = "FOMA"
)

$ErrorActionPreference = "Stop"

schtasks.exe /End /TN $TaskName 2>$null | Out-Null
schtasks.exe /Delete /TN $TaskName /F
if ($LASTEXITCODE -eq 0) {
    Write-Host "Task '$TaskName' removed."
} else {
    Write-Host "Task '$TaskName' not found or already removed."
}