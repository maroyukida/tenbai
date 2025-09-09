<#
HeavenMS (v83) quick diagnostic for white world-select screen.

What it does:
- Checks that Login (8484) and Channel base (7575+) ports are listening
- Greps recent server logs for world/channel registration lines
- Shows your active IP stack (IPv4/IPv6) and hosts file overrides
- Produces a concise report to help pinpoint: server misreg vs client (WZ/compat)

Usage (PowerShell):
  Set-ExecutionPolicy -Scope Process Bypass -Force
  ./scripts/heavenms_diag.ps1 -ServerRoot "C:\\path\\to\\HeavenMS" -ClientRoot "C:\\path\\to\\MapleV83"

Params:
-ServerRoot: Folder containing your built/ran HeavenMS (logs/*.log or console capture)
-ClientRoot: Folder that has MapleStory.exe, UI.wz, Etc.wz, String.wz

Output:
- Writes scripts/heavenms_diag_output.txt (UTF-8) and prints a short summary
#>
param(
  [Parameter(Mandatory=$false)][string]$ServerRoot,
  [Parameter(Mandatory=$false)][string]$ClientRoot
)

function Write-Log([string]$line) {
  Write-Output $line
  Add-Content -Path $OutFile -Value $line -Encoding UTF8
}

function Write-Section($title) {
  Write-Log "\n==== $title ===="
}

function Find-Logs($root) {
  if (-not $root) { return @() }
  $allowedExt = @('.log','.out','.txt')
  $candidates = Get-ChildItem -Recurse -ErrorAction SilentlyContinue -Path $root |
    Where-Object { $_.PSIsContainer -eq $false } |
    Where-Object {
      ($allowedExt -contains $_.Extension.ToLower()) -or
      ($_.DirectoryName -match "(?i)(^|[\\/])logs?([\\/]|$)") -or
      ($_.Name -match "(?i)^console.*\.(log|txt|out)$")
    }
  $candidates | Sort-Object LastWriteTime -Descending | Select-Object -Unique
}

function Tail-IfExists($path, $lines=200) {
  if (Test-Path $path) {
    Write-Log "--- $path (last $lines lines) ---"
    try {
      $text = Get-Content -Tail $lines -Path $path -ErrorAction Stop
      foreach ($ln in $text) { Write-Log $ln }
    } catch {
      Write-Log "(skip: could not read as text)"
    }
  }
}

$OutFile = Join-Path (Split-Path -Parent $PSCommandPath) "heavenms_diag_output.txt"
Remove-Item $OutFile -ErrorAction SilentlyContinue | Out-Null
Set-Content -Path $OutFile -Value "HeavenMS diag $(Get-Date -Format o)" -Encoding UTF8

Write-Section "Process/Port check"
$net = @()
try {
  $net = netstat -ano | Select-String -Pattern ":8484|:7575|:7576|:7577|:7578"
  if ($net) {
    foreach ($ln in $net) { Write-Log $ln.ToString() }
  } else {
    Write-Log "No listeners found on 8484/7575+"
  }
} catch { Write-Log "netstat failed: $_" }

Write-Section "IP stack"
try {
  $ip = Get-NetIPConfiguration | Format-Table -AutoSize | Out-String
  Write-Log $ip
} catch {}

Write-Section "Hosts file relevant lines"
$hosts = "$env:SystemRoot\System32\drivers\etc\hosts"
if (Test-Path $hosts) {
  $hostLines = Get-Content $hosts | Where-Object { $_ -match "localhost|nexon|maple|heaven" }
  foreach ($ln in $hostLines) { Write-Log $ln }
}

Write-Section "Server logs (world/channel registration)"
if ($ServerRoot) {
  $logs = Find-Logs $ServerRoot | Select-Object -First 6
  foreach ($f in $logs) { Tail-IfExists $f.FullName 200 }
} else {
  Write-Log "ServerRoot not provided; skipped log scan."
}

Write-Section "Client WZ presence"
$hasUI = $false
$hasDinput = $false
function Get-PathSizeMB([string]$path) {
  try {
    $item = Get-Item $path -ErrorAction Stop
    if ($item.PSIsContainer) {
      $bytes = (Get-ChildItem -Recurse -File -ErrorAction SilentlyContinue $path | Measure-Object -Property Length -Sum).Sum
      if (-not $bytes) { $bytes = 0 }
      return [math]::Round($bytes/1MB,2)
    } else {
      return [math]::Round($item.Length/1MB,2)
    }
  } catch { return 0 }
}
if ($ClientRoot) {
  $wz = @("UI.wz","Etc.wz","String.wz","Map.wz")
  foreach ($n in $wz) {
    $p = Join-Path $ClientRoot $n
    if (Test-Path $p) {
      $mb = Get-PathSizeMB $p
      $mod = (Get-Item $p).LastWriteTime
      Write-Log ("{0}: {1} MB, Modified={2}" -f $n,$mb,$mod)
      if ($n -eq 'UI.wz' -and $mb -gt 0) { $hasUI = $true }
      if ($mb -eq 0) { Write-Log ("WARNING: {0} has 0 MB content (possible broken extract)" -f $n) }
    } else {
      Write-Log ("{0}: MISSING" -f $n)
    }
  }
  $dinput = Join-Path $ClientRoot "dinput8.dll"
  if (Test-Path $dinput) { $hasDinput = $true; Write-Log "dinput8.dll: PRESENT" } else { Write-Log "dinput8.dll: MISSING" }
} else {
  Write-Log "ClientRoot not provided; skipped WZ presence check."
}

Write-Section "Heuristic verdict"
$has8484 = ($net | Where-Object { $_.ToString() -match ":8484" })
$has7575 = ($net | Where-Object { $_.ToString() -match ":7575" })

if (-not $has8484 -or -not $has7575) {
  Write-Log "Likely server-side issue: missing listeners (8484/7575). Check channel process and IP binding (use 127.0.0.1)."
} elseif ($has8484 -and $has7575 -and $hasUI -and -not $hasDinput) {
  Write-Log "Server looks up. Client-side likely: add dinput8.dll and ensure v83-clean UI.wz/Etc.wz/String.wz from same source."
} else {
  Write-Log "If world list remains blank with listeners OK, suspect WZ mismatch (UI.wz WorldSelect) or IPv6/localhost mismatch; force 127.0.0.1 in client."
}

Write-Section "Next steps"
Write-Log "1) Ensure server binds to 127.0.0.1 and shows 'Registered channel' in logs."
Write-Log "2) Client: serverIP=127.0.0.1:8484, run as Admin, XP SP3 compat, DPI override."
Write-Log "3) If still white, replace UI.wz first with a known-good v83 (same pack as Etc/String/Map)."
Write-Log "4) As last resort, full v83 pack from same source (no mix)."

Write-Section "Summary"
Get-Content $OutFile | Select-String -Pattern "Likely server-side|Server looks up|If world list" | ForEach-Object { $_.Line } | ForEach-Object { Write-Output $_ }
Write-Output "\nFull report: $OutFile"
