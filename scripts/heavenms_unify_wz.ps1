<#
HeavenMS v83 — Unify WZ from a source pack

Copies all top-level *.wz from a source folder into the client folder.
Backs up existing client WZ to *.bak if not already backed up.

Usage:
  Set-ExecutionPolicy -Scope Process Bypass -Force
  ./scripts/heavenms_unify_wz.ps1 -SourceRoot "E:\\hoge\\v83pack" -ClientRoot "E:\\Games\\MapleStory_v83\\MapleStory"
#>
param(
  [Parameter(Mandatory=$true)][string]$SourceRoot,
  [Parameter(Mandatory=$true)][string]$ClientRoot
)

if (-not (Test-Path $SourceRoot)) { throw "SourceRoot not found: $SourceRoot" }
if (-not (Test-Path $ClientRoot)) { throw "ClientRoot not found: $ClientRoot" }

$srcFiles = Get-ChildItem -Path $SourceRoot -File -Filter '*.wz' -ErrorAction SilentlyContinue
if (-not $srcFiles) { throw "No .wz files in $SourceRoot" }

"Backing up existing client WZ (once) and copying from: $SourceRoot" | Write-Output

foreach ($sf in $srcFiles) {
  $dst = Join-Path $ClientRoot $sf.Name
  $bak = "$dst.bak"
  try {
    if ((Test-Path $dst) -and -not (Test-Path $bak)) {
      Copy-Item -Force -Path $dst -Destination $bak
      Write-Output ("BACKUP: {0}" -f (Split-Path $dst -Leaf))
    }
    Copy-Item -Force -Path $sf.FullName -Destination $dst
    Write-Output ("COPIED: {0}" -f $sf.Name)
  } catch {
    Write-Output ("ERROR: {0} -> {1}" -f $sf.Name, $_)
  }
}

Write-Output "Done."
