// Pre-release checklist validator
const fs = require('fs');
const path = require('path');

const root = path.join(__dirname, '..');
const appJsonPath = path.join(root, 'app.json');
const assetsIcon = path.join(root, 'assets', 'icon.png');
const assetsSplash = path.join(root, 'assets', 'splash.png');

function fail(msg) { console.error('✗', msg); process.exitCode = 1; }
function pass(msg) { console.log('✓', msg); }

function exists(p) { return fs.existsSync(p); }

function checkAppJson() {
  const aj = JSON.parse(fs.readFileSync(appJsonPath, 'utf8'));
  const f = (((aj||{}).expo||{}).extra||{}).firebase || {};
  const useEmu = (((aj||{}).expo||{}).extra||{}).useEmulator === true ||
    String(process.env.EXPO_PUBLIC_USE_EMULATOR||'').toLowerCase() === 'true';
  const need = ['apiKey','authDomain','projectId','storageBucket','messagingSenderId','appId'];
  let ok = true;
  if (!useEmu) {
    for (const k of need) {
      if (!f[k] || String(f[k]).startsWith('YOUR_')) { ok = false; fail(`expo.extra.firebase.${k} is missing`); }
    }
    if (ok) pass('Firebase config present');
  } else {
    pass('Emulator mode: skipping Firebase config checks');
  }

  const android = (aj.expo||{}).android || {};
  if (!useEmu) {
    if (!android.package || android.package.includes('example')) fail('Android package is placeholder'); else pass('Android package set');
  } else {
    pass('Emulator mode: skipping package checks');
  }
  const ios = (aj.expo||{}).ios || {};
  if (!useEmu) {
    if (!ios.bundleIdentifier || ios.bundleIdentifier.includes('example')) fail('iOS bundleIdentifier is placeholder'); else pass('iOS bundleIdentifier set');
  }
}

function checkAssets() {
  if (!exists(assetsIcon)) fail('assets/icon.png missing'); else pass('assets/icon.png exists');
  if (!exists(assetsSplash)) fail('assets/splash.png missing'); else pass('assets/splash.png exists');
}

function main() {
  console.log('Preflight checks...');
  try { checkAppJson(); } catch (e) { fail('app.json parse error: '+e.message); }
  checkAssets();
  console.log('Done. (non-zero exit code means issues)');
}

main();
