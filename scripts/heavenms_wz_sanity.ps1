<#
HeavenMS v83 — WZ sanity checker

Checks presence and size of key WZ files in a Maple v83 client folder.
Optionally computes SHA256 for integrity bookkeeping.

Usage:
  Set-ExecutionPolicy -Scope Process Bypass -Force
  ./scripts/heavenms_wz_sanity.ps1 -ClientRoot "C:\\MapleV83" [-Hash]

Output:
  scripts/heavenms_wz_sanity_output.txt (UTF-8)
#>
param(
  [Parameter(Mandatory=$true)][string]$ClientRoot,
  [switch]$Hash
)

$OutFile = Join-Path (Split-Path -Parent $PSCommandPath) "heavenms_wz_sanity_output.txt"
Remove-Item $OutFile -ErrorAction SilentlyContinue | Out-Null
Set-Content -Path $OutFile -Value "WZ sanity $(Get-Date -Format o)" -Encoding UTF8

function Write-Log($line) {
  Write-Output $line
  Add-Content -Path $OutFile -Value $line -Encoding UTF8
}

if (-not (Test-Path $ClientRoot)) { throw "ClientRoot not found: $ClientRoot" }

Write-Log "\nClientRoot: $ClientRoot"

$targets = @(
  @{ Name='UI.wz';       MinMB=1 },
  @{ Name='Etc.wz';      MinMB=1 },
  @{ Name='String.wz';   MinMB=1 },
  @{ Name='Map.wz';      MinMB=50 }
)

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

Write-Log "\n==== Presence/Size ===="
foreach ($t in $targets) {
  $p = Join-Path $ClientRoot $t.Name
  if (Test-Path $p) {
    $it = Get-Item $p
    $mb = Get-PathSizeMB $p
    $ok = $mb -ge $t.MinMB
    $mark = if ($ok) { 'OK' } else { 'SUSPECT' }
    Write-Log ("{0}: {1} MB, Modified={2} [{3}] (min {4} MB)" -f $t.Name,$mb,$it.LastWriteTime,$mark,$t.MinMB)
    if (-not $ok -and $mb -eq 0) { Write-Log ("WARNING: {0} has 0 MB content (likely broken extract)" -f $t.Name) }
    if ($Hash) {
      try {
        $sha = (Get-FileHash -Algorithm SHA256 -Path $p).Hash
        Write-Log ("{0}.sha256: {1}" -f $t.Name,$sha)
      } catch { Write-Log ("Hash failed for {0}: {1}" -f $t.Name,$_) }
    }
  } else {
    Write-Log ("{0}: MISSING" -f $t.Name)
  }
}

Write-Log "\nSummary: If any are SUSPECT/MISSING, re-extract the same-source v83 pack (no mixing), then rerun."
Write-Output "\nFull report: $OutFile"
