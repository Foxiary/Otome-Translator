const {contextBridge, ipcRenderer} = require('electron');

contextBridge.exposeInMainWorld('vees', {
  state: () => ipcRenderer.invoke('state'),
  setEngine: id => ipcRenderer.invoke('set-engine', id),
  chooseWorkspace: () => ipcRenderer.invoke('choose-workspace'),
  choosePath: (kind, current, filters) => ipcRenderer.invoke('choose-path', kind, current, filters),
  choosePython: () => ipcRenderer.invoke('choose-python'),
  setupPython: () => ipcRenderer.invoke('setup-python'),
  openWorkspace: () => ipcRenderer.invoke('open-workspace'),
  missingFiles: toolId => ipcRenderer.invoke('missing-files', toolId),
  openDocument: name => ipcRenderer.invoke('open-document', name),
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
    if (!['run-start', 'run-output', 'run-end', 'update-status'].includes(event)) throw new Error('Invalid event');
    const handler = (_event, payload) => callback(payload);
    ipcRenderer.on(event, handler);
    return () => ipcRenderer.removeListener(event, handler);
  }
});
