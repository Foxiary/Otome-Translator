const {app, BrowserWindow, dialog, ipcMain, shell, Notification} = require('electron');
const fs = require('node:fs');
const path = require('node:path');
const {spawn, spawnSync} = require('node:child_process');
const {engines} = require('./engines');
const {checkForUpdate} = require('./update-check');
const {normalizePatchSettings} = require('./patch-settings');
const {isXlsx} = require('./patch-ui');
const {recipeFor, setupError} = require('./patch-recipe');

let window;
let currentRun = null;
let settings;
let lastUpdate = null;
let updateRequest = null;
// The engine commit this build carries. It must name the commit
// engines/otomate is pinned at; `npm run check` refuses a build where the
// two differ. Update notices compare the app version with the latest
// Otome Translator release, not with a new engine commit.
const SOURCE_COMMIT = '08807f7e9783afae1aaf6cf9058d47a4c7039e21';
const engineById = new Map(engines.map(engine => [engine.id, engine]));
const toolById = new Map(engines.flatMap(engine => engine.tools.map(tool => [tool.id, {engine, tool}])));

function settingsPath() { return path.join(app.getPath('userData'), 'settings.json'); }
// Until 1.2.1 the package was named ve-es-desktop, and Electron keys the user data
// folder on the name. Copy the old settings once; the paths inside them still
// point at the old folder, where the workspace and Python environment stay.
function migrateSettings() {
  const legacy = path.join(app.getPath('appData'), 've-es-desktop', 'settings.json');
  if (fs.existsSync(settingsPath()) || !fs.existsSync(legacy)) return;
  fs.mkdirSync(path.dirname(settingsPath()), {recursive: true});
  fs.copyFileSync(legacy, settingsPath());
}
function loadSettings() {
  try { migrateSettings(); } catch {}
  try { settings = JSON.parse(fs.readFileSync(settingsPath(), 'utf8')); }
  catch { settings = {}; }
  // One workspace per engine. Before the Unity engine there was a single one,
  // and it belonged to the Otomate tools.
  settings.workspaces ||= {};
  if (settings.workspace && !settings.workspaces.otomate) settings.workspaces.otomate = settings.workspace;
  delete settings.workspace;
  for (const engine of engines) {
    settings.workspaces[engine.id] ||= path.join(app.getPath('userData'),
      engine.id === 'otomate' ? 'workspace' : `workspace-${engine.id}`);
  }
  if (!engineById.has(settings.engine)) settings.engine = 'otomate';
  settings.python ||= process.platform === 'win32' ? 'py' : 'python3';
  settings.history ||= [];
  settings.values ||= {};
  settings = normalizePatchSettings(settings, engines.map(engine => engine.id));
}
function saveSettings() {
  fs.mkdirSync(path.dirname(settingsPath()), {recursive: true});
  fs.writeFileSync(settingsPath(), JSON.stringify(settings, null, 2));
}
function activeEngine() { return engineById.get(settings.engine); }
function workspace() { return settings.workspaces[settings.engine]; }
function enginePath(engine) { return path.resolve(__dirname, '..', 'engines', engine.dir); }
function sha256(data) { return require('node:crypto').createHash('sha256').update(data).digest('hex'); }
function copyMissing(source, target, relative, previousHashes) {
  if (!fs.existsSync(source)) return;
  const stat = fs.statSync(source);
  if (stat.isDirectory()) {
    if (['__pycache__', '.git'].includes(path.basename(source))) return;
    fs.mkdirSync(target, {recursive: true});
    for (const name of fs.readdirSync(source)) copyMissing(path.join(source, name), path.join(target, name), `${relative}/${name}`, previousHashes);
  } else if (!fs.existsSync(target)) fs.copyFileSync(source, target);
  else if (previousHashes[relative]) {
    // Hashes are recorded over LF text, so a CRLF checkout must match too.
    const data = fs.readFileSync(target);
    const lf = Buffer.from(data.toString('latin1').split('\r\n').join('\n'), 'latin1');
    if ([sha256(data), sha256(lf)].includes(previousHashes[relative])) fs.copyFileSync(source, target);
  }
}
function prepareWorkspace(folder, engine) {
  fs.mkdirSync(folder, {recursive: true});
  for (const name of engine.copy) {
    copyMissing(path.join(enginePath(engine), name), path.join(folder, name), name, engine.hashes);
  }
  copyMissing(path.resolve(__dirname, '..', 'requirements.txt'), path.join(folder, 'requirements.txt'), 'requirements.txt', engine.hashes);
}
function pythonCheck() {
  const modules = activeEngine().modules.join(', ');
  const result = spawnSync(settings.python, ['-c',
    `import sys, ${modules}; print(sys.version.split()[0])`],
    {encoding: 'utf8', timeout: 10000, windowsHide: true});
  return {ok: result.status === 0, version: result.status === 0 ? result.stdout.trim() : '',
    message: result.status === 0 ? '' : (result.stderr || result.error?.message || 'Python could not start').trim()};
}
function emit(event, payload) { if (window && !window.isDestroyed()) window.webContents.send(event, payload); }
function performUpdateCheck() {
  if (updateRequest) return updateRequest;
  updateRequest = checkForUpdate(app.getVersion()).then(result => {
    lastUpdate = {...result, dismissed: settings.dismissedUpdateTag === result.tag};
    if (result.status === 'available' && settings.lastNotifiedUpdateTag !== result.tag) {
      settings.lastNotifiedUpdateTag = result.tag;
      saveSettings();
      if (app.isPackaged && Notification.isSupported()) {
        const notice = new Notification({title: 'Otome Translator update',
          body: `Version ${result.latestVersion} is available.`});
        notice.on('click', () => {window?.show(); window?.focus();});
        notice.show();
      }
    }
    return lastUpdate;
  }).catch(error => ({status: 'error', message: error.message})).finally(() => {updateRequest = null;});
  return updateRequest;
}
function displayName(arg) { return arg.name.replace(/^--/, '').replace(/-/g, ' '); }
function makeArgs(tool, values) {
  const args = [...tool.prefix];
  const positionals = tool.args.filter(arg => arg.positional);
  for (let i = 0; i < positionals.length; i++) {
    const arg = positionals[i];
    const value = String(values[arg.name] ?? '').trim();
    if (!value && arg.required) throw new Error(`${displayName(arg)} is required.`);
    if (value || i < positionals.length - 1) args.push(value);
  }
  for (const arg of tool.args.filter(arg => !arg.positional)) {
    const raw = values[arg.name];
    if (arg.kind === 'bool') { if (raw) args.push(arg.name); continue; }
    const list = arg.repeat ? String(raw ?? '').split(/\r?\n/).map(x => x.trim()).filter(Boolean) : [String(raw ?? '').trim()];
    if (!list.length || !list[0]) {
      if (arg.required) throw new Error(`${displayName(arg)} is required.`);
      continue;
    }
    for (const value of list) {
      if (arg.kind === 'number' && !Number.isFinite(Number(value))) throw new Error(`${displayName(arg)} must be a number.`);
      args.push(arg.name, value);
    }
  }
  return args;
}
function createWindow() {
  window = new BrowserWindow({
    width: 1450, height: 940, minWidth: 1050, minHeight: 690,
    title: 'Otome Translator', backgroundColor: '#11131b',
    icon: path.resolve(__dirname, '..', 'assets', 'icon.png'),
    webPreferences: {preload: path.join(__dirname, 'preload.js'), contextIsolation: true,
      nodeIntegration: false, sandbox: true}
  });
  window.loadFile(path.join(__dirname, 'index.html'));
  window.webContents.setWindowOpenHandler(() => ({action: 'deny'}));
}

app.whenReady().then(() => {
  if (process.platform === 'win32') app.setAppUserModelId('dev.vees.desktop');
  loadSettings();
  prepareWorkspace(workspace(), activeEngine());
  saveSettings();
  createWindow();
  const updateTimer = setInterval(() => {
    performUpdateCheck().then(result => emit('update-status', result));
  }, 24 * 60 * 60 * 1000);
  updateTimer.unref();
  app.on('activate', () => { if (BrowserWindow.getAllWindows().length === 0) createWindow(); });
});
app.on('window-all-closed', () => { if (process.platform !== 'darwin') app.quit(); });
app.on('before-quit', () => { if (currentRun) currentRun.child.kill(); });

function publicEngines() {
  return engines.map(({id, name, subtitle, docs, flow, modules, groups, symbols, summaries, tools}) =>
    ({id, name, subtitle, docs, flow, modules, groups, symbols, summaries, tools}));
}
ipcMain.handle('state', () => ({engines: publicEngines(), settings, workspace: workspace(),
  python: pythonCheck(), running: !!currentRun, sourceCommit: SOURCE_COMMIT, appVersion: app.getVersion()}));
ipcMain.handle('set-engine', (_event, id) => {
  if (currentRun) throw new Error('Wait for the current command to finish before switching engines.');
  const engine = engineById.get(id);
  if (!engine) throw new Error('Unknown engine.');
  settings.engine = id;
  prepareWorkspace(workspace(), engine);
  saveSettings();
  return {settings, workspace: workspace(), python: pythonCheck()};
});
ipcMain.handle('check-update', () => performUpdateCheck());
ipcMain.handle('dismiss-update', (_event, tag) => {
  if (lastUpdate?.status !== 'available' || tag !== lastUpdate.tag) return false;
  settings.dismissedUpdateTag = tag;
  saveSettings();
  lastUpdate.dismissed = true;
  return true;
});
ipcMain.handle('open-update', () => {
  if (lastUpdate?.status !== 'available') return false;
  return shell.openExternal(lastUpdate.url);
});
ipcMain.handle('choose-workspace', async () => {
  const result = await dialog.showOpenDialog(window, {title: `Choose a ${activeEngine().name} project folder`,
    defaultPath: workspace(), properties: ['openDirectory', 'createDirectory']});
  if (result.canceled) return null;
  prepareWorkspace(result.filePaths[0], activeEngine());
  settings.workspaces[settings.engine] = result.filePaths[0];
  saveSettings();
  return {workspace: workspace(), python: pythonCheck()};
});
ipcMain.handle('choose-path', async (_event, kind, current) => {
  const defaultPath = current || workspace();
  if (kind === 'save') {
    const result = await dialog.showSaveDialog(window, {defaultPath});
    return result.canceled ? null : result.filePath;
  }
  const properties = kind === 'dir' ? ['openDirectory', 'createDirectory'] : ['openFile', 'openDirectory'];
  const result = await dialog.showOpenDialog(window, {defaultPath, properties});
  return result.canceled ? null : result.filePaths[0];
});
ipcMain.handle('choose-python', async () => {
  const result = await dialog.showOpenDialog(window, {title: 'Choose a Python executable', properties: ['openFile']});
  if (result.canceled) return null;
  settings.python = result.filePaths[0];
  saveSettings();
  return {python: settings.python, check: pythonCheck()};
});
ipcMain.handle('setup-python', () => {
  if (currentRun) throw new Error('Another command is already running.');
  const runId = `${Date.now()}-setup`;
  const environment = path.join(app.getPath('userData'), 'python-env');
  const executable = process.platform === 'win32' ? path.join(environment, 'Scripts', 'python.exe') : path.join(environment, 'bin', 'python');
  currentRun = {runId, child: null, id: 'setup', cancelled: false};
  emit('run-start', {runId, id: 'setup', title: 'Set up Python', started: new Date().toISOString(),
    command: [settings.python, '-m', 'venv', environment]});
  const step = (command, args) => new Promise(resolve => {
    if (currentRun?.cancelled) return resolve(130);
    emit('run-output', {runId, stream: 'stdout', text: `$ ${[command, ...args].join(' ')}\n`});
    const child = spawn(command, args, {cwd: workspace(), windowsHide: true, shell: false});
    currentRun.child = child;
    child.stdout.on('data', data => emit('run-output', {runId, stream: 'stdout', text: data.toString('utf8')}));
    child.stderr.on('data', data => emit('run-output', {runId, stream: 'stderr', text: data.toString('utf8')}));
    child.on('error', error => {emit('run-output', {runId, stream: 'stderr', text: `${error.message}\n`});resolve(1);});
    child.on('close', code => resolve(code ?? 1));
  });
  (async () => {
    let code = fs.existsSync(executable) ? 0 : await step(settings.python, ['-m', 'venv', environment]);
    if (code === 0 && !currentRun.cancelled) code = await step(executable,
      ['-m', 'pip', 'install', '--disable-pip-version-check', '-r', path.join(workspace(), 'requirements.txt')]);
    if (code === 0 && !currentRun.cancelled) {
      settings.python = executable;
      saveSettings();
      emit('run-output', {runId, stream: 'stdout', text: '\nPython environment is ready.\n'});
    }
    const cancelled = currentRun.cancelled;
    currentRun = null;
    emit('run-end', {runId, code: cancelled ? 130 : code, signal: cancelled ? 'cancelled' : null});
  })().catch(error => {
    emit('run-output', {runId, stream: 'stderr', text: `${error.stack || error}\n`});
    currentRun = null;
    emit('run-end', {runId, code: 1, signal: null});
  });
  return {runId};
});
ipcMain.handle('open-workspace', () => shell.openPath(workspace()));
ipcMain.handle('open-document', (_event, name) => {
  if (!activeEngine().docs.some(([, doc]) => doc === name)) throw new Error('Unknown document');
  return shell.openPath(path.join(workspace(), name));
});
ipcMain.handle('run-tool', (_event, id, values) => {
  if (currentRun) throw new Error('Another command is already running.');
  const entry = toolById.get(id);
  if (!entry || entry.engine.id !== settings.engine) throw new Error('Unknown tool.');
  const {tool} = entry;
  if (!values || typeof values !== 'object') throw new Error('Missing input values.');
  const args = makeArgs(tool, values);
  const root = path.resolve(workspace());
  const script = path.resolve(root, tool.script);
  if (!script.startsWith(root + path.sep)) throw new Error('Invalid script path.');
  if (!fs.existsSync(script)) throw new Error('Script is missing from the project folder.');
  settings.values[id] = values;
  saveSettings();
  const runId = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  const started = new Date().toISOString();
  const child = spawn(settings.python, ['-u', script, ...args],
    {cwd: root, env: {...process.env, PYTHONIOENCODING: 'utf-8'}, windowsHide: true, shell: false});
  currentRun = {runId, child, id};
  emit('run-start', {runId, id, title: tool.title, started, command: [settings.python, tool.script, ...args]});
  child.stdout.on('data', data => emit('run-output', {runId, stream: 'stdout', text: data.toString('utf8')}));
  child.stderr.on('data', data => emit('run-output', {runId, stream: 'stderr', text: data.toString('utf8')}));
  child.on('error', error => emit('run-output', {runId, stream: 'stderr', text: `${error.message}\n`}));
  child.on('close', (code, signal) => {
    currentRun = null;
    settings.history.unshift({id, engine: settings.engine, title: tool.title, started, code, signal});
    settings.history = settings.history.slice(0, 30);
    saveSettings();
    emit('run-end', {runId, code, signal});
  });
  return {runId};
});
ipcMain.handle('cancel-run', () => {
  if (!currentRun) return false;
  currentRun.cancelled = true;
  currentRun.child?.kill();
  return true;
});
ipcMain.handle('set-language', (_event, language) => {
  if (language !== 'en' && language !== 'vi') throw new Error('Unknown language.');
  settings.language = language;
  saveSettings();
  return {settings};
});
ipcMain.handle('set-patch', (_event, fields) => {
  const current = settings.patch[settings.engine];
  if (Object.prototype.hasOwnProperty.call(fields, 'sheetPath')) current.sheetPath = String(fields.sheetPath || '');
  if (Object.prototype.hasOwnProperty.call(fields, 'outputPath')) current.outputPath = String(fields.outputPath || '');
  if (Object.prototype.hasOwnProperty.call(fields, 'group')) current.group = fields.group || null;
  saveSettings();
  return {settings};
});
ipcMain.handle('open-output', () => shell.openPath(settings.patch[settings.engine].outputPath));

function projectAssets(engineId) {
  const folder = settings.workspaces[engineId];
  if (!folder || !fs.existsSync(folder)) return {hasGameFiles: false, hasFonts: false};
  const names = fs.readdirSync(folder);
  if (engineId === 'otomate') {
    return {
      hasGameFiles: names.includes('STORY.cpk'),
      hasFonts: names.includes('fonts.json')
    };
  }
  const bundled = names.some(name => /\.(bundle|assets)$/i.test(name));
  return {hasGameFiles: bundled, hasFonts: bundled || names.some(name => /\.(ttf|otf)$/i.test(name))};
}
function outputHasPatch(folder) {
  if (!folder || !fs.existsSync(folder)) return false;
  return fs.readdirSync(folder).some(name => name !== 'runs');
}
function spawnPython(script, args, cwd) {
  return new Promise(resolve => {
    if (!currentRun || currentRun.cancelled) return resolve({code: 130, stdout: ''});
    const child = spawn(settings.python, ['-u', script, ...args],
      {cwd, env: {...process.env, PYTHONIOENCODING: 'utf-8'}, windowsHide: true, shell: false});
    currentRun.child = child;
    let stdout = '';
    const runId = currentRun.runId;
    child.stdout.on('data', data => {
      const text = data.toString('utf8');
      stdout += text;
      emit('run-output', {runId, stream: 'stdout', text});
    });
    child.stderr.on('data', data => emit('run-output', {runId, stream: 'stderr', text: data.toString('utf8')}));
    child.on('error', error => {
      emit('run-output', {runId, stream: 'stderr', text: `${error.message}\n`});
      resolve({code: 1, stdout});
    });
    child.on('close', code => resolve({code: code ?? 1, stdout}));
  });
}
function patchFindings(stdout) {
  return stdout.split(/\r?\n/).filter(Boolean).map(line => {
    try { return JSON.parse(line); } catch { return null; }
  }).filter(Boolean);
}
ipcMain.handle('run-patch', async (_event, options = {}) => {
  if (currentRun) throw new Error('Another command is already running.');
  const engineId = settings.engine;
  const patch = settings.patch[engineId];
  const projectPath = settings.workspaces[engineId];
  const outputPath = patch.outputPath;
  const originalPath = patch.sheetPath;
  if (!isXlsx(path.basename(originalPath || ''))) return {error: 'xlsx', skip: false};
  if (setupError({projectPath, outputPath, ...projectAssets(engineId)})) return {error: 'setup', skip: false};
  if (outputHasPatch(outputPath) && options.confirmed !== true) return {needsConfirm: true, skip: false};
  const runDirectory = path.join(outputPath, 'runs', `${Date.now()}`);
  const copyPath = path.join(runDirectory, 'sheet.xlsx');
  const reportPath = path.join(runDirectory, 'quarong-report.xlsx');
  let copied = false;
  try {
    fs.mkdirSync(runDirectory, {recursive: true});
    fs.copyFileSync(originalPath, copyPath);
    copied = true;
  } catch (error) {
    return {error: 'copy', message: error.message, skip: false};
  }
  const runId = `patch-${Date.now()}`;
  currentRun = {runId, child: null, cancelled: false, id: 'patch'};
  emit('run-start', {runId, id: 'patch', title: 'Create patch', started: new Date().toISOString(), command: ['patch', engineId]});
  const recipe = recipeFor(engineId);
  const findings = [];
  let blocked = false;
  let failedStep = null;
  const finish = (code, extra) => {
    const cancelled = currentRun?.cancelled;
    currentRun = null;
    emit('run-end', {runId, id: 'patch', code: cancelled ? 130 : code, signal: cancelled ? 'cancelled' : null, ...extra});
    return {started: true, runDirectory, copied, skip: false, ...extra, code: cancelled ? 130 : code};
  };
  const noteFailure = step => {blocked = true; failedStep = failedStep || step.id;};
  try {
  for (const step of recipe) {
    if (currentRun.cancelled) return finish(130, {stopped: true, findings, failedStep});
    if (step.phase === 'create' && blocked) return finish(2, {findings, skip: false, failedStep});
    emit('run-output', {runId, stream: 'stdout', text: `\n${step.phase}: ${step.id}\n`});
    let result = {code: 0, stdout: ''};
    if (step.id === 'empty-scan') {
      result = await spawnPython(path.join(__dirname, 'sheet_scan.py'), [copyPath], projectPath);
      findings.push(...patchFindings(result.stdout));
      if (result.code !== 0) noteFailure(step);
    } else if (step.id === 'unity-sheetfit') {
      const boxes = path.join(projectPath, 'text-boxes.json');
      const bundle = fs.readdirSync(projectPath).find(name => /\.(bundle|assets)$/i.test(name));
      if (!fs.existsSync(boxes) || !bundle) {
        noteFailure(step);
        emit('run-output', {runId, stream: 'stderr', text: 'Layout check could not be read.\n'});
      } else {
        result = await spawnPython(path.join(enginePath(activeEngine()), 'tools', 'sheetfit.py'),
          [copyPath, boxes, path.join(projectPath, bundle)], projectPath);
        findings.push(...patchFindings(result.stdout));
        if (result.code !== 0) noteFailure(step);
      }
    } else if (step.id === 'quarong') {
      const script = path.join(projectPath, 'tools', 'quarong.py');
      result = await spawnPython(script, [copyPath, reportPath, copyPath], projectPath);
      const readable = fs.existsSync(reportPath) && fs.readFileSync(reportPath).subarray(0, 2).toString() === 'PK';
      if (!readable || result.code !== 0) noteFailure(step);
      const scan = await spawnPython(path.join(__dirname, 'sheet_scan.py'), [copyPath], projectPath);
      findings.push(...patchFindings(scan.stdout));
      if (scan.code !== 0) noteFailure(step);
    } else if (step.id === 'filltitles-fill') {
      result = await spawnPython(path.join(projectPath, 'tools', 'filltitles.py'),
        ['fill', copyPath, copyPath], projectPath);
      if (result.code !== 0) noteFailure(step);
    } else if (step.id === 'applyvi') {
      result = await spawnPython(path.join(projectPath, 'tools', 'applyvi.py'),
        [copyPath, path.join(projectPath, 'STORY.cpk'), outputPath], projectPath);
      if (result.code !== 0) return finish(result.code, {findings, skip: false, failedStep: step.id});
    } else if (step.id === 'unity-sheet-apply') {
      const bundle = fs.readdirSync(projectPath).find(name => /\.(bundle|assets)$/i.test(name));
      if (!bundle) return finish(1, {findings, skip: false, failedStep: step.id});
      result = await spawnPython(path.join(projectPath, 'tools', 'jsonsheet.py'),
        ['apply', path.join(projectPath, bundle), copyPath, '--out', path.join(outputPath, 'patched.bundle'), '--apply'], projectPath);
      if (result.code !== 0) return finish(result.code, {findings, skip: false, failedStep: step.id});
    }
    if (step.phase === 'prepare' && blocked) return finish(result.code || 1, {findings, skip: false, failedStep});
  }
  return finish(0, {findings, complete: !blocked, skip: false, failedStep});
  } catch (error) {
    emit('run-output', {runId, stream: 'stderr', text: `${error.message}\n`});
    return finish(1, {findings, skip: false, failedStep});
  }
});

module.exports = {makeArgs};
