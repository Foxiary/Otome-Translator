// Step two of the start page: where the project lives. Start from scratch (the
// app takes the whole game out of the .nsp/.xci, or copies what Ryujinx took
// out), carry on an existing mod (copied into the project's mod/), or open a
// project made before. The work happens in the main process ('project-create');
// detect-ui.js shows this step once an engine is chosen and gets the result
// back through window.otmStart.finish().
(() => {
  const box = document.getElementById('start-project');
  const gameStep = document.getElementById('start-game');
  const s = {mode: 'scratch', gameFile: null, gameFolder: null, modFolder: null, folder: null,
    busy: false, progress: null, error: null};

  const baseName = input => (input || '').split(/[\\/]/).filter(Boolean).pop() || input;
  const gb = bytes => new Intl.NumberFormat(language() === 'vi' ? 'vi-VN' : 'en-US', {minimumFractionDigits: 1, maximumFractionDigits: 1}).format(bytes / 1e9);
  function button(label, onClick, className = 'button') {
    const node = elt('button', className, label);
    node.type = 'button';
    node.disabled = s.busy;
    node.addEventListener('click', onClick);
    return node;
  }
  // One labelled value with its picker: the chosen path, or "nothing chosen".
  function field(label, value, ...actions) {
    const row = elt('div', 'project-field');
    const copy = elt('div', 'project-field-copy');
    copy.append(elt('div', 'project-field-label', label));
    const shown = elt('div', `project-field-value${value ? ' mono' : ' is-empty'}`, value || text('project.none'));
    if (value) shown.title = value;
    copy.append(shown);
    const buttons = elt('div', 'project-field-actions');
    buttons.append(...actions);
    row.append(copy, buttons);
    return row;
  }
  async function pickGame() {
    const file = await window.vees.choosePath('file', s.gameFile || '', [{name: 'Switch game', extensions: ['nsp', 'xci']}, {name: 'All files', extensions: ['*']}]);
    if (file) { s.gameFile = file; s.gameFolder = null; s.error = null; render(); }
  }
  async function pickGameFolder() {
    const folder = await window.vees.choosePath('dir', s.gameFolder || '');
    if (folder) { s.gameFolder = folder; s.gameFile = null; s.error = null; render(); }
  }
  async function pickMod() {
    const folder = await window.vees.choosePath('dir', s.modFolder || '');
    if (folder) { s.modFolder = folder; s.error = null; render(); }
  }
  async function pickWhere() {
    const parent = await window.vees.choosePath('dir', s.folder || '');
    if (!parent) return;
    // A chosen empty folder is the project; otherwise the project goes inside it.
    s.folder = await window.vees.projectSuggest(baseName(s.folder), parent);
    render();
  }

  function errorText(message) {
    const match = /(keys|space|not-empty|update|cancelled)(?::\s*(.*))?$/.exec(message || '');
    if (!match) return text('project.error.other', {message: (message || '').replace(/^Error invoking remote method '[^']+': (Error: )?/, '')});
    return text(`project.error.${match[1]}`, {detail: match[2] || ''});
  }

  async function create() {
    if (s.mode === 'mod' && !s.modFolder) { s.error = text('project.needMod'); return render(); }
    if (s.mode === 'scratch' && !s.gameFile && !s.gameFolder) { s.error = text('project.needGame'); return render(); }
    s.busy = true; s.error = null; s.progress = null;
    render();
    try {
      const result = await window.vees.projectCreate({folder: s.folder, gameFile: s.gameFile, gameFolder: s.gameFolder,
        modFolder: s.mode === 'mod' ? s.modFolder : null});
      state.workspace = result.workspace;
      updatePython(result.python);
      s.busy = false;
      hide();
      window.otmStart.finish(result.files || {});
    } catch (error) {
      s.busy = false;
      s.error = {message: error.message, keys: /keys/.test(error.message)};
      render();
    }
  }
  async function openExisting() {
    const result = await window.vees.chooseWorkspace();
    if (!result) return;
    state.workspace = result.workspace;
    updatePython(result.python);
    hide();
    window.otmStart.finish({});
  }

  function renderProgress() {
    const panel = box.querySelector('.project-progress');
    if (!panel || !s.progress) return;
    const p = s.progress;
    panel.replaceChildren();
    panel.append(elt('div', 'project-progress-stage', text(`project.stage.${p.stage}`, {engine: engine().name})));
    if (p.stage === 'extract' && p.total) {
      const bar = elt('div', 'project-bar');
      const fill = elt('div', 'project-bar-fill');
      fill.style.width = `${Math.min(100, (p.done / p.total) * 100).toFixed(1)}%`;
      bar.append(fill);
      panel.append(bar, elt('div', 'project-progress-counts', text('project.counts', {files: p.files, count: p.count, done: gb(p.done), total: gb(p.total)})));
      if (p.current) panel.append(elt('div', 'project-progress-file mono', p.current));
    }
  }

  function render() {
    box.replaceChildren();
    if (!s.busy) box.append(button(`← ${text('project.back')}`, () => { hide(); window.otmStart.back(); }, 'project-back'));
    box.append(elt('h1', '', text('project.title')), elt('p', 'start-lead', text('project.lead', {engine: engine().name})));

    const modes = elt('div', 'project-modes');
    modes.setAttribute('role', 'radiogroup');
    for (const mode of ['scratch', 'mod', 'open']) {
      const choice = elt('label', `project-mode${s.mode === mode ? ' is-selected' : ''}`);
      const radio = elt('input', '');
      radio.type = 'radio'; radio.name = 'project-mode'; radio.value = mode;
      radio.checked = s.mode === mode; radio.disabled = s.busy;
      radio.addEventListener('change', () => { s.mode = mode; s.error = null; render(); });
      const copy = elt('span', 'project-mode-copy');
      copy.append(elt('span', 'project-mode-title', text(`project.mode.${mode}`)), elt('span', 'project-mode-hint', text(`project.mode.${mode}Hint`)));
      choice.append(radio, copy);
      modes.append(choice);
    }
    box.append(modes);

    const form = elt('div', 'project-form');
    if (s.mode === 'open') {
      form.append(button(text('project.openButton'), openExisting, 'button primary'));
    } else {
      if (s.mode === 'mod') form.append(field(text('project.mod'), s.modFolder, button(text('project.pickFolder'), pickMod)));
      if (s.gameFolder) {
        form.append(field(text('project.gameFolder'), s.gameFolder, button(text('project.pickFile'), pickGame), button(text('project.change'), pickGameFolder)));
      } else {
        form.append(field(text(s.mode === 'mod' ? 'project.gameOptional' : 'project.game'), s.gameFile, button(text('project.pickFile'), pickGame)));
      }
      const guide = elt('details', 'project-ryujinx');
      guide.append(elt('summary', '', text('project.ryujinx')));
      const steps = elt('ol', '');
      for (const n of [1, 2, 3]) steps.append(elt('li', '', text(`project.ryujinx.${n}`)));
      guide.append(steps, button(text('project.ryujinx.pick'), pickGameFolder));
      if (s.gameFolder) guide.open = true;
      form.append(guide);
      form.append(field(text('project.where'), s.folder, button(text('project.change'), pickWhere)));
    }
    box.append(form);

    if (s.error) {
      const problem = elt('div', 'detect-problem project-error', typeof s.error === 'string' ? s.error : errorText(s.error.message));
      if (s.error.keys) problem.append(button(text('detect.chooseKeys'), async () => { if (await window.vees.chooseKeys()) create(); }, 'button'));
      box.append(problem);
    }
    if (s.busy) {
      const progress = elt('div', 'project-progress');
      box.append(progress);
      renderProgress();
    }
    const actions = elt('div', 'project-actions');
    if (s.busy) {
      const stop = elt('button', 'button', text('project.stop'));
      stop.type = 'button';
      stop.addEventListener('click', () => window.vees.projectCancel());
      actions.append(stop);
    } else {
      if (s.mode !== 'open') actions.append(button(text('project.create'), create, 'button primary'));
      actions.append(button(text('project.later'), () => { hide(); window.otmStart.finish({}); }, 'button quiet'));
    }
    box.append(actions);
  }

  function hide() {
    box.classList.add('hidden');
    gameStep.classList.remove('hidden');
  }
  async function show(context = {}) {
    s.mode = context.modFolder ? 'mod' : 'scratch';
    s.gameFile = context.gameFile || null;
    s.gameFolder = null;
    s.modFolder = context.modFolder || null;
    s.error = null; s.progress = null; s.busy = false;
    s.folder = await window.vees.projectSuggest(context.gameName || baseName(context.gameFile || context.modFolder) || engine().name);
    gameStep.classList.add('hidden');
    box.classList.remove('hidden');
    render();
    box.querySelector('h1')?.focus?.();
  }

  window.vees.on('project-progress', progress => { s.progress = progress; renderProgress(); });
  document.addEventListener('languagechange', () => { if (!box.classList.contains('hidden')) render(); });
  // state and render are exposed for checks that cannot drive the native folder dialog.
  window.otmProject = {show, hide, state: s, render};
})();
