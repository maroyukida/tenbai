# Simple web health monitor for YTAnalyzer
# Usage:
#   powershell -ExecutionPolicy Bypass -File scripts\monitor_health.ps1 -Port 5000 -RestartTask yta_serve_waitress_logon

param(
  [int]$Port = 5000,
  [string]$RestartTask = "",
  [int]$IntervalSec = 30
)

function Test-Health {
  param([string]$Url)
  try {
    $r = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 5
    return $r.StatusCode -eq 200
  } catch {
    return $false
  }
}

while ($true) {
  $ok = Test-Health -Url ("http://127.0.0.1:{0}/health" -f $Port)
  if (-not $ok) {
    Write-Host ("[{0}] health NG on port {1}" -f (Get-Date), $Port)
    if ($RestartTask -ne "") {
      try {
        schtasks /Run /TN $RestartTask | Out-Null
        Write-Host "Triggered task: $RestartTask"
      } catch {
        Write-Warning "Failed to trigger task: $RestartTask"
      }
    }
  } else {
    Write-Host ("[{0}] health OK" -f (Get-Date))
  }
  Start-Sleep -Seconds $IntervalSec
}

