// CLI to write Firebase config into app.json interactively
const fs = require('fs');
const path = require('path');
const readline = require('readline');

const appJsonPath = path.join(__dirname, '..', 'app.json');

function loadAppJson() {
  return JSON.parse(fs.readFileSync(appJsonPath, 'utf8'));
}
function saveAppJson(json) {
  fs.writeFileSync(appJsonPath, JSON.stringify(json, null, 2));
}

function ask(q) {
  return new Promise((resolve) => {
    const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
    rl.question(q, (ans) => { rl.close(); resolve(ans.trim()); });
  });
}

(async () => {
  console.log('Apply Firebase config to app.json');
  const apiKey = await ask('apiKey: ');
  const authDomain = await ask('authDomain: ');
  const projectId = await ask('projectId: ');
  const storageBucket = await ask('storageBucket: ');
  const messagingSenderId = await ask('messagingSenderId: ');
  const appId = await ask('appId: ');

  const pkgAndroid = await ask('Android package (e.g. com.example.pocchari) [enter to skip]: ');
  const pkgIOS = await ask('iOS bundleIdentifier (e.g. com.example.pocchari) [enter to skip]: ');

  const aj = loadAppJson();
  aj.expo = aj.expo || {};
  aj.expo.extra = aj.expo.extra || {};
  aj.expo.extra.firebase = {
    apiKey, authDomain, projectId, storageBucket, messagingSenderId, appId,
  };
  if (pkgAndroid) {
    aj.expo.android = aj.expo.android || {};
    aj.expo.android.package = pkgAndroid;
  }
  if (pkgIOS) {
    aj.expo.ios = aj.expo.ios || {};
    aj.expo.ios.bundleIdentifier = pkgIOS;
  }
  saveAppJson(aj);
  console.log('Updated app.json');
})();

