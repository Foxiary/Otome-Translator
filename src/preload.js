const {contextBridge, ipcRenderer} = require('electron');
const {t} = require('./i18n');
const {browse, selectTool} = require('./tool-browser');
const {isXlsx, successActions, canSwitchEngine, canOpenTools, languageChange} = require('./patch-ui');

contextBridge.exposeInMainWorld('vees', {
  state: () => ipcRenderer.invoke('state'),
  setEngine: id => ipcRenderer.invoke('set-engine', id),
  chooseWorkspace: () => ipcRenderer.invoke('choose-workspace'),
  choosePath: (kind, current) => ipcRenderer.invoke('choose-path', kind, current),
  choosePython: () => ipcRenderer.invoke('choose-python'),
  setupPython: () => ipcRenderer.invoke('setup-python'),
  openWorkspace: () => ipcRenderer.invoke('open-workspace'),
  openDocument: name => ipcRenderer.invoke('open-document', name),
  run: (id, values) => ipcRenderer.invoke('run-tool', id, values),
  runPatch: options => ipcRenderer.invoke('run-patch', options),
  setLanguage: language => ipcRenderer.invoke('set-language', language),
  setPatch: fields => ipcRenderer.invoke('set-patch', fields),
  openOutput: () => ipcRenderer.invoke('open-output'),
  cancel: () => ipcRenderer.invoke('cancel-run'),
  t: (key, language) => t(key, language),
  browse: (tools, options) => browse(tools, options),
  selectTool: tool => selectTool(tool),
  isXlsx,
  successActions,
  canSwitchEngine,
  canOpenTools,
  languageChange,
  checkUpdates: () => ipcRenderer.invoke('check-update'),
  dismissUpdate: tag => ipcRenderer.invoke('dismiss-update', tag),
  openUpdate: () => ipcRenderer.invoke('open-update'),
  on: (event, callback) => {
    if (!['run-start', 'run-output', 'run-end', 'update-status'].includes(event)) throw new Error('Invalid event');
    const handler = (_event, payload) => callback(payload);
    ipcRenderer.on(event, handler);
    return () => ipcRenderer.removeListener(event, handler);
  }
});
