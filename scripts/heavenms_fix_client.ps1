<#
HeavenMS v83 — Client one-shot fixer

What it does:
- Sets compatibility flags for MapleStory.exe (XP SP3, RunAsAdmin, DPI tweaks)
- Copies 32-bit dinput8.dll from SysWOW64 into the client folder (if missing)
- Unblocks downloaded files (removes Zone.Identifier)
- Optionally ensures hosts file has localhost entries (use -PatchHosts)

Usage:
  Set-ExecutionPolicy -Scope Process Bypass -Force
  ./scripts/heavenms_fix_client.ps1 -ClientRoot "E:\\Games\\MapleStory_v83\\MapleStory" [-PatchHosts]
#>
param(
  [Parameter(Mandatory=$true)][string]$ClientRoot,
  [switch]$PatchHosts
)

function Info($m){ Write-Host $m }

if (-not (Test-Path $ClientRoot)) { throw "ClientRoot not found: $ClientRoot" }

$exe = Join-Path $ClientRoot 'MapleStory.exe'
if (-not (Test-Path $exe)) { throw "MapleStory.exe not found in $ClientRoot" }

# 1) Compatibility flags
$layers = 'HKCU:\Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers'
if (-not (Test-Path $layers)) { New-Item -Path $layers -Force | Out-Null }
$flags = 'WINXPSP3 RUNASADMIN HIGHDPIAWARE DISABLEDXMAXIMIZEDWINDOWEDMODE 640X480 DPIUNAWARE'
New-ItemProperty -Path $layers -Name $exe -PropertyType String -Value $flags -Force | Out-Null
Info "Compat flags set: $flags"

# 2) dinput8.dll
$src = "$env:WINDIR\SysWOW64\dinput8.dll"
$dst = Join-Path $ClientRoot 'dinput8.dll'
if (Test-Path $src) {
  if (-not (Test-Path $dst)) { Copy-Item -Force -Path $src -Destination $dst }
  Info "dinput8.dll ensured in client folder"
} else {
  Info "WARNING: dinput8.dll not found in SysWOW64"
}

# 3) Unblock downloaded files
Get-ChildItem -Path $ClientRoot -Recurse -File -ErrorAction SilentlyContinue |
  ForEach-Object { try { Unblock-File -Path $_.FullName -ErrorAction SilentlyContinue } catch {} }
Info "Removed Zone.Identifier from client files (if any)"

# 4) Optional hosts patch
if ($PatchHosts) {
  $hostsPath = "$env:SystemRoot\System32\drivers\etc\hosts"
  try {
    $content = Get-Content $hostsPath -ErrorAction Stop
    if (-not ($content -match '^\s*127\.0\.0\.1\s+localhost')) {
      Add-Content -Path $hostsPath -Value "127.0.0.1 localhost"
      Info "Added '127.0.0.1 localhost' to hosts"
    }
    if (-not ($content -match '^\s*::1\s+localhost')) {
      Add-Content -Path $hostsPath -Value "::1 localhost"
      Info "Added '::1 localhost' to hosts"
    }
  } catch {
    Info "WARNING: Could not modify hosts file (admin rights may be required): $_"
  }
}

Info "Done. Launching MapleStory as Admin..."
Start-Process -FilePath $exe -WorkingDirectory $ClientRoot -Verb RunAs
