const {app, BrowserWindow, dialog, ipcMain, shell, Notification} = require('electron');
const fs = require('node:fs');
const http = require('node:http');
const path = require('node:path');
const {spawn, spawnSync} = require('node:child_process');
const {engines} = require('./engines');
const {checkForUpdate} = require('./update-check');
const {normalizePatchSettings, cleanPatchOptions} = require('./patch-settings');
const {isXlsx} = require('./patch-ui');
const {t} = require('./i18n');
const {missingFiles, jpNames} = require('./required-files');
const {readWindows, saveWindow} = require('./windows-config');
const {recipeFor, setupError} = require('./patch-recipe');
const {MAPPED_ARGS, argValue, ffugenArgs, fontJobProblem, strokeFor, withOverrides} = require('./font-map');
const {detect} = require('./detect-engine');
const {extractGame} = require('./game-extract');
const {splitGuide, documentationPage} = require('./markdown');

let window;
let currentRun = null;
let settings;
let lastUpdate = null;
let updateRequest = null;
// The engine commit this build carries. It must name the commit
// engines/otomate is pinned at; `npm run check` refuses a build where the
// two differ. Update notices compare the app version with the latest
// Otome Translator release, not with a new engine commit.
const SOURCE_COMMIT = '8d1fa50f5eda4bfea02a6b83a856b564393867dc';
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
  // Someone who already used the app has picked an engine; a fresh install has
  // not, and opens on the start page that asks for the game first.
  if (typeof settings.engineChosen !== 'boolean') settings.engineChosen = engineById.has(settings.engine);
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
    // Every earlier version the file has had (scripts/update-engine-hashes.js): an
    // untouched copy of any of them is replaced, an edited one is kept.
    const earlier = [].concat(previousHashes[relative]);
    // Hashes are recorded over LF text, so a CRLF checkout must match too.
    const data = fs.readFileSync(target);
    const lf = Buffer.from(data.toString('latin1').split('\r\n').join('\n'), 'latin1');
    if ([sha256(data), sha256(lf)].some(hash => earlier.includes(hash))) fs.copyFileSync(source, target);
  }
}
function prepareWorkspace(folder, engine) {
  fs.mkdirSync(folder, {recursive: true});
  for (const name of engine.copy) {
    copyMissing(path.join(enginePath(engine), name), path.join(folder, name), name, engine.hashes);
  }
  copyMissing(path.resolve(__dirname, '..', 'requirements.txt'), path.join(folder, 'requirements.txt'), 'requirements.txt', engine.hashes);
}
// Whether the chosen Python starts (`found`) and which of the engine's modules
// it cannot import (`missing`): the window asks for the right fix from these.
function pythonCheck() {
  const probe = ['import sys, json, importlib', 'missing = []',
    `for name in ${JSON.stringify(activeEngine().modules)}:`,
    '    try: importlib.import_module(name)',
    '    except Exception: missing.append(name)',
    'print(json.dumps({"version": sys.version.split()[0], "missing": missing}))'].join('\n');
  const result = spawnSync(settings.python, ['-c', probe], {encoding: 'utf8', timeout: 10000, windowsHide: true});
  let report = null;
  try { report = JSON.parse((result.stdout || '').trim().split(/\r?\n/).pop()); } catch {}
  if (result.status !== 0 || !report || !Array.isArray(report.missing)) {
    return {ok: false, found: false, version: '', missing: [],
      message: (result.stderr || result.error?.message || 'Python could not start').trim()};
  }
  return {ok: !report.missing.length, found: true, version: String(report.version), missing: report.missing,
    message: report.missing.length ? `No module named ${report.missing.join(', ')}` : ''};
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
        const notice = new Notification({title: t('update.notice', settings.language),
          body: t('update.noticeBody', settings.language, {version: result.latestVersion})});
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
app.on('before-quit', () => { if (currentRun) currentRun.child.kill(); docsServer?.close(); });

function publicEngines() {
  return engines.map(({id, name, subtitle, docs, flow, modules, groups, symbols, summaries, tools, vi}) =>
    ({id, name, subtitle, docs, flow, modules, groups, symbols, summaries, tools, vi}));
}
ipcMain.handle('state', () => ({engines: publicEngines(), settings, workspace: workspace(),
  python: pythonCheck(), running: !!currentRun, sourceCommit: SOURCE_COMMIT, appVersion: app.getVersion()}));
ipcMain.handle('set-engine', (_event, id) => {
  if (currentRun) throw new Error('Wait for the current command to finish before switching engines.');
  const engine = engineById.get(id);
  if (!engine) throw new Error('Unknown engine.');
  settings.engine = id;
  settings.engineChosen = true;
  prepareWorkspace(workspace(), engine);
  saveSettings();
  return {settings, workspace: workspace(), python: pythonCheck()};
});
// The files a dropped game hands to the tools' fields, named by what they are;
// the page matches them to fields by each field's own wording.
function relatedFiles(result) {
  const {input, kind} = result;
  const isFile = file => { try { return fs.statSync(file).isFile(); } catch { return false; } };
  const sibling = (file, from, to) => { const other = file.replace(from, to); return isFile(other) ? other : null; };
  const out = {};
  if (kind === 'nsp') out.nsp = input;
  if (kind === 'xci') out.xci = input;
  if (kind === 'file') {
    const name = path.basename(input).toLowerCase();
    if (name.endsWith('.memfs')) Object.assign(out, {memfs: input, membody: sibling(input, /\.memfs$/i, '.membody')});
    if (name.endsWith('.membody')) Object.assign(out, {membody: input, memfs: sibling(input, /\.membody$/i, '.memfs')});
    if (name === 'main') out.exe = input;
    if (name.endsWith('.tat')) out.tat = input;
    if (name.endsWith('.cpk')) out.cpk = input;
    if (/\.(assets|bundle)$/.test(name)) out.assets = input;
  }
  if (kind === 'folder') {
    const first = list => list.map(rel => path.join(input, rel)).find(isFile) || null;
    out.memfs = first(['romfs/common/script.memfs', 'common/script.memfs', 'script.memfs']);
    if (out.memfs) out.membody = sibling(out.memfs, /\.memfs$/i, '.membody');
    out.exe = first(['exefs/main', 'main']);
    // A mod folder holds romfs/ (and maybe exefs/) the way the emulator loads it.
    if (fs.existsSync(path.join(input, 'romfs'))) out.mod = input;
  }
  return Object.fromEntries(Object.entries(out).filter(([, value]) => value));
}
// Picking the engine already in use (from the start page, or a detection that
// matched it) counts as choosing it too.
ipcMain.handle('engine-chosen', () => {
  settings.engineChosen = true;
  saveSettings();
  return {settings};
});
ipcMain.handle('detect-engine', (_event, input) => {
  if (typeof input !== 'string' || !input) throw new Error('Nothing to read.');
  const result = detect(input, {keys: settings.keysPath});
  return {...result, files: relatedFiles(result)};
});
// ---------------------------------------------------------------- projects
// A project folder holds the engine's tools, the original game files and a
// clean mod/ (romfs/, exefs/) that is the mod itself. The Otomate tools read the
// game's archives from the project root (SYSTEM.cpk, STORY.cpk beside build.py),
// so its RomFS goes there; the other engines take paths and get game/romfs/.
function projectLayout(folder, engineId) {
  return {
    romfs: engineId === 'otomate' ? folder : path.join(folder, 'game', 'romfs'),
    exefs: path.join(folder, 'game', 'exefs'),
    mod: path.join(folder, 'mod')
  };
}
// Fields of the engine's tools a new project can fill, named as detection names them.
function projectFiles(folder, engineId, gameFile) {
  const layout = projectLayout(folder, engineId);
  const isFile = file => { try { return fs.statSync(file).isFile(); } catch { return false; } };
  const memfs = path.join(layout.romfs, 'common', 'script.memfs');
  const files = {mod: layout.mod};
  if (gameFile) files[/\.xci$/i.test(gameFile) ? 'xci' : 'nsp'] = gameFile;
  if (isFile(memfs)) Object.assign(files, {memfs, membody: memfs.replace(/\.memfs$/, '.membody'), jp: path.dirname(memfs)});
  if (isFile(path.join(layout.exefs, 'main'))) files.exe = path.join(layout.exefs, 'main');
  return files;
}
function safeName(text) {
  return String(text || 'Game').replace(/[\\/:*?"<>|]+/g, ' ').replace(/\s+/g, ' ').trim().slice(0, 80) || 'Game';
}
let projectJob = null;
// A free folder for a new project: inside `parent` (Documents/Otome Translator
// by default), named after the game. An empty folder chosen as parent is used as is.
ipcMain.handle('project-suggest', (_event, name, chosen) => {
  const isEmptyDir = dir => { try { return fs.statSync(dir).isDirectory() && !fs.readdirSync(dir).length; } catch { return false; } };
  if (typeof chosen === 'string' && path.isAbsolute(chosen) && isEmptyDir(chosen)) return chosen;
  const parent = typeof chosen === 'string' && path.isAbsolute(chosen) ? chosen : path.join(app.getPath('documents'), 'Otome Translator');
  let folder = path.join(parent, safeName(name));
  for (let n = 2; fs.existsSync(folder) && fs.readdirSync(folder).length; n++) folder = path.join(parent, `${safeName(name)} ${n}`);
  return folder;
});
ipcMain.handle('project-cancel', () => { if (projectJob) projectJob.cancelled = true; return !!projectJob; });
// options: folder (new or empty), gameFile (.nsp/.xci) or gameFolder (a RomFS
// already taken out, e.g. by Ryujinx), modFolder (an existing mod to carry on).
ipcMain.handle('project-create', async (_event, options = {}) => {
  if (currentRun || projectJob) throw new Error('Wait for the current command to finish first.');
  const {folder, gameFile, gameFolder, modFolder} = options;
  if (typeof folder !== 'string' || !path.isAbsolute(folder)) throw new Error('Choose where to create the project.');
  const existed = fs.existsSync(folder);
  if (existed && fs.readdirSync(folder).length) {
    throw new Error('not-empty: that folder already has files in it');
  }
  const engine = activeEngine();
  const layout = projectLayout(folder, engine.id);
  const job = projectJob = {cancelled: false};
  const progress = payload => emit('project-progress', payload);
  try {
    fs.mkdirSync(path.join(layout.mod, 'romfs'), {recursive: true});
    fs.mkdirSync(path.join(layout.mod, 'exefs'), {recursive: true});
    let summary = null;
    if (gameFile) {
      progress({stage: 'extract', done: 0, total: 0, files: 0, count: 0, current: ''});
      summary = await extractGame(gameFile, {romfsDir: layout.romfs, exefsDir: layout.exefs, keys: settings.keysPath,
        onProgress: p => progress({stage: 'extract', ...p}), isCancelled: () => job.cancelled});
    } else if (gameFolder) {
      progress({stage: 'copy-game'});
      await fs.promises.cp(gameFolder, layout.romfs, {recursive: true, errorOnExist: false});
    }
    if (job.cancelled) throw Object.assign(new Error('stopped'), {code: 'cancelled'});
    if (modFolder) {
      progress({stage: 'copy-mod'});
      await fs.promises.cp(modFolder, layout.mod, {recursive: true});
    }
    progress({stage: 'prepare'});
    prepareWorkspace(folder, engine);
    settings.workspaces[engine.id] = folder;
    saveSettings();
    return {workspace: folder, layout, summary, files: projectFiles(folder, engine.id, gameFile), python: pythonCheck()};
  } catch (error) {
    // A folder this call made holds only a partial project: take it away again.
    if (!existed) fs.rmSync(folder, {recursive: true, force: true});
    throw Object.assign(new Error(error.code ? `${error.code}: ${error.message}` : error.message), {code: error.code});
  } finally {
    projectJob = null;
  }
});
ipcMain.handle('choose-detect-input', async (_event, kind) => {
  const result = await dialog.showOpenDialog(window, {properties: [kind === 'dir' ? 'openDirectory' : 'openFile']});
  return result.canceled ? null : result.filePaths[0];
});
ipcMain.handle('choose-keys', async () => {
  const result = await dialog.showOpenDialog(window, {properties: ['openFile'],
    filters: [{name: 'prod.keys', extensions: ['keys']}, {name: 'All files', extensions: ['*']}]});
  if (result.canceled) return null;
  settings.keysPath = result.filePaths[0];
  saveSettings();
  return settings.keysPath;
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
// True while the project's fonts.json is the one the Otomate engine ships (or an
// earlier shipped version): the Virche Evermore set-up, not the user's own.
function exampleFontsConfig(folder) {
  const file = path.join(folder, 'fonts.json');
  if (settings.engine !== 'otomate' || !fs.existsSync(file)) return false;
  const lf = data => sha256(Buffer.from(data.toString('latin1').split('\r\n').join('\n'), 'latin1'));
  const engine = engineById.get('otomate');
  const shipped = path.join(enginePath(engine), 'fonts.json');
  const known = [].concat(engine.hashes['fonts.json'] || []);
  if (fs.existsSync(shipped)) known.push(lf(fs.readFileSync(shipped)));
  return known.includes(lf(fs.readFileSync(file)));
}
ipcMain.handle('missing-files', async (_event, toolId) => {
  const folder = workspace();
  const names = jpNames(toolId, folder);
  let jp = {};
  if (names.length && folder && fs.existsSync(path.join(folder, 'tools', 'jpfiles.py'))) {
    // Asked of the engine itself, so the app finds the same file the tool will read.
    const result = await runHelper(path.join(__dirname, 'find_jp.py'), names, folder);
    try { jp = JSON.parse(result.stdout.trim().split(/\r?\n/).pop() || '{}'); } catch {}
  }
  return missingFiles(toolId, folder, jp, {exampleFonts: exampleFontsConfig(folder)});
});
ipcMain.handle('choose-workspace', async () => {
  const result = await dialog.showOpenDialog(window, {title: t('workspace.dialog', settings.language, {engine: activeEngine().name}),
    defaultPath: workspace(), properties: ['openDirectory', 'createDirectory']});
  if (result.canceled) return null;
  prepareWorkspace(result.filePaths[0], activeEngine());
  settings.workspaces[settings.engine] = result.filePaths[0];
  saveSettings();
  return {workspace: workspace(), python: pythonCheck()};
});
function dialogFilters(filters) {
  if (!Array.isArray(filters)) return [];
  return filters.filter(filter => typeof filter?.name === 'string' && Array.isArray(filter.extensions)
    && filter.extensions.every(extension => typeof extension === 'string' && /^(\*|[a-z0-9]+)$/i.test(extension)))
    .map(filter => ({name: filter.name, extensions: filter.extensions}));
}
ipcMain.handle('choose-path', async (_event, kind, current, filters) => {
  const defaultPath = current || workspace();
  if (kind === 'save') {
    const result = await dialog.showSaveDialog(window, {defaultPath, filters: dialogFilters(filters)});
    return result.canceled ? null : result.filePath;
  }
  // Windows and Linux cannot show one dialog for both files and folders: it becomes a folder picker.
  const properties = kind === 'dir' ? ['openDirectory', 'createDirectory'] : ['openFile'];
  const result = await dialog.showOpenDialog(window, {defaultPath, properties, filters: kind === 'dir' ? [] : dialogFilters(filters)});
  return result.canceled ? null : result.filePaths[0];
});
ipcMain.handle('choose-python', async () => {
  const result = await dialog.showOpenDialog(window, {title: t('python.dialog', settings.language), properties: ['openFile']});
  if (result.canceled) return null;
  settings.python = result.filePaths[0];
  saveSettings();
  return {python: settings.python, check: pythonCheck()};
});
ipcMain.handle('check-python', () => pythonCheck());
ipcMain.handle('open-python-download', () => shell.openExternal('https://www.python.org/downloads/'));
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
// A note lives in the project folder once the engine has been copied there, and
// in the engine folder before that. Only a relative Markdown path is readable.
let docsServer = null;
let docsHtml = '';
function docsPort() {
  if (docsServer) return Promise.resolve(docsServer.address().port);
  return new Promise((resolve, reject) => {
    docsServer = http.createServer((_req, res) => {
      res.writeHead(200, {'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store'});
      res.end(docsHtml);
    });
    docsServer.listen(0, '127.0.0.1', () => resolve(docsServer.address().port));
    docsServer.on('error', reject);
  });
}
ipcMain.handle('open-documentation', async (_event, language) => {
  const lang = language === 'vi' ? 'vi' : 'en';
  const guide = splitGuide(fs.readFileSync(path.join(__dirname, 'guides', lang === 'vi' ? 'app.vi.md' : 'app.en.md'), 'utf8'));
  docsHtml = documentationPage({
    title: t('rail.docs', lang),
    intro: guide.intro,
    pages: guide.pages
  });
  const port = await docsPort();
  await shell.openExternal(`http://127.0.0.1:${port}/`);
  return '';
});
ipcMain.handle('run-tool', (_event, id, values) => {
  if (currentRun) throw new Error('Another command is already running.');
  const entry = toolById.get(id);
  if (!entry || entry.engine.id !== settings.engine) throw new Error('Unknown tool.');
  const {tool} = entry;
  if (!values || typeof values !== 'object') throw new Error('Missing input values.');
  const args = makeArgs(tool, values);
  if (tool.builtin) return runBuiltin(id, tool, values, args);
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
// Tools that run inside the app instead of as a Python script. They use the
// same run log, Stop button and history as the scripts.
const BUILTINS = {
  // The whole game out of an .nsp or .xci, as the project set-up does:
  // <output>/romfs and <output>/exefs, with progress, a free-space check and a
  // stop that removes what it had started.
  async 'extract-game'(values, log, isCancelled) {
    const lang = settings.language;
    const file = String(values.game || '').trim();
    const out = path.resolve(String(values['output folder'] || '').trim());
    const romfsDir = path.join(out, 'romfs'), exefsDir = path.join(out, 'exefs');
    for (const dir of [romfsDir, exefsDir]) {
      if (fs.existsSync(dir) && fs.readdirSync(dir).length) throw new Error(`${t('project.error.not-empty', lang)} (${dir})`);
    }
    const made = [romfsDir, exefsDir, out].filter(dir => !fs.existsSync(dir));
    const gb = bytes => new Intl.NumberFormat(lang === 'vi' ? 'vi-VN' : 'en-US', {minimumFractionDigits: 1, maximumFractionDigits: 1}).format(bytes / 1e9);
    log(t('extract.start', lang, {name: path.basename(file), folder: out}));
    let last = 0;
    try {
      const summary = await extractGame(file, {romfsDir, exefsDir, keys: String(values['--keys'] || '').trim() || settings.keysPath, isCancelled,
        onProgress: p => {
          const now = Date.now();
          if (now - last < 2000 && p.done < p.total) return;
          last = now;
          log(`${p.total ? Math.floor((p.done / p.total) * 100) : 0}% · ${t('project.counts', lang, {files: p.files, count: p.count, done: gb(p.done), total: gb(p.total)})}`);
        }});
      log(t('extract.done', lang, {count: summary.files, total: gb(summary.bytes), romfs: romfsDir, exefs: summary.exefsDir || '-'}));
    } catch (error) {
      // What this run created goes; the output folder only if it made it and nothing else is in it.
      for (const dir of made) {
        if (dir !== out) fs.rmSync(dir, {recursive: true, force: true});
        else if (fs.existsSync(dir) && !fs.readdirSync(dir).length) fs.rmdirSync(dir);
      }
      const known = {keys: 'project.error.keys', space: 'project.error.space', update: 'project.error.update', cancelled: 'project.error.cancelled'};
      if (known[error.code]) throw Object.assign(new Error(t(known[error.code], lang, {detail: error.message})), {code: error.code});
      throw error;
    }
  }
};
function runBuiltin(id, tool, values, args) {
  const run = BUILTINS[tool.builtin];
  if (!run) throw new Error('Unknown tool.');
  settings.values[id] = values;
  saveSettings();
  const runId = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  const started = new Date().toISOString();
  currentRun = {runId, child: null, id, cancelled: false};
  emit('run-start', {runId, id, title: tool.title, started, command: [tool.builtin, ...args]});
  const log = text => emit('run-output', {runId, stream: 'stdout', text: `${text}\n`});
  const finish = (code, error) => {
    if (error) emit('run-output', {runId, stream: 'stderr', text: `${error.message}\n`});
    const signal = currentRun?.cancelled ? 'cancelled' : null;
    currentRun = null;
    settings.history.unshift({id, engine: settings.engine, title: tool.title, started, code, signal});
    settings.history = settings.history.slice(0, 30);
    saveSettings();
    emit('run-end', {runId, code, signal});
  };
  run(values, log, () => !!currentRun?.cancelled)
    .then(() => finish(0), error => finish(error.code === 'cancelled' ? 130 : 1, error));
  return {runId};
}
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
  if (Object.prototype.hasOwnProperty.call(fields, 'sheetPath')) {
    const next = String(fields.sheetPath || '');
    // Worksheets picked from the old workbook may not exist in the new one.
    if (next !== current.sheetPath) current.options = cleanPatchOptions(settings.engine, {...current.options, sheets: '', sheetName: ''});
    current.sheetPath = next;
  }
  if (Object.prototype.hasOwnProperty.call(fields, 'outputPath')) current.outputPath = String(fields.outputPath || '');
  if (Object.prototype.hasOwnProperty.call(fields, 'group')) current.group = fields.group || null;
  if (Object.prototype.hasOwnProperty.call(fields, 'options')) current.options = cleanPatchOptions(settings.engine, fields.options);
  saveSettings();
  return {settings};
});
ipcMain.handle('open-output', () => shell.openPath(settings.patch[settings.engine].outputPath));
// Worksheet names of the chosen translation sheet, for picking them on the patch page.
ipcMain.handle('sheet-names', async () => {
  const sheet = settings.patch[settings.engine].sheetPath;
  if (!isXlsx(path.basename(sheet || '')) || !fs.existsSync(sheet)) return [];
  const result = await runHelper(path.join(__dirname, 'sheet_names.py'), [sheet], path.dirname(sheet));
  try { return JSON.parse(result.stdout); }
  catch { throw new Error(result.stderr.trim().split('\n').pop() || 'sheet_names.py failed'); }
});

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
// Removes the app's own run folders (named by timestamp) and then `runs` if that
// leaves it empty. Anything else someone keeps in a folder called runs is left alone.
function clearRuns(folder) {
  if (!fs.existsSync(folder)) return;
  for (const name of fs.readdirSync(folder)) {
    if (/^\d+$/.test(name)) fs.rmSync(path.join(folder, name), {recursive: true, force: true});
  }
  if (!fs.readdirSync(folder).length) fs.rmdirSync(folder);
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
  const runsFolder = path.join(outputPath, 'runs');
  // Each run copies the whole sheet here. Earlier runs go when a new one starts,
  // and a run that succeeds removes its own: only a failed run stays to look at.
  clearRuns(runsFolder);
  const runDirectory = path.join(runsFolder, `${Date.now()}`);
  const copyPath = path.join(runDirectory, 'sheet.xlsx');
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
  const patchOptions = cleanPatchOptions(engineId, patch.options);
  const list = value => value.split(/[\n,]/).map(item => item.trim()).filter(Boolean);
  // A dry run checks everything and writes nothing; the result says which it was.
  // Lines too wide for their box: held back unless allowed, and always listed.
  const overflowPath = path.join(outputPath, 'overflow.csv');
  const extraResult = {dryRun: patchOptions.dryRun, allowOverflow: patchOptions.allowOverflow, overflow: [],
    unmeasured: engineId === 'otomate' && !fs.existsSync(path.join(projectPath, 'windows.json')),
    widths: engineId === 'otomate' ? Object.fromEntries(Object.entries(readWindows(projectPath)).map(([screen, entry]) => [screen, entry.ceiling])) : {}};
  const findings = [];
  const untranslated = [];
  let blocked = false;
  let failedStep = null;
  const finish = (code, extra) => {
    const cancelled = currentRun?.cancelled;
    currentRun = null;
    if (code === 0 && !cancelled) clearRuns(runsFolder);
    emit('run-end', {runId, id: 'patch', code: cancelled ? 130 : code, signal: cancelled ? 'cancelled' : null, ...extra});
    return {started: true, runDirectory, copied, skip: false, ...extra, code: cancelled ? 130 : code};
  };
  const noteFailure = step => {blocked = true; failedStep = failedStep || step.id;};
  // sheet_scan.py exits 2 when it lists rows with no translation. Those rows stay
  // in English, so they are reported with the result instead of stopping the patch.
  const scanSheet = async step => {
    const scan = await spawnPython(path.join(__dirname, 'sheet_scan.py'), [copyPath], projectPath);
    untranslated.push(...patchFindings(scan.stdout));
    if (scan.code !== 0 && scan.code !== 2) noteFailure(step);
    return scan;
  };
  try {
  for (const step of recipe) {
    if (currentRun.cancelled) return finish(130, {stopped: true, findings, untranslated, failedStep});
    if (step.phase === 'create' && blocked) return finish(2, {findings, untranslated, skip: false, failedStep});
    emit('run-output', {runId, stream: 'stdout', text: `\n${step.phase}: ${step.id}\n`});
    let result = {code: 0, stdout: ''};
    if (step.id === 'empty-scan') {
      result = await scanSheet(step);
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
    } else if (step.id === 'filltitles-fill') {
      // Only titles spelled `<japanese key>@<text>` are composed. A game whose titles
      // carry no key (the fan disc) has nothing here, so the step is skipped quietly.
      const keys = await runHelper(path.join(__dirname, 'title_keys.py'), [copyPath], runDirectory);
      let keyed = 1;
      try { keyed = JSON.parse(keys.stdout).keyed; } catch {}
      if (keyed === 0) {
        emit('run-output', {runId, stream: 'stdout', text: 'khong co ten chuong mang khoa <tieng Nhat>@ - bo qua ghep ten chuong\n'});
        continue;
      }
      // Composing chapter titles needs the translated prefixes from Export chapter
      // labels: filltitles reads them from a `title_prefix` worksheet, which can be
      // in the translation sheet itself or in work/title_prefixes.xlsx. A project
      // with neither still patches, its titles as they are.
      const names = await runHelper(path.join(__dirname, 'sheet_names.py'), [copyPath], runDirectory);
      let inSheet = false;
      try { inSheet = JSON.parse(names.stdout).includes('title_prefix'); } catch {}
      const projectFile = path.join(projectPath, 'work', 'title_prefixes.xlsx');
      const prefixes = inSheet ? copyPath : fs.existsSync(projectFile) ? projectFile : null;
      if (!prefixes) {
        extraResult.titlesSkipped = true;
        emit('run-output', {runId, stream: 'stdout', text: 'bo qua ghep ten chuong: khong co sheet title_prefix trong bang dich, cung khong co work/title_prefixes.xlsx\n'});
      } else {
        emit('run-output', {runId, stream: 'stdout', text: `tien to chuong lay tu: ${inSheet ? 'sheet title_prefix trong bang dich' : projectFile}\n`});
        result = await spawnPython(path.join(projectPath, 'tools', 'filltitles.py'),
          ['fill', copyPath, copyPath, '--prefixes', prefixes], projectPath);
        if (result.code !== 0) noteFailure(step);
      }
    } else if (step.id === 'applyvi') {
      // applyvi writes the report only when a line overflows, so an old one must not linger.
      fs.rmSync(overflowPath, {force: true});
      result = await spawnPython(path.join(projectPath, 'tools', 'applyvi.py'),
        [copyPath, path.join(projectPath, 'STORY.cpk'), outputPath,
          ...(patchOptions.dryRun ? ['--dry-run'] : []),
          ...list(patchOptions.sheets).flatMap(sheet => ['--sheet', sheet]),
          ...(patchOptions.allowOverflow ? [] : ['--fit-width']),
          '--report', overflowPath], projectPath);
      extraResult.overflow = readOverflow(overflowPath);
      if (result.code !== 0) return finish(result.code, {findings, untranslated, skip: false, failedStep: step.id});
    } else if (step.id === 'unity-sheet-apply') {
      const bundle = fs.readdirSync(projectPath).find(name => /\.(bundle|assets)$/i.test(name));
      if (!bundle) return finish(1, {findings, untranslated, skip: false, failedStep: step.id});
      result = await spawnPython(path.join(projectPath, 'tools', 'jsonsheet.py'),
        ['apply', path.join(projectPath, bundle), copyPath, '--out', path.join(outputPath, 'patched.bundle'),
          ...(patchOptions.dryRun ? [] : ['--apply']),
          ...(patchOptions.sheetName.trim() ? ['--sheet-name', patchOptions.sheetName.trim()] : []),
          ...(patchOptions.force ? ['--force'] : []),
          ...(patchOptions.packer !== 'auto' ? ['--packer', patchOptions.packer] : []),
          // Tokens are regular expressions, which may hold commas: one per line only.
          ...patchOptions.tokens.split(/\r?\n/).map(token => token.trim()).filter(Boolean)
            .flatMap(token => ['--token', token])], projectPath);
      if (result.code !== 0) return finish(result.code, {findings, untranslated, skip: false, failedStep: step.id});
    }
    if (step.phase === 'prepare' && blocked) return finish(result.code || 1, {findings, untranslated, skip: false, failedStep});
  }
  return finish(0, {findings, untranslated, ...extraResult, complete: !blocked, skip: false, failedStep});
  } catch (error) {
    emit('run-output', {runId, stream: 'stderr', text: `${error.message}\n`});
    return finish(1, {findings, untranslated, skip: false, failedStep});
  }
});

// overflow.csv from applyvi --report: sheet, id, vi_bytes, en_bytes, vi_px, over_px, vietnamese.
function parseCsv(text) {
  const rows = [];
  let row = [], cell = '', quoted = false;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (quoted) {
      if (ch === '"' && text[i + 1] === '"') {cell += '"'; i++;}
      else if (ch === '"') quoted = false;
      else cell += ch;
    } else if (ch === '"') quoted = true;
    else if (ch === ',') {row.push(cell); cell = '';}
    else if (ch === '\n' || ch === '\r') {
      if (ch === '\r' && text[i + 1] === '\n') i++;
      row.push(cell); rows.push(row); row = []; cell = '';
    } else cell += ch;
  }
  if (cell || row.length) {row.push(cell); rows.push(row);}
  return rows;
}
function readOverflow(file) {
  if (!fs.existsSync(file)) return [];
  const [header, ...rows] = parseCsv(fs.readFileSync(file, 'utf8').replace(/^\ufeff/, ''));
  const at = name => (header || []).indexOf(name);
  return rows.filter(row => row.length > 1).map(row => ({sheet: row[at('sheet')], id: row[at('id')],
    over: Number(row[at('over_px')]) || 0, text: row[at('vietnamese')] || ''}));
}
ipcMain.handle('open-overflow', () => {
  const file = path.join(settings.patch[settings.engine].outputPath || '', 'overflow.csv');
  return fs.existsSync(file) ? shell.openPath(file) : 'overflow.csv was not found.';
});
// A short Python helper outside the run log: no output events, no Stop button.
function runHelper(script, args, cwd) {
  return new Promise(resolve => {
    const child = spawn(settings.python, ['-u', script, ...args],
      {cwd, env: {...process.env, PYTHONIOENCODING: 'utf-8'}, windowsHide: true, shell: false});
    let stdout = '';
    let stderr = '';
    child.stdout.on('data', data => {stdout += data.toString('utf8');});
    child.stderr.on('data', data => {stderr += data.toString('utf8');});
    child.on('error', error => resolve({code: 1, stdout, stderr: error.message}));
    child.on('close', code => resolve({code: code ?? 1, stdout, stderr}));
  });
}
// The measure screen: a screenshot to click on, and one line's width in font units.
const IMAGE_TYPES = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.webp': 'image/webp', '.bmp': 'image/bmp'};
ipcMain.handle('choose-image', async () => {
  const result = await dialog.showOpenDialog(window, {properties: ['openFile'],
    filters: [{name: 'Images', extensions: Object.keys(IMAGE_TYPES).map(ext => ext.slice(1))}]});
  if (result.canceled) return null;
  const file = result.filePaths[0];
  const type = IMAGE_TYPES[path.extname(file).toLowerCase()];
  if (!type) throw new Error('Choose a PNG, JPG, WEBP or BMP image.');
  // The page only loads data: images, so the file is handed over inline.
  return {path: file, dataUrl: `data:${type};base64,${fs.readFileSync(file).toString('base64')}`};
});
ipcMain.handle('measure-line', async (_event, text) => {
  const result = await runHelper(path.join(__dirname, 'measure_line.py'), [String(text || '')], workspace());
  const line = result.stdout.trim().split(/\r?\n/).pop() || '';
  let parsed = null;
  try { parsed = JSON.parse(line); } catch {}
  if (result.code !== 0 || !parsed || parsed.error) {
    throw new Error(parsed?.error === 'font' ? `No font file at ${parsed.path}` : (result.stderr.trim().split(/\r?\n/).pop() || 'measure_line.py failed'));
  }
  return parsed;
});
ipcMain.handle('measure-saved', () => readWindows(workspace()));
ipcMain.handle('measure-save', (_event, screen, entry) => {
  const folder = workspace();
  // The font is recorded relative to the project folder when it lives there.
  const relative = entry?.fontFile && folder ? path.relative(folder, entry.fontFile) : '';
  const fontFile = relative && !relative.startsWith('..') && !path.isAbsolute(relative) ? relative.split(path.sep).join('/') : entry?.fontFile;
  return saveWindow(folder, screen, {...entry, fontFile});
});
// The replace-fonts page: stock .ffu files, a TTF/OTF for each, and ffugen run on every pair.
function helperJson(result, fallback) {
  const line = result.stdout.trim().split(/\r?\n/).pop() || '';
  try { return JSON.parse(line); } catch {}
  throw new Error(result.stderr.trim().split(/\r?\n/).pop() || fallback);
}
async function ffuInfo(files) {
  return helperJson(await runHelper(path.join(__dirname, 'font_info.py'), ['ffu', ...files], workspace()), 'font_info.py failed');
}
ipcMain.handle('choose-ffu', async (_event, current) => {
  const result = await dialog.showOpenDialog(window, {defaultPath: current || workspace(),
    properties: ['openFile', 'multiSelections'], filters: [{name: 'Game fonts (.ffu)', extensions: ['ffu']}]});
  return result.canceled ? [] : result.filePaths;
});
ipcMain.handle('ffu-info', (_event, files) => ffuInfo((Array.isArray(files) ? files : []).map(String)));
ipcMain.handle('font-info', async (_event, file) =>
  helperJson(await runHelper(path.join(__dirname, 'font_info.py'), ['font', String(file)], workspace()), 'font_info.py failed'));
ipcMain.handle('run-fonts', async (_event, jobs, output, options) => {
  if (currentRun) throw new Error('Another command is already running.');
  output = String(output || '').trim();
  if (output && !path.isAbsolute(output)) return {problem: 'output'};
  const root = path.resolve(workspace());
  const script = path.join(root, 'tools', 'ffugen.py');
  if (!fs.existsSync(script)) throw new Error('tools/ffugen.py is missing from the project folder.');
  // The advanced settings, parsed like the tool form would; each replaces the automatic one.
  const ffugen = toolById.get('ffugen').tool;
  const given = makeArgs({prefix: [], args: ffugen.args.filter(arg => !MAPPED_ARGS.includes(arg.name))},
    options && typeof options === 'object' ? options : {});
  const chosen = (Array.isArray(jobs) ? jobs : []).map(job => ({path: String(job.template || ''),
    fonts: (Array.isArray(job.fonts) ? job.fonts : []).map(String).filter(Boolean).map(file => ({path: file}))}));
  // Read the files again here rather than trust the page: the flags come from them.
  const infos = await ffuInfo(chosen.map(job => job.path));
  const templates = chosen.map((job, index) => ({...job, info: infos[index]}));
  const problem = fontJobProblem(templates, output);
  if (problem) return {problem};
  settings.values.ffugen = {...options};
  saveSettings();
  const runId = `fonts-${Date.now()}`;
  currentRun = {runId, child: null, cancelled: false, id: 'fonts'};
  const todo = templates.filter(job => job.fonts.length);
  emit('run-start', {runId, id: 'fonts', title: 'Make game font', started: new Date().toISOString(), command: ['ffugen', `${todo.length} fonts`, ...given]});
  const made = [];
  let failed = null;
  try {
    fs.mkdirSync(output, {recursive: true});
    for (const item of todo) {
      const name = path.basename(item.path);
      emit('run-output', {runId, stream: 'stdout', text: `\n== ${name} <- ${item.fonts.map(font => path.basename(font.path)).join(' + ')}\n`});
      // ffugen sizes the chain by its first font, so that is the one fitted to the cell.
      let px = argValue(given, '--px');
      if (!px) {
        const cell = argValue(given, '--cell') || item.info.cell;
        const stroke = argValue(given, '--stroke') ?? strokeFor(item.info);
        px = helperJson(await runHelper(path.join(__dirname, 'font_info.py'),
          ['fit', String(cell), String(stroke), item.fonts[0].path], root), 'font_info.py fit failed').px;
      }
      if (currentRun.cancelled) break;
      const result = await spawnPython(script, ['--template', item.path, '--out', path.join(output, name),
        ...item.fonts.flatMap(font => ['--font', font.path]), ...withOverrides(ffugenArgs(item.info, px), given)], root);
      if (currentRun.cancelled) break;
      if (result.code !== 0) {failed = name; break;}
      made.push(name);
    }
  } catch (error) {
    emit('run-output', {runId, stream: 'stderr', text: `${error.message}\n`});
    failed = failed || 'output';
  }
  const cancelled = currentRun.cancelled;
  currentRun = null;
  const code = cancelled ? 130 : failed ? 1 : 0;
  // What Repack CPK needs next: the game's SYSTEM.cpk when the project has one.
  const archive = path.join(root, 'SYSTEM.cpk');
  const repack = {archive: fs.existsSync(archive) ? archive : '', output: path.join(path.dirname(output), 'SYSTEM_vn.cpk'), folder: output};
  emit('run-end', {runId, id: 'fonts', code, signal: cancelled ? 'cancelled' : null, made, failed, output, repack});
  return {started: true, code};
});
// Saves the rows the last patch left untranslated, for handing to translators.
ipcMain.handle('export-untranslated', async (_event, rows) => {
  if (!Array.isArray(rows) || !rows.length) return null;
  const defaultPath = path.join(settings.patch[settings.engine].outputPath || workspace(), 'untranslated.csv');
  const result = await dialog.showSaveDialog(window, {defaultPath, filters: [{name: 'CSV', extensions: ['csv']}]});
  if (result.canceled) return null;
  const cell = value => `"${String(value ?? '').replace(/"/g, '""')}"`;
  const lines = [['Sheet', 'Row', 'Source'], ...rows.map(row => [row.sheet, row.row, row.source])].map(row => row.map(cell).join(','));
  // The byte order mark lets Excel read the file as UTF-8.
  fs.writeFileSync(result.filePath, `\ufeff${lines.join('\r\n')}\r\n`, 'utf8');
  return result.filePath;
});

module.exports = {makeArgs};
