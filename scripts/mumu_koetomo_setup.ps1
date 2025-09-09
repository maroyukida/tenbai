# Requires: MuMu Player Global 12 installed (MuMuManager.exe), ADB bundled
# Optional: Appium server running (for Play Store login/UI automation)
#
# Usage examples:
#   # 1) Create+launch a new instance, sideload APK, launch app
#   powershell -ExecutionPolicy Bypass -File scripts/mumu_koetomo_setup.ps1 -CreateNew -KoetomoApk "C:\path\jp.co.meetscom.koetomo.apk"
#
#   # 2) Use Play Store flow (needs Appium+Google credentials)
#   $env:GOOGLE_EMAIL = "you@example.com"
#   $env:GOOGLE_PASSWORD = "your-password"
#   powershell -ExecutionPolicy Bypass -File scripts/mumu_koetomo_setup.ps1 -CreateNew -UsePlayStore -AppiumUrl "http://localhost:4725/wd/hub"
#
#   # 3) Reuse existing running instance by index 9
#   powershell -ExecutionPolicy Bypass -File scripts/mumu_koetomo_setup.ps1 -VmIndex 9 -UsePlayStore -AppiumUrl "http://localhost:4725/wd/hub"

[CmdletBinding()]
param(
  [switch]$CreateNew,
  [int]$VmIndex,
  [string]$AppiumUrl = "http://localhost:4725/wd/hub",
  [switch]$UsePlayStore,
  [string]$KoetomoApk,
  [int]$CreateCount = 1,
  [int]$LaunchTimeoutSec = 180
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Get-MuMuBinPath {
  $base = "C:\\Program Files\\Netease\\MuMuPlayerGlobal-12.0\\shell"
  if (-not (Test-Path $base)) {
    throw "MuMu shell directory not found: $base"
  }
  return $base
}

function Invoke-MuMuManager {
  param(
    [Parameter(Mandatory=$true)][string]$ArgsString
  )
  $shell = Get-MuMuBinPath
  $exe = Join-Path $shell 'MuMuManager.exe'
  Write-Verbose "MuMuManager.exe $ArgsString"
  & $exe @($ArgsString.Split(' ')) 2>&1 | Out-String
}

function Get-PlayersInfo {
  $raw = Invoke-MuMuManager -ArgsString "info --vmindex all"
  try {
    $jsonStart = $raw.IndexOf('{')
    if ($jsonStart -lt 0) { throw "No JSON in output: $raw" }
    $json = $raw.Substring($jsonStart)
    return ($json | ConvertFrom-Json)
  } catch {
    throw "Failed to parse MuMu info output: $_\nRaw: $raw"
  }
}

function New-MuMuInstance {
  param(
    [int]$Count = 1
  )
  $before = Get-PlayersInfo
  [void](Invoke-MuMuManager -ArgsString "create --number $Count")
  Start-Sleep -Seconds 2
  $after = Get-PlayersInfo
  $new = @()
  foreach ($k in $after.PSObject.Properties.Name) {
    if (-not $before.PSObject.Properties.Name.Contains($k)) { $new += $k }
  }
  if (-not $new) { throw "No new players detected after create" }
  return $new | Sort-Object {[int]$_}
}

function Start-MuMuAndWaitReady {
  param(
    [Parameter(Mandatory=$true)][int]$Index,
    [int]$TimeoutSec = 180
  )
  [void](Invoke-MuMuManager -ArgsString "control --vmindex $Index launch")
  $deadline = (Get-Date).AddSeconds($TimeoutSec)
  while ((Get-Date) -lt $deadline) {
    $info = Get-PlayersInfo
    $node = $info."$Index"
    if ($null -ne $node -and $node.is_android_started -and $node.is_process_started) {
      Write-Host "MuMu index=$Index is ready. adb_port=$($node.adb_port)" -ForegroundColor Green
      return $node
    }
    Start-Sleep -Seconds 2
  }
  throw "Timed out waiting for MuMu index=$Index to start"
}

function Connect-Adb {
  param(
    [Parameter(Mandatory=$true)][int]$Index
  )
  $out = Invoke-MuMuManager -ArgsString "adb --vmindex $Index --cmd connect"
  Write-Verbose $out
  $info = Get-PlayersInfo
  $node = $info."$Index"
  if ($null -eq $node.adb_port) { throw "adb_port not found for index=$Index" }
  return "127.0.0.1:$($node.adb_port)"
}

function Invoke-Adb {
  param(
    [Parameter(Mandatory=$true)][string]$Udid,
    [Parameter(Mandatory=$true)][string]$ArgsString
  )
  $shell = Get-MuMuBinPath
  $adb = Join-Path $shell 'adb.exe'
  Write-Verbose "adb -s $Udid $ArgsString"
  & $adb -s $Udid @($ArgsString.Split(' ')) 2>&1 | Out-String
}

function Open-PlayStoreDetails {
  param(
    [Parameter(Mandatory=$true)][string]$Udid,
    [string]$PackageId = 'jp.co.meetscom.koetomo'
  )
  $uri = "market://details?id=$PackageId"
  [void](Invoke-Adb -Udid $Udid -ArgsString "shell am start -a android.intent.action.VIEW -d $uri com.android.vending")
}

function Install-KoetomoFromApk {
  param(
    [Parameter(Mandatory=$true)][string]$Udid,
    [Parameter(Mandatory=$true)][string]$ApkPath
  )
  if (-not (Test-Path $ApkPath)) { throw "APK not found: $ApkPath" }
  # Optional sanity check: ensure package id matches jp.co.meetscom.koetomo
  try {
    $py = Join-Path $PSScriptRoot 'apk_info.py'
    if (Test-Path $py) {
      $info = python $py $ApkPath 2>$null
      if ($LASTEXITCODE -eq 0 -and $info) {
        $pkg = ($info | Select-String -Pattern '^package:').ToString().Split(':')[-1].Trim()
        if ($pkg -and $pkg -ne 'jp.co.meetscom.koetomo') {
          Write-Warning "APK package is '$pkg' (expected 'jp.co.meetscom.koetomo'). Installing anyway — verify source."
        }
      }
    }
  } catch {}
  Write-Host "Installing APK: $ApkPath" -ForegroundColor Cyan
  $out = Invoke-Adb -Udid $Udid -ArgsString "install -r `"$ApkPath`""
  if ($out -notmatch 'Success') { throw "adb install failed: $out" }
  Write-Host "APK installed successfully" -ForegroundColor Green
}

function Install-KoetomoFromXapk {
  param(
    [Parameter(Mandatory=$true)][string]$Udid,
    [Parameter(Mandatory=$true)][string]$XapkPath
  )
  if (-not (Test-Path $XapkPath)) { throw "XAPK not found: $XapkPath" }
  Write-Host "Extracting XAPK: $XapkPath" -ForegroundColor Cyan
  $tmp = Join-Path $env:TEMP ("xapk_" + [System.Guid]::NewGuid().ToString('N'))
  New-Item -ItemType Directory -Path $tmp | Out-Null
  Add-Type -AssemblyName System.IO.Compression.FileSystem
  [System.IO.Compression.ZipFile]::ExtractToDirectory($XapkPath, $tmp)

  $manifest = Join-Path $tmp 'manifest.json'
  if (-not (Test-Path $manifest)) { throw "manifest.json not found in XAPK" }
  $m = Get-Content -Raw $manifest | ConvertFrom-Json
  $pkg = $m.package_name
  if ($pkg -and $pkg -ne 'jp.co.meetscom.koetomo') {
    Write-Warning "XAPK package is '$pkg' (expected 'jp.co.meetscom.koetomo'). Installing anyway — verify source."
  }

  $apks = @()
  foreach ($s in $m.split_apks) { $apks += (Join-Path $tmp $s.file) }
  # Ensure base APK is first
  $apks = @($apks | Sort-Object { if ($_ -match 'koetomo.apk$') { 0 } else { 1 } })

  $adb = Join-Path (Get-MuMuBinPath) 'adb.exe'
  $args = @('-s', $Udid, 'install-multiple', '-r') + $apks
  Write-Host ("adb " + ($args -join ' ')) -ForegroundColor DarkGray
  $psi = New-Object System.Diagnostics.ProcessStartInfo
  $psi.FileName = $adb
  $psi.Arguments = ($args -join ' ')
  $psi.RedirectStandardOutput = $true
  $psi.RedirectStandardError = $true
  $psi.UseShellExecute = $false
  $p = [System.Diagnostics.Process]::Start($psi)
  $std = $p.StandardOutput.ReadToEnd() + "`n" + $p.StandardError.ReadToEnd()
  $p.WaitForExit()
  if ($std -notmatch 'Success') { throw "adb install-multiple failed: $std" }
  Write-Host "XAPK installed successfully" -ForegroundColor Green
}

function Launch-Koetomo {
  param(
    [Parameter(Mandatory=$true)][string]$Udid
  )
  # Try to launch default launcher activity via monkey
  [void](Invoke-Adb -Udid $Udid -ArgsString "shell monkey -p jp.co.meetscom.koetomo -c android.intent.category.LAUNCHER 1")
}

Write-Host "=== MuMu Koetomo Bootstrap ===" -ForegroundColor Yellow

# 1) Resolve target instance index
if ($CreateNew) {
  $created = New-MuMuInstance -Count $CreateCount
  $VmIndex = [int]$created[-1]
  Write-Host "Created new MuMu index: $VmIndex" -ForegroundColor Green
} elseif ($VmIndex -ge 0) {
  Write-Host "Using existing MuMu index: $VmIndex" -ForegroundColor Green
} else {
  throw "Specify -CreateNew or -VmIndex <n>"
}

# 2) Launch and wait for ready
$node = Start-MuMuAndWaitReady -Index $VmIndex -TimeoutSec $LaunchTimeoutSec

# 3) Connect adb and get udid
$udid = Connect-Adb -Index $VmIndex
Write-Host "ADB connected: $udid" -ForegroundColor Green

# 4) Install Koetomo
if ($UsePlayStore) {
  Write-Host "Opening Play Store detail page (manual/Appium flow)" -ForegroundColor Yellow
  Open-PlayStoreDetails -Udid $udid
  # If Appium is intended, user can run the Python UI automation script separately.
  Write-Host "If Appium is running at $AppiumUrl, run the UI script to sign-in and tap Install." -ForegroundColor Yellow
} elseif ($KoetomoApk) {
  $ext = [System.IO.Path]::GetExtension($KoetomoApk)
  if ($ext -ieq '.xapk') {
    Install-KoetomoFromXapk -Udid $udid -XapkPath $KoetomoApk
  } else {
    Install-KoetomoFromApk -Udid $udid -ApkPath $KoetomoApk
  }
}

# 5) Launch Koetomo app
Launch-Koetomo -Udid $udid

Write-Host "Done. You can now proceed with in-app registration automation (Appium)." -ForegroundColor Yellow
