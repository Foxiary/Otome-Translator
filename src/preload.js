const {contextBridge, ipcRenderer, webUtils} = require('electron');

contextBridge.exposeInMainWorld('vees', {
  state: () => ipcRenderer.invoke('state'),
  detectEngine: input => ipcRenderer.invoke('detect-engine', input),
  chooseDetectInput: kind => ipcRenderer.invoke('choose-detect-input', kind),
  chooseKeys: () => ipcRenderer.invoke('choose-keys'),
  markEngineChosen: () => ipcRenderer.invoke('engine-chosen'),
  projectSuggest: (name, parent) => ipcRenderer.invoke('project-suggest', name, parent),
  projectCreate: options => ipcRenderer.invoke('project-create', options),
  projectCancel: () => ipcRenderer.invoke('project-cancel'),
  // A dropped File carries no path in the page since Electron 32; this asks for it.
  pathForFile: file => webUtils.getPathForFile(file),
  setEngine: id => ipcRenderer.invoke('set-engine', id),
  chooseWorkspace: () => ipcRenderer.invoke('choose-workspace'),
  choosePath: (kind, current, filters, startIn) => ipcRenderer.invoke('choose-path', kind, current, filters, startIn),
  fileExists: file => ipcRenderer.invoke('file-exists', file),
  pathKind: target => ipcRenderer.invoke('path-kind', target),
  revealPath: target => ipcRenderer.invoke('reveal-path', target),
  choosePython: () => ipcRenderer.invoke('choose-python'),
  setupPython: () => ipcRenderer.invoke('setup-python'),
  checkPython: () => ipcRenderer.invoke('check-python'),
  openPythonDownload: () => ipcRenderer.invoke('open-python-download'),
  openWorkspace: () => ipcRenderer.invoke('open-workspace'),
  missingFiles: toolId => ipcRenderer.invoke('missing-files', toolId),
  openDocumentation: language => ipcRenderer.invoke('open-documentation', language),
  run: (id, values) => ipcRenderer.invoke('run-tool', id, values),
  runPatch: options => ipcRenderer.invoke('run-patch', options),
  setLanguage: language => ipcRenderer.invoke('set-language', language),
  setPatch: fields => ipcRenderer.invoke('set-patch', fields),
  openOutput: () => ipcRenderer.invoke('open-output'),
  openOverflow: () => ipcRenderer.invoke('open-overflow'),
  sheetNames: () => ipcRenderer.invoke('sheet-names'),
  exportUntranslated: rows => ipcRenderer.invoke('export-untranslated', rows),
  chooseImage: () => ipcRenderer.invoke('choose-image'),
  measureLine: text => ipcRenderer.invoke('measure-line', text),
  measureSaved: () => ipcRenderer.invoke('measure-saved'),
  measureSave: (screen, entry) => ipcRenderer.invoke('measure-save', screen, entry),
  chooseFfu: current => ipcRenderer.invoke('choose-ffu', current),
  ffuInfo: files => ipcRenderer.invoke('ffu-info', files),
  fontInfo: file => ipcRenderer.invoke('font-info', file),
  runFonts: (jobs, output, options) => ipcRenderer.invoke('run-fonts', jobs, output, options),
  cancel: () => ipcRenderer.invoke('cancel-run'),
  checkUpdates: () => ipcRenderer.invoke('check-update'),
  dismissUpdate: tag => ipcRenderer.invoke('dismiss-update', tag),
  openUpdate: () => ipcRenderer.invoke('open-update'),
  on: (event, callback) => {
    if (!['run-start', 'run-output', 'run-end', 'update-status', 'project-progress'].includes(event)) throw new Error('Invalid event');
    const handler = (_event, payload) => callback(payload);
    ipcRenderer.on(event, handler);
    return () => ipcRenderer.removeListener(event, handler);
  }
});
