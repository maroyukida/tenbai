# YTAnalyzer status helper
# Usage:
#   powershell -ExecutionPolicy Bypass -File scripts\status.ps1 [-Port 5000] [-Db data\rss_watch.sqlite] \
#              [-ChannelsFile C:\\Users\\mouda\\yutura_channels.ndjson] [-Top 5] [-Logs]

param(
  [int]$Port = 5000,
  [string]$Db = "data\\rss_watch.sqlite",
  [string]$ChannelsFile = "C:\\Users\\mouda\\yutura_channels.ndjson",
  [int]$Top = 5,
  [switch]$Logs
)

function Get-PythonPath {
  if (Test-Path .venv) {
    $p = Join-Path -Path (Resolve-Path .venv).Path -ChildPath 'Scripts/python.exe'
    if (Test-Path $p) { return $p }
  }
  return 'python'
}

function Test-Health {
  param([int]$Port)
  try {
    $r = Invoke-WebRequest -UseBasicParsing -Uri ("http://127.0.0.1:{0}/health" -f $Port) -TimeoutSec 3
    if ($r.StatusCode -eq 200) { return $true } else { return $false }
  } catch { return $false }
}

Write-Host "== YTAnalyzer Status ==" -ForegroundColor Cyan
Write-Host "Time:  " (Get-Date)
Write-Host "DB:    " (Resolve-Path $Db -ErrorAction SilentlyContinue)
Write-Host "Port:  " $Port
Write-Host "NDJSON:" $ChannelsFile

# Task status
try {
  $task = Get-ScheduledTask yta_scheduler -ErrorAction Stop
  $inst = $task | Select-Object TaskName, State
  Write-Host "Task : " $inst.TaskName ":" $inst.State
  $info = schtasks /Query /TN yta_scheduler /V /FO LIST | Out-String
  ($info -split "`n" | Select-String -Pattern "Last Run Time|Last Result|Task To Run" | ForEach-Object { $_.ToString() })
} catch { Write-Host "Task : not found" -ForegroundColor Yellow }

# Health check
if (Test-Health -Port $Port) {
  Write-Host ("Web  : OK http://127.0.0.1:{0}" -f $Port) -ForegroundColor Green
} else {
  Write-Host ("Web  : NG http://127.0.0.1:{0}" -f $Port) -ForegroundColor Yellow
}

# Latest exports
Write-Host "Exports (latest):"
Get-ChildItem exports\*.jsonl -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 3 |
  ForEach-Object { "  " + $_.LastWriteTime.ToString('yyyy-MM-dd HH:mm:ss') + "  " + $_.Name }

# Channels NDJSON tail
if (Test-Path $ChannelsFile) {
  Write-Host "NDJSON tail (last 5):"
  try { Get-Content -Tail 5 $ChannelsFile } catch { Write-Host "  (cannot read)" }
} else {
  Write-Host "NDJSON tail: file not found" -ForegroundColor Yellow
}

# Auto-discover progress
if (Test-Path 'data/yutura_auto_discover.json') {
  Write-Host "auto_discover state:"
  Get-Content data\yutura_auto_discover.json
}

# SQLite quick stats via Python
$py = Get-PythonPath
function Run-PySql {
  param([string]$Code)
  & $py -c $Code 2>$null
}

$code = @"
import sqlite3, json
con = sqlite3.connect(r'''$Db''')
cur = con.cursor()
def q(sql):
    try:
        return cur.execute(sql).fetchone()[0]
    except Exception:
        return None
def js(sql):
    try:
        con.row_factory = sqlite3.Row
        c = con.cursor()
        rows = [dict(r) for r in c.execute(sql).fetchall()]
        print(json.dumps(rows, ensure_ascii=False))
    except Exception as e:
        print('[]')

print('discovered_1h=', q("select count(*) from rss_videos_discovered where strftime('%s',replace(substr(discovered_at,1,19),'T',' '))>=strftime('%s','now','-1 hour')"))
print('snapshots_1h =', q("select count(*) from ytapi_snapshots where strftime('%s',replace(substr(polled_at,1,19),'T',' '))>=strftime('%s','now','-1 hour')"))
print('trending_cnt=', q("select count(*) from trending_ranks"))
print('trending_at =', q("select max(updated_at) from trending_ranks"))
print('top_trending=')
js("select video_id, title, score from trending_ranks order by score desc limit $Top")
con.close()
"@

Write-Host "DB stats:"
Run-PySql -Code $code

# Monitor process
$mon = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*scripts\monitor_health.ps1*' }
if ($mon) { Write-Host ("Monitor: running (pid={0})" -f $mon.ProcessId) } else { Write-Host "Monitor: not running" }

# Optional logs
if ($Logs) {
  Write-Host "\nLogs (tail 20):" -ForegroundColor Cyan
  foreach ($f in 'scheduler','rss_export','api_fetch','api_refetch','growth_rank','auto_discover') {
    $p = Join-Path 'logs' ("{0}.log" -f $f)
    if (Test-Path $p) {
      Write-Host ("-- " + $p)
      Get-Content -Tail 20 $p
    }
  }
}

