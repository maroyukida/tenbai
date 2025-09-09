# Koetomo end-to-end bootstrap using iCloud+ Hide My Email.
# 1) Create iCloud alias (Playwright, interactive first run)
# 2) Register Koetomo with alias email (Appium)
# 3) Poll iCloud IMAP and open verification URL in MuMu

param(
  [string]$Udid = "127.0.0.1:16932",
  [string]$Appium = "http://localhost:4725/wd/hub",
  [string]$Password = "Abc12345!",
  [string]$Label = "koetomo",
  [string]$Note = "batch",
  [string]$ProfileDir = ".playwright-icloud",
  [string]$SubjectHint = "koetomo",
  [switch]$Headless
)

$ErrorActionPreference = 'Stop'
function Require-Cmd {
  param([string]$cmd)
  $loc = (Get-Command $cmd -ErrorAction SilentlyContinue)
  if (-not $loc) { throw "Command not found: $cmd" }
}

function Ensure-Playwright {
  try { python - <<'PY'
import importlib, sys
import pkgutil
sys.exit(0 if pkgutil.find_loader('playwright') else 1)
PY
  if ($LASTEXITCODE -ne 0) { pip install --disable-pip-version-check playwright -q }
  playwright install chromium | Out-Null
  } catch {}
}

Require-Cmd python
Ensure-Playwright

Write-Host "[1/3] Creating iCloud alias (browser may open; login if needed)" -ForegroundColor Yellow
$aliasLine = python scripts/icloud_alias.py --label $Label --note $Note --profile $ProfileDir --headless $([string]$Headless.IsPresent).ToLower()
$alias = ($aliasLine | Select-String -Pattern '^ALIAS_EMAIL:' | ForEach-Object { $_.Line.Split(':',2)[1].Trim() }) | Select-Object -First 1
if (-not $alias) { throw "Alias not captured. Please ensure login completed and re-run." }
Write-Host "Alias: $alias" -ForegroundColor Green

Write-Host "[2/3] Registering Koetomo (UDID=$Udid)" -ForegroundColor Yellow
python scripts/koetomo_full_register.py $alias $Password $Udid $Appium

Write-Host "[3/3] Waiting verification mail via iCloud IMAP" -ForegroundColor Yellow
if (-not $env:IC_USER -or -not $env:IC_APP_PASS) {
  Write-Warning "IC_USER / IC_APP_PASS env vars not set. Skipping IMAP verification step."
  Write-Host "Run: setx IC_USER your_icloud_login@icloud.com; setx IC_APP_PASS <app-password>" -ForegroundColor Yellow
  exit 0
}
python scripts/verify_email_imap.py --udid $Udid --host imap.mail.me.com --user $env:IC_USER --app-pass $env:IC_APP_PASS --to $alias --subject $SubjectHint --timeout 900

Write-Host "Done." -ForegroundColor Green

