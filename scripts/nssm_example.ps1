# Example script to install YTAnalyzer as Windows Services using NSSM
# Requires: NSSM installed (e.g., C:\tools\nssm\win64\nssm.exe)
# Usage (PowerShell, as Administrator):
#   $env:NSSM="C:\tools\nssm\win64\nssm.exe"
#   cd C:\Users\mouda\ytanalyzer_v3\ytanalyzer_v3
#   ./scripts/nssm_example.ps1 -PythonPath .\.venv\Scripts\python.exe

param(
  [string]$PythonPath = ".\\.venv\\Scripts\\python.exe",
  [string]$NSSM = $env:NSSM,
  [string]$WorkDir = (Get-Location).Path
)

if (-not (Test-Path $NSSM)) {
  Write-Error "Set -NSSM path or env:NSSM to nssm.exe; current='$NSSM'"
  exit 1
}

function Install-Service {
  param([string]$Name, [string]$Args)
  & $NSSM install $Name $PythonPath $Args
  & $NSSM set $Name AppDirectory $WorkDir
  & $NSSM set $Name AppStopMethodConsole 2000
  & $NSSM set $Name AppStopMethodWindow 2000
  & $NSSM set $Name AppStopMethodThreads 2000
  & $NSSM set $Name AppPriority NORMAL_PRIORITY_CLASS
  & $NSSM set $Name AppStdout "$WorkDir\logs\$Name.out.log"
  & $NSSM set $Name AppStderr "$WorkDir\logs\$Name.err.log"
  & $NSSM set $Name AppRotateFiles 1
  & $NSSM set $Name AppRotateOnline 1
  & $NSSM set $Name AppRotateBytes 10485760
  Write-Host "Installed service: $Name"
}

# Headless scheduler (spawns rss-watch, rss-export, and runs periodic jobs)
Install-Service -Name "yta_scheduler" -Args "-m ytanalyzer.tools.headless_scheduler --serve"

# Alternatively, standalone Waitress server
# Install-Service -Name "yta_waitress" -Args "scripts\\serve_prod.py"

Write-Host "Use 'nssm start yta_scheduler' to start."

