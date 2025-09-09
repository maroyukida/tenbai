# Requires -Version 5.1
# Windows Scheduled Tasks installer for YTAnalyzer jobs
# Usage (PowerShell, as Administrator recommended):
#   cd C:\Users\mouda\ytanalyzer_v3\ytanalyzer_v3
#   ./scripts/install_tasks.ps1 -PythonPath .\.venv\Scripts\python.exe -Every5 1 -Every10 1 -Serve 1 -Port 5000

param(
  [string]$PythonPath = ".\\.venv\\Scripts\\python.exe",
  [string]$WorkDir = (Get-Location).Path,
  [int]$Every5 = 1,
  [int]$Every10 = 1,
  [int]$Serve = 1,
  [int]$Port = 5000,
  [int]$Headless = 0,
  [string]$ChannelsFile = "C:\\Users\\mouda\\yutura_channels.ndjson",
  [int]$Startup = 1,
  [int]$AsSystem = 0
)

Import-Module ScheduledTasks -ErrorAction Stop

function Ensure-Python {
  param([string]$Path)
  if (-not (Test-Path $Path)) {
    Write-Warning "PythonPath not found: $Path. Falling back to 'python'."
    return "python"
  }
  return (Resolve-Path $Path).Path
}

$py = Ensure-Python -Path $PythonPath

function New-YTAAction {
  param([string]$ArgLine)
  New-ScheduledTaskAction -Execute $py -Argument $ArgLine -WorkingDirectory $WorkDir
}

function Register-YTATask {
  param(
    [string]$Name,
    $Action,
    $Trigger,
    $Triggers = $null,
    $Principal = $null,
    $Settings = $null
  )
  $desc = "YTAnalyzer task: $Name"
  if (Get-ScheduledTask -TaskName $Name -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $Name -Confirm:$false
  }
  $args = @{
    TaskName    = $Name
    Action      = $Action
    Description = $desc
    RunLevel    = 'Highest'
    Force       = $true
  }
  if ($Triggers) { $args['Trigger'] = $Triggers }
  elseif ($Trigger) { $args['Trigger'] = $Trigger }
  if ($null -ne $Principal) { $args['Principal'] = $Principal }
  if ($null -ne $Settings) { $args['Settings'] = $Settings }
  Register-ScheduledTask @args | Out-Null
  Write-Host "Installed task: $Name"
}

# Try to read API key from environment or .env in WorkDir
function Get-DotenvValue {
  param([string]$Name)
  try {
    $v = [System.Environment]::GetEnvironmentVariable($Name, 'Process')
    if (-not $v) { $v = [System.Environment]::GetEnvironmentVariable($Name, 'User') }
    if (-not $v) { $v = [System.Environment]::GetEnvironmentVariable($Name, 'Machine') }
    if ($v) { return $v }
  } catch {}
  $envPath = Join-Path $WorkDir ".env"
  if (Test-Path $envPath) {
    try {
      $line = Select-String -Path $envPath -Pattern "^\s*${Name}\s*=\s*(.+)\s*$" -SimpleMatch:$false -ErrorAction SilentlyContinue | Select-Object -First 1
      if ($line) {
        $m = [Regex]::Match($line.Line, "^\s*${Name}\s*=\s*(.+)\s*$")
        if ($m.Success) { return $m.Groups[1].Value.Trim() }
      }
    } catch {}
  }
  return ""
}

$apiKey = Get-DotenvValue -Name "YOUTUBE_API_KEY"

# Every 5 minutes tasks (non-headless)
if ($Every5 -eq 1 -and $Headless -eq 0) {
  $t5 = New-ScheduledTaskTrigger -Once (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 5) -RepetitionDuration ([TimeSpan]::MaxValue)
  $refetchArgs = "-m ytanalyzer.cli api-refetch --db data\\rss_watch.sqlite --qps 1.5"
  if ($apiKey) { $refetchArgs += " --api-key `"$apiKey`"" }
  Register-YTATask -Name "yta_api_refetch_5m" -Action (New-YTAAction -ArgLine $refetchArgs) -Trigger $t5
  Register-YTATask -Name "yta_growth_rank_5m" -Action (New-YTAAction -ArgLine "-m ytanalyzer.cli growth-rank --db data\\rss_watch.sqlite") -Trigger $t5
}

# Every 10 minutes tasks (non-headless)
if ($Every10 -eq 1 -and $Headless -eq 0) {
  $t10 = New-ScheduledTaskTrigger -Once (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 10) -RepetitionDuration ([TimeSpan]::MaxValue)
  $fetchArgs = "-m ytanalyzer.cli api-fetch --db data\\rss_watch.sqlite --in-dir exports --qps 1.0"
  if ($apiKey) { $fetchArgs += " --api-key `"$apiKey`"" }
  Register-YTATask -Name "yta_api_fetch_10m" -Action (New-YTAAction -ArgLine $fetchArgs) -Trigger $t10
}

# Web server on logon (non-headless)
if ($Serve -eq 1 -and $Headless -eq 0) {
  $logon = New-ScheduledTaskTrigger -AtLogOn
  $argLine = "scripts\\serve_prod.py"  # 127.0.0.1:$Port (update script for port if needed)
  Register-YTATask -Name "yta_serve_waitress_logon" -Action (New-YTAAction -ArgLine $argLine) -Trigger $logon
}

# Headless scheduler (single process handles fetch/refetch/rank/serve)
if ($Headless -eq 1) {
  # Triggers: logon + (optional) startup
  $trigs = @()
  $trigs += (New-ScheduledTaskTrigger -AtLogOn)
  if ($Startup -eq 1) { $trigs += (New-ScheduledTaskTrigger -AtStartup) }

  # Robust settings for 24x7
  try {
    $settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -StartWhenAvailable
  } catch { $settings = $null }

  # Principal: current user (default) or LocalSystem when -AsSystem 1
  $principal = $null
  if ($AsSystem -eq 1) {
    try { $principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest } catch {}
  }

  $argLine = "-m ytanalyzer.tools.headless_scheduler --serve --channels-file `"$ChannelsFile`""
  Register-YTATask -Name "yta_scheduler" -Action (New-YTAAction -ArgLine $argLine) -Triggers $trigs -Principal $principal -Settings $settings
}

Write-Host "Done. Open Task Scheduler > Task Scheduler Library to confirm tasks."
