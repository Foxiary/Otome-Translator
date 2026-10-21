const $ = id => document.getElementById(id);
let state;
let activeGroup = null;
let activeId = null;
let running = false;
let page = 'form';
let patchStage = 'choose';
let patchPhase = 0;
let patchMissing = [];
let formValues = {};
let currentLog = '';
let pythonCheck = null;
let runStatus = {key: 'status.idle', css: ''};

const acronyms = {jp: 'JP', vn: 'VN', cpk: 'CPK', id: 'ID', px: 'PX', aoc: 'AOC', exefs: 'ExeFS', romfs: 'RomFS'};
function titleOf(name) {
  const words = name.replace(/^--/, '').replace(/[-_]/g, ' ').replace(/\b[a-z]+\b/g, word => acronyms[word] || word);
  return words.charAt(0).toUpperCase() + words.slice(1);
}
const SVG = 'http://www.w3.org/2000/svg';
function icon(name, className = 'icon') {
  const svg = document.createElementNS(SVG, 'svg');
  svg.setAttribute('class', className);
  const use = document.createElementNS(SVG, 'use');
  use.setAttribute('href', `#i-${name}`);
  svg.append(use);
  return svg;
}
const groupIcons = {Build: 'build', Fonts: 'font', Archives: 'archive', Sheets: 'sheet', Apply: 'arrow', Executable: 'terminal',
  Diagnostics: 'diagnostics', Dump: 'download', Inspect: 'search', Text: 'sheet', Layout: 'layout', Release: 'package'};
// The patch page sits in the group list next to the group whose output it shares.
const patchAfter = {otomate: 'Build', unity: 'Text'};
function elt(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}
function engine() { return state.engines.find(item => item.id === state.settings.engine); }
function tools() { return engine().tools; }
function tool() { return tools().find(item => item.id === activeId); }
// Land on the first tool of the engine unless the current selection belongs to it.
function selectDefault() {
  if (page !== 'form') return;
  if (tool()) return;
  activeGroup = engine().groups.find(group => tools().some(t => t.group === group));
  activeId = tools().find(t => t.group === activeGroup)?.id;
}
function language() { return state.settings.language === 'vi' ? 'vi' : 'en'; }
function text(key, values) { return t(key, language(), values); }
// Catalog text in the interface language, falling back to the English catalog.
function toolText(item, field) { return (language() === 'vi' && item.vi?.[field]) || item[field]; }
function groupText(group) { return language() === 'vi' ? engine().vi?.groups[group] : null; }
function groupName(group) { return groupText(group)?.name || group; }
function groupSummary(group) { return groupText(group)?.summary || engine().summaries[group]; }
function applyLanguage() {
  if (document.documentElement.lang !== language()) {
    document.documentElement.lang = language();
    document.dispatchEvent(new Event('languagechange'));
  }
  for (const node of document.querySelectorAll('[data-i18n]')) node.textContent = text(node.dataset.i18n);
  for (const node of document.querySelectorAll('[data-i18n-placeholder]')) node.placeholder = text(node.dataset.i18nPlaceholder);
  for (const node of document.querySelectorAll('[data-i18n-title]')) node.title = text(node.dataset.i18nTitle);
  $('language-code').textContent = language().toUpperCase();
  for (const code of ['en', 'vi']) $(`lang-${code}`).setAttribute('aria-checked', String(language() === code));
  renderTheme();
  if (pythonCheck) updatePython(pythonCheck);
  status(runStatus.key, runStatus.css);
  if (!currentLog) $('log').textContent = text('log.empty');
}
function patchState() { return state.settings.patch[state.settings.engine]; }
function theme() { return document.documentElement.dataset.theme === 'light' ? 'light' : 'dark'; }
function renderTheme() {
  $('theme-toggle').setAttribute('aria-checked', String(theme() === 'dark'));
  $('theme-state').textContent = text(theme() === 'dark' ? 'theme.on' : 'theme.off');
}
function toggleTheme() {
  const next = theme() === 'dark' ? 'light' : 'dark';
  document.documentElement.dataset.theme = next;
  try { localStorage.setItem('otm-theme', next); } catch {}
  renderTheme();
}
function toggleLanguageMenu(open) {
  const show = open ?? $('language-menu').classList.contains('hidden');
  $('language-menu').classList.toggle('hidden', !show);
  $('language-toggle').setAttribute('aria-expanded', String(show));
}
function updateWorkspace() {
  $('workspace-name').textContent = state.workspace.split(/[\\/]/).pop() || text('workspace.project');
  const parts = state.workspace.split(/[\\/]/).filter(Boolean);
  $('workspace-path').textContent = parts.length > 2 ? `…\\${parts.slice(-2).join('\\')}` : state.workspace;
  $('workspace-path').title = state.workspace;
}
function renderEngines() {
  const box = $('engines'); box.replaceChildren();
  const locked = running && !canSwitchEngine(running);
  for (const item of state.engines) {
    const selected = item.id === state.settings.engine;
    const choice = elt('label', `engine-choice${selected ? ' is-selected' : ''}${locked ? ' is-disabled' : ''}`);
    choice.title = item.subtitle;
    const glyph = elt('span', 'engine-glyph');
    glyph.append(icon(item.id));
    const copy = elt('span', 'engine-copy');
    copy.append(elt('span', 'engine-title', item.name), elt('span', 'engine-description', item.subtitle));
    const radio = elt('input', 'engine-radio');
    radio.type = 'radio'; radio.name = 'engine'; radio.value = item.id;
    radio.checked = selected; radio.disabled = locked;
    radio.setAttribute('aria-label', item.name);
    radio.addEventListener('change', () => switchEngine(item.id));
    choice.append(glyph, copy, radio);
    box.append(choice);
  }
  $('engine-count').textContent = text('engine.count', {count: state.engines.length});
  $('groups-engine').textContent = engine().name;
}
async function switchEngine(id) {
  if (id === state.settings.engine) return;
  if (!canSwitchEngine(running)) {showError(text('engine.blocked')); return;}
  captureValues();
  try {
    const result = await window.vees.setEngine(id);
    state.settings = result.settings; state.workspace = result.workspace;
    $('search').value = '';
    selectDefault();
    updatePython(result.python);
    render();
  } catch (error) {showError(error.message);}
}
function updatePython(check) {
  pythonCheck = check;
  const badge = $('python-status');
  badge.className = `runtime${check.ok ? '' : ' bad'}`;
  badge.textContent = check.ok ? text('python.ready', {version: check.version}) : text('python.needed');
  badge.title = check.ok ? state.settings.python : check.message;
}
function renderGroups() {
  const nav = $('groups'); nav.replaceChildren();
  for (const group of engine().groups) {
    const count = tools().filter(t => t.group === group).length;
    const active = page === 'form' && activeGroup === group;
    const button = elt('button', `nav-item${active ? ' active' : ''}`);
    button.type = 'button';
    if (active) button.setAttribute('aria-current', 'true');
    button.append(icon(groupIcons[group] || 'archive'), elt('span', '', groupName(group)));
    if (count > 1) button.append(elt('span', 'nav-count', String(count)));
    button.disabled = running;
    button.addEventListener('click', () => {
      if (running) {showError(text('engine.blocked')); return;}
      openToolGroup(group);
    });
    nav.append(button);
    if (group === patchAfter[engine().id]) nav.append(patchItem());
  }
}
// What the patch page writes depends on the engine, so its name does too.
function patchItem() {
  const button = elt('button', `nav-item${page === 'patch' ? ' active' : ''}`);
  button.type = 'button';
  button.id = 'nav-patch';
  if (page === 'patch') button.setAttribute('aria-current', 'true');
  button.append(icon('patch'), elt('span', '', text(`nav.patch.${engine().id}`)));
  button.addEventListener('click', () => showPage('patch'));
  return button;
}
function renderTools() {
  const query = $('search').value.toLowerCase().trim();
  // Search both languages, so a term finds its tool whichever language is showing.
  const words = t => [t.title, t.description, t.group, t.script, t.vi?.title, t.vi?.description, groupName(t.group)].join(' ').toLowerCase();
  const visible = tools().filter(t => query ? words(t).includes(query) : t.group === activeGroup);
  $('group-title').textContent = query ? text('browser.results') : groupName(activeGroup);
  $('group-subtitle').textContent = query ? text('browser.matching', {count: visible.length, engine: engine().name}) : groupSummary(activeGroup);
  $('tool-count').textContent = text('browser.footer', {count: tools().length, groups: engine().groups.length});
  const list = $('tool-list'); list.replaceChildren();
  if (!visible.length) list.append(elt('div', 'panel-empty', text('browser.none')));
  for (const t of visible) {
    const button = elt('button', `tool-item${activeId === t.id ? ' active' : ''}`);
    button.type = 'button';
    if (activeId === t.id) button.setAttribute('aria-current', 'page');
    const line = elt('span', 'tool-name');
    line.append(elt('span', '', toolText(t, 'title')));
    if (activeId === t.id) line.append(icon('arrow'));
    button.append(line, elt('span', 'tool-description', toolText(t, 'description')));
    if (query) button.append(elt('span', 'tool-group-tag', groupName(t.group)));
    button.disabled = running;
    button.addEventListener('click', () => {
      if (running) {showError(text('engine.blocked')); return;}
      captureValues(); activeId = t.id; activeGroup = t.group; render();
    });
    list.append(button);
  }
}
function captureValues() {
  if (!state) return;
  const current = tool();
  if (!current) return;
  const values = {};
  for (const arg of current.args) {
    const input = document.querySelector(`[data-arg="${CSS.escape(arg.name)}"]`);
    if (input) values[arg.name] = arg.kind === 'bool' ? input.checked : input.value;
  }
  formValues[current.id] = values;
}
function renderForm() {
  const current = tool();
  if (!current) return;
  breadcrumbs($('breadcrumb'), [engine().name, groupName(current.group)], current.script);
  $('tool-title').textContent = toolText(current, 'title');
  $('tool-description').textContent = toolText(current, 'description');
  $('notice').classList.toggle('hidden', !current.note);
  $('notice').textContent = toolText(current, 'note');
  const values = formValues[current.id] || state.settings.values[current.id] || {};
  const fields = $('form-fields'); fields.replaceChildren();
  for (const [index, arg] of current.args.entries()) {
    const field = elt('div',`field ${arg.kind === 'bool' ? 'toggle-field' : ''} ${arg.repeat || arg.help?.length > 85 ? 'wide' : ''}`);
    const label = elt('label','',titleOf(arg.name));
    label.htmlFor = `arg-${index}`;
    if (arg.required) label.append(elt('span','required','*'));
    let input;
    if (arg.kind === 'bool') {
      input = elt('input'); input.type = 'checkbox'; input.checked = !!values[arg.name];
      input.id = `arg-${index}`; input.dataset.arg = arg.name;
      const words = elt('div'); words.append(label);
      if (arg.help) words.append(elt('div','help',arg.help));
      field.append(input,words);
    } else {
      field.append(label);
      const row = elt('div','input-row');
      input = arg.repeat ? elt('textarea') : elt('input');
      if (!arg.repeat) input.type = arg.kind === 'number' ? 'text' : 'text';
      input.id = `arg-${index}`; input.dataset.arg = arg.name;
      input.value = values[arg.name] ?? '';
      input.placeholder = text(arg.repeat ? 'field.lines' : ['save', 'dir', 'file', 'path'].includes(arg.kind) ? `field.${arg.kind}` : 'field.optional');
      row.append(input);
      const browse = (label, kind) => {
        const button = elt('button','browse',label); button.type = 'button';
        button.addEventListener('click', async () => {
          try {
            const selected = await window.vees.choosePath(kind, arg.repeat ? '' : input.value, kind === 'dir' ? [] : filtersFor(arg));
            if (selected) input.value = arg.repeat && input.value.trim() ? `${input.value.trim()}\n${selected}` : selected;
            input.focus();
          } catch (error) {showError(error.message);}
        });
        row.append(button);
      };
      if (arg.kind === 'path') {browse(text('field.chooseFile'), 'file'); browse(text('field.chooseFolder'), 'dir');}
      else if (['file','dir','save'].includes(arg.kind)) browse(text('field.browse'), arg.kind);
      field.append(row);
      if (arg.help) field.append(elt('div','help',arg.help));
    }
    fields.append(field);
  }
  checkMissing();
  $('run-hint').textContent = `${current.script}${current.prefix.length ? ' ' + current.prefix.join(' ') : ''} · ${state.workspace}`;
  $('run-button').disabled = running;
  $('cancel-button').disabled = !running;
}
// The red notice for files a tool reads from the project folder and cannot find.
// The likeliest cause is a wrong project folder, so it asks about that first.
function renderMissing(container, missing) {
  container.classList.toggle('hidden', !missing.length);
  container.replaceChildren();
  if (!missing.length) return;
  const body = elt('div');
  const actions = elt('div', 'missing-actions');
  const change = elt('button', 'button primary', text('missing.change'));
  change.type = 'button';
  change.addEventListener('click', chooseWorkspace);
  const open = elt('button', 'button', text('workspace.open'));
  open.type = 'button';
  open.addEventListener('click', async () => {const error = await window.vees.openWorkspace(); if (error) showError(error);});
  actions.append(elt('code', 'missing-folder mono', state.workspace), change, open);
  const list = elt('ul', 'missing-list');
  for (const item of missing) {
    const row = elt('li');
    row.append(elt('code', 'mono', item.path.replace(/\//g, '\\')), elt('span', '', ` · ${text(`missing.hint.${item.hint}`)}`));
    list.append(row);
  }
  body.append(elt('strong', '', text('missing.title', {count: missing.length})), elt('div', 'missing-where', text('missing.where')),
    actions, elt('div', 'missing-files', text('missing.files')), list, elt('div', 'missing-next', text('missing.next')));
  container.append(body);
}
async function checkMissing() {
  const current = tool();
  if (!current) return;
  let missing = [];
  try { missing = await window.vees.missingFiles(current.id); } catch {}
  if (tool() !== current || page !== 'form') return;
  renderMissing($('missing'), missing);
}
async function checkPatchMissing() {
  const engineId = engine().id;
  let missing = [];
  try { missing = await window.vees.missingFiles(`patch:${engineId}`); } catch {}
  if (page !== 'patch' || engine().id !== engineId) return;
  patchMissing = missing;
  renderMissing($('patch-missing'), patchMissing);
  updatePatchReady();
}
function breadcrumbs(node, parts, script) {
  node.replaceChildren();
  parts.forEach((part, index) => {
    if (index) node.append(elt('span', '', '/'));
    node.append(elt('span', '', part));
  });
  if (script) node.append(elt('span', '', '/'), elt('span', 'script mono', script));
}
function showPage(next) {
  if (next === 'form' && !canOpenTools(running)) {
    showError(text('engine.blocked'));
    return;
  }
  page = next;
  if (next === 'form') selectDefault();
  render();
}
const PHASES = ['prepare', 'check', 'create'];
function renderPatch() {
  const {sheetPath, outputPath} = patchState();
  breadcrumbs($('patch-breadcrumb'), [engine().name]);
  $('patch-title').textContent = text(`nav.patch.${engine().id}`);
  $('patch-scope').textContent = text(`patch.scope.${engine().id}`);
  showValue($('patch-file'), sheetPath, 'patch.noSheet');
  showValue($('patch-output'), outputPath, 'patch.noOutput');
  // Steps: choose, then patch (running or stopped on issues), then try it in game.
  const current = patchStage === 'done' ? 2 : patchStage === 'choose' ? 0 : 1;
  ['choose', 'create', 'try'].forEach((name, index) => {
    const step = $(`step-${name}`);
    step.classList.toggle('done', index < current);
    step.classList.toggle('active', index === current);
    step.querySelector('.step-mark').textContent = index < current ? '' : String(index + 1);
  });
  $('patch-setup').classList.toggle('hidden', patchStage !== 'choose');
  $('patch-working').classList.toggle('hidden', patchStage !== 'working');
  $('patch-issues').classList.toggle('hidden', patchStage !== 'issues');
  $('patch-done').classList.toggle('hidden', patchStage !== 'done');
  $('patch-log-card').classList.toggle('hidden', !$('patch-log').textContent);
  $('stop-patch').classList.toggle('hidden', !running);
  renderTasks();
  if (patchStage === 'done') {
    $('patch-done-body').textContent = text(`patch.done.${engine().id}`);
    $('patch-done-path').textContent = outputPath;
    const actions = $('patch-actions');
    actions.replaceChildren();
    if (engine().id === 'otomate') actions.append(actionButton('button primary', text('patch.nextRepack'), () => openTool('cpk-repack')));
    for (const action of successActions()) {
      const button = actionButton(action === 'open-folder' && engine().id !== 'otomate' ? 'button primary' : 'button',
        text(action === 'open-folder' ? 'patch.open' : 'patch.another'), () => action === 'open-folder' ? window.vees.openOutput() : chooseSheet());
      button.dataset.action = action;
      actions.append(button);
    }
  }
  updatePatchReady();
  checkPatchMissing();
}
function showValue(node, value, emptyKey) {
  node.textContent = value || text(emptyKey);
  node.classList.toggle('is-empty', !value);
  node.title = value || '';
}
function actionButton(className, label, callback) {
  const button = elt('button', className, label);
  button.type = 'button';
  button.addEventListener('click', callback);
  return button;
}
// Each task is done, running, failed (the check that found problems) or waiting.
function renderTasks() {
  PHASES.forEach((name, index) => {
    const task = $(`task-${name}`);
    task.classList.toggle('done', patchStage === 'done' || index < patchPhase);
    task.classList.toggle('active', running && patchStage === 'working' && index === patchPhase);
    task.classList.toggle('failed', patchStage === 'issues' && index === patchPhase);
  });
}
// The run card says what is still needed before a patch can be made.
function updatePatchReady() {
  const {sheetPath, outputPath} = patchState();
  const reason = !isXlsx(sheetPath) ? 'patch.need.sheet' : !outputPath ? 'patch.need.output' : patchMissing.length ? 'patch.need.files' : null;
  $('patch-ready').textContent = text(reason ? 'patch.notReady' : 'patch.ready');
  $('patch-ready-dot').className = `dot${reason ? '' : ' ready'}`;
  $('patch-reason').textContent = reason ? text(reason) : `${sheetPath.split(/[\\/]/).pop()} → ${outputPath}`;
  $('create-patch').disabled = running || !!reason;
}
function openTool(id) {
  const target = tools().find(item => item.id === id);
  if (!target || !canOpenTools(running)) return;
  activeGroup = target.group;
  activeId = target.id;
  page = 'form';
  $('search').value = '';
  render();
}
async function openToolGroup(group) {
  if (!canOpenTools(running)) {showError(text('engine.blocked')); return;}
  captureValues();
  activeGroup = group;
  const first = tools().find(t => t.group === group);
  if (first) activeId = first.id;
  page = 'form';
  $('search').value = '';
  render();
  const saved = await window.vees.setPatch({group});
  state.settings = saved.settings;
}
function render() {
  applyLanguage();
  // A group with one tool skips the tool list and goes straight to its form.
  const single = page === 'form' && !$('search').value.trim() && tools().filter(t => t.group === activeGroup).length === 1;
  document.querySelector('.app').className = `app page-${page}${single ? ' single-tool' : ''}`;
  renderEngines();
  updateWorkspace();
  renderGroups();
  if (page === 'patch') renderPatch();
  if (page === 'form') {renderTools(); renderForm();}
}
function showError(message) {
  if (page === 'patch') showPatchError(message);
  $('notice').classList.remove('hidden');
  $('notice').textContent = message;
}
function setLog(text) {currentLog = text; $('log').textContent = text; $('log').scrollTop = $('log').scrollHeight;}
function status(key, css) {
  runStatus = {key, css};
  $('run-status').textContent = text(key);
  $('run-status').className = `log-state ${css || ''}`;
  document.querySelector('.console-dot').className = `console-dot ${css || ''}`;
  document.querySelector('.log').classList.toggle('running', css === 'running');
}
function dialogContent(title, build) {
  $('dialog-title').textContent = title;
  const body = $('dialog-body');body.replaceChildren();build(body);
  $('info-dialog').showModal();
}
function paragraph(parent, text, cls = '') {parent.append(elt('p',cls,text));}
function action(parent, label, callback) {const b=elt('button','',label); b.type='button';b.addEventListener('click', callback);parent.append(b);}
function showDocs() {
  dialogContent(text('rail.docs'), body => {
    paragraph(body,text('docs.body', {engine: engine().name}));
    paragraph(body,text('docs.flow', {flow: (language() === 'vi' && engine().vi?.flow) || engine().flow}));
    for (const [label,name] of engine().docs) {
      action(body,(language() === 'vi' && engine().vi?.docs[name]) || label,async()=>{const error=await window.vees.openDocument(name);if(error)showError(error);});
    }
  });
}
function showPython() {
  dialogContent(text('rail.python'), body => {
    paragraph(body,text('python.body', {engine: engine().name, modules: engine().modules.join(', ')}));
    paragraph(body,text('python.current', {path: state.settings.python}),'mono');
    action(body,text('python.setup'), async () => {
      try {await window.vees.setupPython();$('info-dialog').close();}
      catch(error){showError(error.message);}
    });
    action(body,text('python.choose'), async () => {
      try {
        const result=await window.vees.choosePython();
        if(result){state.settings.python=result.python;updatePython(result.check);$('info-dialog').close();}
      } catch(error){showError(error.message);}
    });
  });
}

async function start() {
  state = await window.vees.state();
  formValues = structuredClone(state.settings.values || {});
  selectDefault();
  updatePython(state.python);
  render();
  $('search').addEventListener('input', renderTools);
  $('lang-en').addEventListener('click', () => {toggleLanguageMenu(false); chooseLanguage('en');});
  $('lang-vi').addEventListener('click', () => {toggleLanguageMenu(false); chooseLanguage('vi');});
  $('language-toggle').addEventListener('click', () => toggleLanguageMenu());
  document.addEventListener('click', event => {if (!$('language-switcher').contains(event.target)) toggleLanguageMenu(false);});
  document.addEventListener('keydown', event => {if (event.key === 'Escape') toggleLanguageMenu(false);});
  $('theme-toggle').addEventListener('click', toggleTheme);
  // Files are usually copied in from Explorer, so check again on return.
  window.addEventListener('focus', () => {if (page === 'form') checkMissing(); if (page === 'patch') checkPatchMissing();});
  $('choose-sheet').addEventListener('click', chooseSheet);
  $('choose-fixed').addEventListener('click', chooseSheet);
  $('choose-output').addEventListener('click', chooseOutput);
  $('create-patch').addEventListener('click', () => startPatch(false));
  $('stop-patch').addEventListener('click', () => window.vees.cancel());
  $('workspace-button').addEventListener('click', chooseWorkspace);
  $('open-folder').addEventListener('click', async () => {const error=await window.vees.openWorkspace();if(error)showError(error);});
  $('docs-button').addEventListener('click',showDocs);
  $('python-button').addEventListener('click',showPython);
  $('dialog-close').addEventListener('click',()=>$('info-dialog').close());
  $('clear-log').addEventListener('click',()=>setLog(''));
  $('tool-form').addEventListener('submit',event=>event.preventDefault());
  $('run-button').addEventListener('click',async()=>{
    if(running)return;
    captureValues();
    const current = tool();
    try {
      await window.vees.run(current.id,formValues[current.id]);
    } catch(error){showError(error.message);}
  });
  $('cancel-button').addEventListener('click',async()=>{await window.vees.cancel();});
  window.vees.on('run-start',event=>{
    running=true;render();setLog(`$ ${event.command.map(x=>/\s/.test(String(x))&&/\s/.test(x)?JSON.stringify(x):x).join(' ')}\n\n`);
    if (event.id === 'patch') {$('patch-log').textContent = ''; patchStage = 'working'; patchPhase = 0;}
    status('status.running','running');
    render();
  });
  window.vees.on('run-output',event=>{
    setLog(currentLog+event.text);
    if (page === 'patch') {
      $('patch-log').textContent += event.text;
      $('patch-log-card').classList.remove('hidden');
      const phase = String(event.text).match(/^(prepare|check|create):/m);
      if (phase) {patchPhase = PHASES.indexOf(phase[1]); renderTasks();}
    }
  });
  window.vees.on('run-end',event=>{
    running=false;const ok=event.code===0;
    setLog(`${currentLog}\n${ok?text('log.success'):event.signal?text('status.stopped'):text('log.exit', {code: event.code})}\n`);
    status(ok?'status.complete':event.signal?'status.stopped':'status.failed',ok?'success':'failed');
    if (event.id === 'patch') applyPatchResult(event);
    else render();
    window.vees.state().then(fresh=>{state.settings=fresh.settings;state.workspace=fresh.workspace;updatePython(fresh.python);}).catch(()=>{});
  });
}
function chooseLanguage(next) {
  if (languageChange().workbookPath) return;
  window.vees.setLanguage(next).then(result => {state.settings = result.settings; render();});
}
async function chooseWorkspace() {
  try {
    const result = await window.vees.chooseWorkspace();
    if (result) {state.workspace = result.workspace;updateWorkspace();renderForm();updatePython(result.python);}
  } catch(error){showError(error.message);}
}
async function chooseSheet() {
  const selected = await window.vees.choosePath('file', patchState().sheetPath, filtersFor({name: 'xlsx'}));
  if (!selected) return;
  if (!isXlsx(selected)) {
    showPatchError(text('patch.reject'));
    const cleared = await window.vees.setPatch({sheetPath: ''});
    state.settings = cleared.settings;
    patchStage = 'choose';
    render();
    return;
  }
  showPatchError('');
  const saved = await window.vees.setPatch({sheetPath: selected});
  state.settings = saved.settings;
  patchStage = 'choose';
  render();
}
async function chooseOutput() {
  const selected = await window.vees.choosePath('dir', patchState().outputPath);
  if (!selected) return;
  const saved = await window.vees.setPatch({outputPath: selected});
  state.settings = saved.settings;
  render();
}
function showPatchError(message) {
  const node = $('patch-error');
  node.textContent = message || '';
  node.classList.toggle('hidden', !message);
}
function applyPatchResult(result) {
  running = false;
  if (result.needsConfirm) return;
  if (result.stopped || result.signal === 'cancelled' || result.code === 130) {
    patchStage = 'choose';
    showPatchError(text('patch.stopped'));
  } else if (result.findings && result.findings.length) {
    patchStage = 'issues';
    const list = $('finding-list');
    list.replaceChildren();
    for (const finding of result.findings) list.append(elt('li', '', `${finding.sheet || ''} · ${finding.row}`));
  } else if (result.code === 0 && result.complete !== false && !result.error) {
    patchStage = 'done';
    showPatchError('');
  } else {
    patchStage = 'choose';
    showPatchError(result.failedStep ? text('patch.failed', {step: result.failedStep}) : text('patch.setup'));
  }
  render();
}
async function startPatch(confirmed) {
  if (running || !isXlsx(patchState().sheetPath)) return;
  showPatchError('');
  try {
    const result = await window.vees.runPatch({confirmed});
    if (result.needsConfirm) {
      if (window.confirm(text('patch.replace'))) return startPatch(true);
      return;
    }
    if (result.error) {
      running = false;
      patchStage = 'choose';
      const message = result.error === 'xlsx' ? text('patch.reject') : result.error === 'copy' ? result.message : text('patch.setup');
      showPatchError(message);
      render();
      return;
    }
    applyPatchResult(result);
  } catch (error) {running = false; showPatchError(error.message); render();}
}
start().catch(error=>{document.body.textContent=`Unable to start Otome Translator: ${error.message}`;});
