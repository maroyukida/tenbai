/*
  Firebase bootstrap (interactive):
  - Login via firebase-tools
  - List/select project (or input an ID)
  - List/create a Web app, fetch SDK config
  - Write config to app.json (expo.extra.firebase)
  - Deploy Firestore rules/indexes
*/
const cp = require('child_process');
const fs = require('fs');
const path = require('path');
const readline = require('readline');

const root = path.join(__dirname, '..');
const appJsonPath = path.join(root, 'app.json');

function sh(cmd, opts = {}) {
  return cp.execSync(cmd, { stdio: 'pipe', encoding: 'utf8', ...opts });
}

function ask(q) {
  return new Promise((resolve) => {
    const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
    rl.question(q, (ans) => { rl.close(); resolve(ans.trim()); });
  });
}

function ensureFirebaseCLI() {
  try {
    const v = sh('npx firebase-tools --version');
    console.log('firebase-tools', v.trim());
  } catch (e) {
    console.log('Installing firebase-tools...');
    sh('npm i -D firebase-tools');
  }
}

async function login() {
  console.log('\n== Firebase Login ==');
  try {
    // Will be no-op if already logged in
    cp.execSync('npx firebase-tools login', { stdio: 'inherit' });
  } catch (e) {
    throw new Error('Login failed');
  }
}

function listProjects() {
  try {
    const out = sh('npx firebase-tools projects:list --json');
    const json = JSON.parse(out);
    return (json?.result || json?.projects || []).map(p => ({ id: p.projectId || p.project_id, name: p.displayName || p.name }));
  } catch {
    return [];
  }
}

async function pickProject(projects) {
  if (!projects.length) {
    console.log('No projects found. Create one in console then input its ID.');
    console.log('Console: https://console.firebase.google.com/');
    const pid = await ask('Project ID: ');
    return { id: pid, name: pid };
  }
  console.log('\n== Select Project ==');
  projects.forEach((p, i) => console.log(`[${i+1}] ${p.id}  (${p.name||''})`));
  const ans = await ask(`Choose 1-${projects.length} or type projectId: `);
  const idx = parseInt(ans, 10);
  if (!isNaN(idx) && idx >= 1 && idx <= projects.length) return projects[idx-1];
  return { id: ans, name: ans };
}

function listWebApps(projectId) {
  try {
    const out = sh(`npx firebase-tools apps:list --platform WEB --project ${projectId} --json`);
    const json = JSON.parse(out);
    return (json?.result || json?.apps || []).map(a => ({ appId: a.appId || a.app_id, displayName: a.displayName || a.display_name }));
  } catch {
    return [];
  }
}

function createWebApp(projectId) {
  const name = 'Pocchari Chat';
  const out = sh(`npx firebase-tools apps:create WEB "${name}" --project ${projectId} --json`);
  const json = JSON.parse(out);
  const app = json?.result || json;
  return { appId: app.appId || app.app_id, displayName: app.displayName || app.display_name };
}

function fetchWebConfig(projectId, appId) {
  const out = sh(`npx firebase-tools apps:sdkconfig WEB ${appId} --project ${projectId}`);
  // Extract firebaseConfig = { ... } block
  const m = out.match(/firebaseConfig\s*=\s*\{([\s\S]*?)\}/);
  if (!m) throw new Error('Failed to parse SDK config');
  let body = m[1];
  // Convert to JSON: add quotes to keys, preserve quoted values
  const lines = body.split(/\n|,/).map(s => s.trim()).filter(Boolean);
  const obj = {};
  for (const line of lines) {
    const kv = line.replace(/[,{}]/g,'').trim();
    const mm = kv.match(/([a-zA-Z0-9_]+)\s*:\s*['"]?([^'"\n]+)['"]?/);
    if (mm) obj[mm[1]] = mm[2];
  }
  return obj;
}

function writeAppJson(cfg) {
  const aj = JSON.parse(fs.readFileSync(appJsonPath, 'utf8'));
  aj.expo = aj.expo || {};
  aj.expo.extra = aj.expo.extra || {};
  aj.expo.extra.firebase = cfg;
  fs.writeFileSync(appJsonPath, JSON.stringify(aj, null, 2));
  console.log('app.json updated with Firebase config');
}

function deployFirestore(projectId) {
  console.log('\n== Deploy Firestore rules/indexes ==');
  cp.execSync(`npx firebase-tools use ${projectId}`, { stdio: 'inherit' });
  cp.execSync('npx firebase-tools deploy --only firestore:rules,firestore:indexes', { stdio: 'inherit' });
}

(async () => {
  ensureFirebaseCLI();
  await login();
  const projects = listProjects();
  const proj = await pickProject(projects);
  console.log('Using project:', proj.id);

  let apps = listWebApps(proj.id);
  let app = apps[0];
  if (!app) {
    console.log('No WEB apps. Creating one...');
    app = createWebApp(proj.id);
    console.log('Created app:', app.appId);
  } else {
    console.log('Found WEB app:', app.appId);
  }

  const cfg = fetchWebConfig(proj.id, app.appId);
  writeAppJson(cfg);
  deployFirestore(proj.id);
  console.log('\nAll set. Next: run preflight.bat, then build_android_preview.bat');
})().catch((e) => {
  console.error('Bootstrap error:', e.message);
  process.exit(1);
});

