const $ = id => document.getElementById(id);
let state;
let activeGroup = null;
let activeId = null;
let running = false;
let page = 'form';
let patchStage = 'choose';
let patchPhase = 0;
let patchMissing = [];
let patchUntranslated = [];
let patchResult = {};
// The chosen workbook's worksheet names, read once per file.
let patchSheets = {path: '', names: null, error: ''};
// The measure screen's state: a screenshot, the line on it, and up to three clicked x positions.
const measure = {image: null, text: '', font: 'advfont1.ffu', screen: 'dialogue', points: [], zoomed: false,
  widths: null, widthsFor: '', busy: false, error: '', saved: {}, justSaved: ''};
const MEASURE_POINTS = ['start', 'end', 'edge'];
const MEASURE_FONTS = {'advfont1.ffu': 'I', 'advfont2.ffu': 'II', 'advfont3.ffu': 'III', 'advfont4.ffu': 'IV'};
// The screens a width can be saved for, named as in windows.json and the engine.
const MEASURE_SCREENS = ['dialogue', 'framed', 'backlog', 'narration'];
// Tools whose checks depend on the measured box widths; their forms show them.
const WIDTH_TOOLS = ['quarong', 'reflow', 'mksheet'];
// Advanced options on each engine's patch page, in the order they show.
const PATCH_OPTIONS = {
  otomate: [['dryRun', 'bool'], ['sheets', 'sheets'], ['allowOverflow', 'bool']],
  unity: [['dryRun', 'bool'], ['sheetName', 'sheet'], ['force', 'bool'], ['packer', ['auto', 'lz4', 'lzma', 'none', 'original']], ['tokens', 'lines']]
};
let formValues = {};
let currentLog = '';
let pythonCheck = null;
let runStatus = {key: 'status.idle', css: ''};

const acronyms = {jp: 'JP', vn: 'VN', cpk: 'CPK', id: 'ID', px: 'PX', aoc: 'AOC', exefs: 'ExeFS', romfs: 'RomFS'};
function titleOf(name) {
  const words = name.replace(/^--/, '').replace(/[-_]/g, ' ').replace(/\b[a-z]+\b/g, word => acronyms[word] || word);
  return words.charAt(0).toUpperCase() + words.slice(1);
}
// A field's label or help in the interface language: the catalog's `vi.args`
// where a tool has them, else the English name and help.
function argText(item, arg, field) {
  const vi = language() === 'vi' ? item.vi?.args?.[arg.name]?.[field] : '';
  return vi || (field === 'label' ? titleOf(arg.name) : arg.help);
}
// A tool that `follows` another (catalog: {tool, fields: {mine: theirs}}) takes
// those fields from it: the folder step 1 saved to is the folder step 2 reads.
// Null unless every one of them is filled in `source`.
function handedOn(item, source) {
  const out = {};
  for (const [mine, theirs] of Object.entries(item.follows?.fields || {})) {
    const value = String(source?.[theirs] ?? '').trim();
    if (!value) return null;
    out[mine] = value;
  }
  return item.follows ? out : null;
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
  Diagnostics: 'diagnostics', Dump: 'download', Inspect: 'search', Text: 'sheet', Layout: 'layout', Release: 'package', Patch: 'patch'};
// The patch page sits in the group list next to the group whose output it shares.
const patchAfter = {otomate: 'Build', unity: 'Text'};
// The measure screen uses the Otomate width tools, so only that engine offers it.
const measureAfter = {otomate: 'Diagnostics'};
// Make game font opens on a row per stock .ffu instead of its flag form.
const FONT_TOOL = 'ffugen';
const fontPage = {templates: [], output: '', outputChosen: false, result: null};
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
  for (const node of document.querySelectorAll('[data-i18n-aria]')) node.setAttribute('aria-label', text(node.dataset.i18nAria));
  $('language-code').textContent = language().toUpperCase();
  $('language-toggle').title = text('language.label');
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
  $('theme-toggle').title = text('theme.dark');
}
const SIDEBAR_MIN = 200;
const SIDEBAR_MAX = 480;
const SIDEBAR_DEFAULT = 250;
function setSidebarWidth(width, persist) {
  const next = Math.round(Math.min(SIDEBAR_MAX, Math.max(SIDEBAR_MIN, width)));
  document.documentElement.style.setProperty('--sidebar-width', `${next}px`);
  $('sidebar-resize').setAttribute('aria-valuenow', String(next));
  if (persist) { try { localStorage.setItem('otm-sidebar-width', String(next)); } catch {} }
  if (!$('language-menu').classList.contains('hidden')) placeLanguageMenu();
  if (!$('settings-menu').classList.contains('hidden')) placeSettingsMenu();
  return next;
}
function bindSidebarResize() {
  const handle = $('sidebar-resize');
  setSidebarWidth(document.querySelector('.sidebar').getBoundingClientRect().width, false);
  handle.addEventListener('pointerdown', event => {
    if (event.button !== 0) return;
    event.preventDefault();
    const startX = event.clientX;
    const startWidth = document.querySelector('.sidebar').getBoundingClientRect().width;
    handle.setPointerCapture(event.pointerId);
    document.body.classList.add('resizing-sidebar');
    const move = ev => setSidebarWidth(startWidth + ev.clientX - startX, false);
    const end = ev => {
      handle.removeEventListener('pointermove', move);
      handle.removeEventListener('pointerup', end);
      handle.removeEventListener('pointercancel', end);
      document.body.classList.remove('resizing-sidebar');
      setSidebarWidth(startWidth + ev.clientX - startX, true);
    };
    handle.addEventListener('pointermove', move);
    handle.addEventListener('pointerup', end);
    handle.addEventListener('pointercancel', end);
  });
  handle.addEventListener('dblclick', () => setSidebarWidth(SIDEBAR_DEFAULT, true));
  handle.addEventListener('keydown', event => {
    const current = document.querySelector('.sidebar').getBoundingClientRect().width;
    if (event.key === 'ArrowRight') { event.preventDefault(); setSidebarWidth(current + 16, true); }
    else if (event.key === 'ArrowLeft') { event.preventDefault(); setSidebarWidth(current - 16, true); }
    else if (event.key === 'Home') { event.preventDefault(); setSidebarWidth(SIDEBAR_DEFAULT, true); }
  });
}
function toggleTheme() {
  const next = theme() === 'dark' ? 'light' : 'dark';
  document.documentElement.dataset.theme = next;
  try { localStorage.setItem('otm-theme', next); } catch {}
  renderTheme();
}
function placeAnchoredMenu(menu, toggle, minWidth) {
  const rect = toggle.getBoundingClientRect();
  const width = Math.max(rect.width, minWidth);
  const left = Math.min(Math.max(8, rect.left), window.innerWidth - width - 8);
  const height = menu.offsetHeight || 140;
  const above = rect.top - 6 - height;
  const top = above >= 8 ? above : Math.min(rect.bottom + 6, window.innerHeight - height - 8);
  menu.style.left = `${left}px`;
  menu.style.width = `${width}px`;
  menu.style.bottom = 'auto';
  menu.style.top = `${Math.max(8, top)}px`;
}
function placeLanguageMenu() {
  placeAnchoredMenu($('language-menu'), $('language-toggle'), 220);
}
function placeSettingsMenu() {
  placeAnchoredMenu($('settings-menu'), $('settings-button'), 240);
}
function toggleSettingsMenu(open) {
  const menu = $('settings-menu');
  const show = open ?? menu.classList.contains('hidden');
  if (!show && menu.contains(document.activeElement)) $('settings-button').focus();
  menu.classList.toggle('hidden', !show);
  $('settings-button').setAttribute('aria-expanded', String(show));
  if (show) {
    toggleLanguageMenu(false);
    placeSettingsMenu();
  }
}
function toggleLanguageMenu(open) {
  const menu = $('language-menu');
  const show = open ?? menu.classList.contains('hidden');
  if (!show && menu.contains(document.activeElement)) $('language-toggle').focus();
  menu.classList.toggle('hidden', !show);
  $('language-toggle').setAttribute('aria-expanded', String(show));
  if (show) {
    toggleSettingsMenu(false);
    placeLanguageMenu();
    menu.querySelector('[aria-checked=true]')?.focus();
  }
}
// The folder's name, and under it the folder it sits in (the name is not
// repeated). The stylesheet clips that path from its start, so the nearest
// folders stay readable.
function updateWorkspace() {
  const trimmed = state.workspace.replace(/[\\/]+$/, '');
  const cut = Math.max(trimmed.lastIndexOf('/'), trimmed.lastIndexOf('\\'));
  $('workspace-name').textContent = trimmed.slice(cut + 1) || text('workspace.project');
  const where = elt('bdi', '', cut > 0 ? trimmed.slice(0, cut) : trimmed.slice(0, cut + 1));
  where.dir = 'ltr';
  $('workspace-path').replaceChildren(where);
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
  // The footer's Python button carries the same warning on pages without the
  // badge, in words as well as the dot: colour alone says nothing to everyone.
  const pythonButton = $('python-button');
  pythonButton.classList.toggle('needs-attention', !check.ok);
  $('settings-button').classList.toggle('needs-attention', !check.ok);
  pythonButton.title = text(check.ok ? 'rail.python' : 'rail.pythonNeeded');
  pythonButton.querySelector('bdi').textContent = pythonButton.title;
  promptPython();
}
// A Python that cannot run the engine's tools is said at once, in a dialog with
// the fix, not left to the badge: once per engine a session, never over the
// start page or a run. The badge and the sidebar button open it again.
const pythonPrompted = new Set();
function promptPython() {
  const ready = () => pythonCheck && !pythonCheck.ok && !running && state?.settings.engineChosen && page !== 'start'
    && !pythonPrompted.has(state.settings.engine);
  if (ready()) whenNoDialog(() => { if (ready()) showPython(); });
}
// Runs `then` once no dialog is open (an update notice, say), so two never stack.
function whenNoDialog(then) {
  const open = document.querySelector('dialog[open]');
  if (!open) return then();
  open.addEventListener('close', () => whenNoDialog(then), {once: true});
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
    if (group === measureAfter[engine().id]) nav.append(pageItem('measure', 'ruler', text('nav.measure')));
  }
}
function pageItem(name, iconName, label) {
  const button = elt('button', `nav-item${page === name ? ' active' : ''}`);
  button.type = 'button';
  if (page === name) button.setAttribute('aria-current', 'true');
  button.append(icon(iconName), elt('span', '', label));
  button.addEventListener('click', () => showPage(name));
  return button;
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
// A tool that writes only when given --apply (or replaces files only when
// given --overwrite) has no checkbox for it: Run never sets it, and when the run
// ends cleanly and says it held back (the tools print "add --apply to write
// <where>", "them --overwrite de ghi de vao <where>"), the app asks, then runs
// it again with the flag. A tick nobody remembers is gone.
const CONFIRM = ['--apply', '--overwrite'];
const confirmFlag = item => CONFIRM.find(flag => item.args.some(arg => arg.kind === 'bool' && arg.name === flag)) || '';
let applyOffer = null;   // {id, values, output, flag} while such a run is going
let runRequest = null;   // {id, values} for the run in progress, including a hidden --apply
let runReveal = null;    // {id, path} after a run that left files to open
async function offerApply(offer) {
  const item = tools().find(t => t.id === offer.id);
  if (!item) return;
  const overwrite = offer.flag === '--overwrite';
  const words = overwrite ? 'overwrite' : 'apply';
  const where = offer.output.match(new RegExp(`${offer.flag}\\s+(?:de ghi de vao|de ghi vao|to overwrite|to write)\\s+(.+?)\\s*$`, 'm'))?.[1];
  // What the write would replace, as "old -> backup" where a copy is kept.
  // rrlib tools name both (the copy sits beside the old file); for a tool that
  // names one output file, look whether it is already there: it is copied to
  // .bak, .bak2 ... only when it is also the file the tool read.
  let replaced = offer.output.match(/^se thay file da co[^:]*:\s*(.+?)\s*$/m)?.[1]?.split(/,\s*/) || [];
  let kept = replaced.length > 0;
  if (!replaced.length && where && !overwrite) {
    const absolute = /^([a-zA-Z]:)?[\\/]/.test(where) ? where : `${state.workspace}/${where}`;
    try {
      if (await window.vees.fileExists(absolute)) {
        const name = where.split(/[\\/]/).pop();
        kept = Object.entries(offer.values).some(([field, value]) => field !== '--out' && String(value ?? '').trim() === where);
        let backup = `${absolute}.bak`;
        for (let n = 2; kept && n < 100 && await window.vees.fileExists(backup); n++) backup = `${absolute}.bak${n}`;
        replaced = [kept ? `${name} -> ${backup.split(/[\\/]/).pop()}` : where];
      }
    } catch {}
  }
  const entries = replaced.map(line => {const [name, backup] = line.split(/\s*->\s*/); return {name, backup};});
  // True until the user says write, and that run starts a log of its own.
  setLog(`${currentLog}${text('apply.declined')}\n`);
  whenNoDialog(() => {
    dialogContent(text(`${words}.title`), body => {
      paragraph(body, text(`${words}.body`, {tool: toolText(item, 'title')}));
      if (where) {paragraph(body, text(overwrite ? 'overwrite.where' : 'apply.where')); paragraph(body, where, 'mono dialog-path');}
      // Files that get replaced stand out in a warning box: yellow while a
      // .bak keeps the old one, red when nothing does.
      if (replaced.length) {
        const box = elt('div', `notice dialog-warning${!overwrite && !kept ? ' missing' : ''}`);
        const lines = elt('div');
        // The heading names the files (up to three); the list below has them all.
        const names = replaced.map(line => line.split(/\s*->\s*/)[0]);
        const heading = key => text(names.length === 1 ? `${key}One` : names.length <= 3 ? `${key}Few` : `${key}Title`,
          {file: names[0], files: names.join(', '), count: names.length});
        if (overwrite) lines.append(elt('strong', '', heading('overwrite.changed')), elt('div', '', text('overwrite.changed')));
        else if (kept) lines.append(elt('strong', '', heading('apply.replace')), elt('div', '', text('apply.replaceKept')));
        else lines.append(elt('strong', '', text('apply.replace', {file: names[0].split(/[\\/]/).pop()})));
        for (const line of replaced) lines.append(elt('div', 'mono', line.replace(/\s*->\s*/, '  →  ')));
        box.append(lines);
        body.append(box);
      } else if (overwrite) paragraph(body, text('overwrite.same'));
      const actions = elt('div', 'dialog-actions');
      const add = (label, onClick, className = 'button') => actions.append(actionButton(className, label, onClick));
      if (overwrite && entries.length) {
        // Like a file manager: keep what was changed, replace it, or decide one by one.
        const names = entries.map(entry => entry.name);
        add(text('overwrite.keepAll'), () => runConfirmed(offer, {'--keep': names.join('\n')}), 'button primary');
        add(text('overwrite.replaceAll'), () => runConfirmed(offer));
        if (entries.length > 1) add(text('overwrite.each'), () => askEach(offer, entries));
      } else add(text(`${words}.write`), () => runConfirmed(offer), 'button primary');
      add(text(overwrite ? 'overwrite.cancel' : 'apply.notNow'), () => $('info-dialog').close(), 'button quiet');
      body.append(actions);
    });
    $('info-dialog').querySelector('.dialog-actions .primary')?.focus();
  });
}
// Runs the tool again with the flag it held back for, plus what the questions chose.
async function runConfirmed(offer, extra = {}) {
  $('info-dialog').close();
  const values = {...offer.values, [offer.flag]: true, ...extra};
  try {runRequest = {id: offer.id, values}; await window.vees.run(offer.id, values);}
  catch (error) {runRequest = null; showError(error.message);}
}
// One changed file at a time, as Finder asks: keep it or replace it, with a box
// to do the same for the rest. Keep is the default; Stop writes nothing.
function askEach(offer, entries) {
  const keep = [];
  let index = 0;
  const step = () => {
    if (index >= entries.length) return runConfirmed(offer, {'--keep': keep.join('\n')});
    const {name, backup} = entries[index];
    const left = entries.length - index - 1;
    dialogContent(text('overwrite.eachTitle', {index: index + 1, total: entries.length}), body => {
      paragraph(body, name, 'mono dialog-file');
      paragraph(body, text(/\.png$/i.test(name) ? 'overwrite.eachBody' : 'overwrite.eachOther'));
      if (backup) paragraph(body, text('overwrite.replaceNote', {backup}), 'help');
      let same = null;
      if (left) {
        const label = elt('label', 'dialog-check');
        same = elt('input');
        same.type = 'checkbox';
        label.append(same, elt('span', '', text('overwrite.sameForRest', {count: left})));
        body.append(label);
      }
      const choose = keepIt => () => {
        const upto = same?.checked ? entries.length : index + 1;
        for (; index < upto; index++) if (keepIt) keep.push(entries[index].name);
        step();
      };
      const actions = elt('div', 'dialog-actions');
      actions.append(actionButton('button primary', text('overwrite.keepOne'), choose(true)),
        actionButton('button', text('overwrite.replaceOne'), choose(false)),
        actionButton('button quiet', text('overwrite.stop'), () => $('info-dialog').close()));
      body.append(actions);
    });
    $('info-dialog').querySelector('.dialog-actions .primary')?.focus();
  };
  step();
}
function renderForm() {
  const current = tool();
  if (!current) return;
  breadcrumbs($('breadcrumb'), [engine().name, groupName(current.group)], current.script);
  $('tool-title').textContent = toolText(current, 'title');
  $('tool-description').textContent = toolText(current, 'description');
  $('notice').classList.toggle('hidden', !current.note);
  $('notice').textContent = toolText(current, 'note');
  // Make game font fills template, output and fonts from its rows; the rest of
  // its arguments are the advanced settings inside the panel.
  const mapping = current.id === FONT_TOOL;
  $('fonts-panel').classList.toggle('hidden', !mapping);
  $('form-generic').classList.toggle('hidden', mapping);
  if (mapping) renderFonts();
  const values = {...(formValues[current.id] || state.settings.values[current.id] || {})};
  if (current.follows) {
    const given = handedOn(current, formValues[current.follows.tool] || state.settings.values[current.follows.tool]);
    for (const [name, value] of Object.entries(given || {})) if (!String(values[name] ?? '').trim()) values[name] = value;
  }
  $('form-fields').replaceChildren();
  $('fonts-options').replaceChildren();
  const fields = mapping ? $('fonts-options') : $('form-fields');
  const fieldFor = (arg, index, paired) => {
    const field = elt('div',`field ${arg.kind === 'bool' ? 'toggle-field' : ''} ${!paired && (arg.repeat || arg.help?.length > 85) ? 'wide' : ''}`);
    const label = elt('label','',argText(current, arg, 'label'));
    label.htmlFor = `arg-${index}`;
    if (arg.required) label.append(elt('span','required','*'));
    let input;
    if (arg.kind === 'bool') {
      input = elt('input'); input.type = 'checkbox'; input.checked = !!values[arg.name];
      input.id = `arg-${index}`; input.dataset.arg = arg.name;
      const words = elt('div'); words.append(label);
      if (arg.help) words.append(elt('div','help',argText(current, arg, 'help')));
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
            const selected = await window.vees.choosePath(kind, arg.repeat ? '' : input.value, kind === 'dir' ? [] : filtersFor(arg), kind === 'file' ? startCandidates(arg) : []);
            if (selected) {
              const extension = companionFor(arg);
              const other = extension && companionPath(selected, extension);
              if (extension && (!other || !await window.vees.fileExists(other))) {
                showError(text('field.needBody', {file: other ? other.split(/[/\\]/).pop() : `.${extension}`}));
              } else input.value = arg.repeat && input.value.trim() ? `${input.value.trim()}\n${selected}` : selected;
            }
            input.focus();
          } catch (error) {showError(error.message);}
        });
        row.append(button);
      };
      if (arg.kind === 'path') {browse(text('field.chooseFile'), 'file'); browse(text('field.chooseFolder'), 'dir');}
      else if (['file','dir','save'].includes(arg.kind)) browse(text('field.browse'), arg.kind);
      field.append(row);
      if (arg.help) field.append(elt('div','help',argText(current, arg, 'help')));
    }
    return field;
  };
  for (let index = 0; index < current.args.length; index++) {
    const arg = current.args[index];
    if (mapping && MAPPED_ARGS.includes(arg.name)) continue;
    if (arg.kind === 'bool' && arg.name === confirmFlag(current)) continue;
    if (arg.hidden) continue;
    // A font and the size that belongs to it share one row: the file on the
    // left, the number on the right.
    const family = /^--font-(.+)$/.exec(arg.name);
    const next = current.args[index + 1];
    if (family && next?.name === `--px-${family[1]}`) {
      const pair = elt('div', 'field-pair');
      pair.append(fieldFor(arg, index, true), fieldFor(next, index + 1, true));
      fields.append(pair);
      index++;
      continue;
    }
    fields.append(fieldFor(arg, index, false));
  }
  checkMissing();
  renderRunReveal();
  if (engine().id === 'otomate' && WIDTH_TOOLS.includes(current.id)) showWidths($('form-widths'));
  else $('form-widths').classList.add('hidden');
  // A built-in tool has no script and does not run in the project folder.
  $('run-hint').textContent = current.builtin ? text('tool.builtin')
    : `${current.script}${current.prefix.length ? ' ' + current.prefix.join(' ') : ''} · ${state.workspace}`;
  $('run-button').disabled = running;
  $('cancel-button').disabled = !running;
}
// Opens a tool with some of its fields filled in. Without `replace`, a field the
// user already filled keeps its value.
function openToolWith(id, values, replace = false) {
  if (page === 'form') captureValues();
  const current = {...(formValues[id] || state.settings.values[id] || {})};
  for (const [name, value] of Object.entries(values)) {
    if (value && (replace || !String(current[name] ?? '').trim())) current[name] = value;
  }
  formValues[id] = current;
  openTool(id);
}
// The red notice for files a tool reads from the project folder and cannot find.
// The likeliest cause is a wrong project folder, so it asks about that first.
function missingList(items) {
  const list = elt('ul', 'missing-list');
  for (const item of items) {
    const row = elt('li');
    row.append(elt('code', 'mono', item.path.replace(/\//g, '\\')), elt('span', '', ` · ${text(`missing.hint.${item.hint}`)}`));
    list.append(row);
  }
  return list;
}
function renderMissing(container, all) {
  // Fonts named by the example fonts.json are that set-up's choice, not a need of
  // every game: they get a quieter note of their own, and alone they are no error.
  const missing = all.filter(item => item.hint !== 'example-font');
  const examples = all.filter(item => item.hint === 'example-font');
  container.classList.toggle('hidden', !all.length);
  container.classList.toggle('missing', missing.length > 0);
  container.replaceChildren();
  if (!all.length) return;
  const body = elt('div');
  if (missing.length) {
    const actions = elt('div', 'missing-actions');
    const change = elt('button', 'button primary', text('missing.change'));
    change.type = 'button';
    change.addEventListener('click', chooseWorkspace);
    const open = elt('button', 'button', text('workspace.open'));
    open.type = 'button';
    open.addEventListener('click', async () => {const error = await window.vees.openWorkspace(); if (error) showError(error);});
    actions.append(elt('code', 'missing-folder mono', state.workspace), change, open);
    body.append(elt('strong', '', text('missing.title', {count: missing.length})), elt('div', 'missing-where', text('missing.where')),
      actions, elt('div', 'missing-files', text('missing.files')), missingList(missing), elt('div', 'missing-next', text('missing.next')));
  }
  if (examples.length) {
    const note = elt('div', missing.length ? 'missing-examples' : '');
    note.append(elt('strong', '', text('missing.example.title')), elt('div', 'missing-example-body', text('missing.example.body')), missingList(examples));
    body.append(note);
  }
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
  // Before a run only: afterwards the result card says which widths were used.
  if (engineId === 'otomate' && patchStage === 'choose') showWidths($('patch-widths'));
  else $('patch-widths').classList.add('hidden');
}
// The widths card: what windows.json holds for this project, or that it holds nothing.
async function showWidths(box) {
  let saved = {};
  try { saved = await window.vees.measureSaved(); } catch {}
  const measured = MEASURE_SCREENS.filter(screen => saved[screen]?.ceiling);
  box.classList.remove('hidden');
  box.classList.toggle('none', !measured.length);
  box.replaceChildren();
  const iconBox = elt('span', 'pick-icon');
  iconBox.append(icon('ruler'));
  const body = elt('div', 'widths-body');
  body.append(elt('strong', '', text('widths.title')), elt('div', 'pick-hint', text(measured.length ? 'widths.some' : 'widths.none')));
  if (measured.length) {
    const chips = elt('div', 'width-chips');
    for (const screen of MEASURE_SCREENS) {
      const chip = elt('span', `width-chip${saved[screen]?.ceiling ? '' : ' off'}`);
      chip.append(elt('span', '', text(`measure.screen.${screen}`)),
        elt('b', '', saved[screen]?.ceiling ? text('widths.unit', {ceiling: saved[screen].ceiling}) : text('measure.notMeasured')));
      chips.append(chip);
    }
    body.append(chips);
  }
  box.append(iconBox, body, actionButton('button', text(measured.length ? 'widths.remeasure' : 'nav.measure'), () => showPage('measure')));
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
  if (patchStage !== 'choose') $('patch-widths').classList.add('hidden');
  $('patch-working').classList.toggle('hidden', patchStage !== 'working');
  $('patch-issues').classList.toggle('hidden', patchStage !== 'issues');
  $('patch-done').classList.toggle('hidden', patchStage !== 'done');
  $('patch-log-card').classList.toggle('hidden', !$('patch-log').textContent);
  $('stop-patch').classList.toggle('hidden', !running);
  renderTasks();
  if (patchStage === 'done') {
    const dry = !!patchResult.dryRun;
    $('patch-done').classList.toggle('dry', dry);
    $('patch-done-title').textContent = text(dry ? 'patch.dryTitle' : 'patch.doneTitle');
    $('patch-done-body').textContent = dry ? text('patch.dryBody') : text(`patch.done.${engine().id}`);
    // Always say what the width check used: the measured widths, or that there were none.
    const used = MEASURE_SCREENS.filter(screen => patchResult.widths?.[screen])
      .map(screen => `${text(`measure.screen.${screen}`)} ${patchResult.widths[screen]}`);
    $('patch-done-measure').classList.toggle('hidden', engine().id !== 'otomate');
    // Chapter titles need translated prefixes; say so when the run had none.
    const labels = tools().find(item => item.id === 'filltitles-prefixes');
    $('patch-titles').classList.toggle('hidden', !patchResult.titlesSkipped || !labels);
    if (labels) {
      $('patch-titles-text').textContent = text('patch.titlesSkipped', {file: 'work\\title_prefixes.xlsx', sheet: 'title_prefix', tool: toolText(labels, 'title')});
      $('patch-titles-tool').textContent = toolText(labels, 'title');
    }
    $('patch-done-widths').textContent = used.length ? text('patch.widthsUsed', {list: used.join(', ')}) : text('patch.unmeasuredDone');
    $('patch-done-measure-open').querySelector('bdi').textContent = text(used.length ? 'widths.remeasure' : 'nav.measure');
    $('patch-done-path').textContent = outputPath;
    renderOverflow();
    renderUntranslated();
    const actions = $('patch-actions');
    actions.replaceChildren();
    const next = engine().id === 'otomate' && !dry;
    if (next) actions.append(actionButton('button primary', text('patch.nextRepack'), () => openTool('cpk-repack')));
    for (const action of successActions()) {
      const button = actionButton(action === 'open-folder' && !next ? 'button primary' : 'button',
        text(action === 'open-folder' ? 'patch.open' : 'patch.another'), () => action === 'open-folder' ? window.vees.openOutput() : chooseSheet());
      button.dataset.action = action;
      actions.append(button);
    }
  }
  renderPatchOptions();
  updatePatchReady();
  checkPatchMissing();
}
// Lines too wide for their box, with their text: held back by default, written when allowed.
function renderOverflow() {
  const box = $('patch-overflow');
  const rows = patchResult.overflow || [];
  box.classList.toggle('hidden', !rows.length);
  box.replaceChildren();
  if (!rows.length) return;
  const list = elt('ul', 'overflow-lines');
  for (const row of overflowRows(rows).slice(0, 5)) list.append(rowItem(row));
  const body = elt('div', 'untranslated-body');
  body.append(elt('strong', '', text(patchResult.allowOverflow ? 'patch.overflowWritten' : 'patch.overflowHeld', {count: rows.length})), list);
  const actions = elt('div', 'untranslated-actions');
  actions.append(actionButton('button primary', text('patch.viewAll', {count: rows.length}),
    () => showRows(text('patch.overflowTitle'), overflowRows(rows))));
  actions.append(actionButton('button', text('patch.openOverflow'), async () => {
    const error = await window.vees.openOverflow();
    if (error) showPatchError(error);
  }));
  body.append(actions);
  box.append(body);
}
// Overflow rows as list rows: where, by how much, and the line with #n as a visible break.
function overflowRows(rows) {
  return rows.map(row => ({sheet: row.sheet, id: row.id, copy: row.id,
    detail: text('patch.overflowBy', {units: row.over}), text: row.text.replace(/#n/g, ' ⏎ ')}));
}
function rowItem(row) {
  const item = elt('li');
  const where = elt('div', 'overflow-where');
  where.append(elt('span', 'mono', `${row.sheet} · ${row.id}`));
  if (row.detail) where.append(elt('span', '', row.detail));
  item.append(where, elt('div', 'overflow-text', row.text));
  return item;
}
// Every row of a list in a dialog, with a filter and a copy button per row.
function showRows(title, rows) {
  dialogContent(title, body => {
    const filter = elt('input', 'rows-filter');
    filter.type = 'search'; filter.placeholder = text('rows.filter');
    const count = elt('div', 'pick-hint');
    const list = elt('ul', 'overflow-lines rows-list');
    const items = rows.map(row => {
      const item = rowItem(row);
      const copy = actionButton('button rows-copy', text('rows.copy'), async () => {
        try { await navigator.clipboard.writeText(row.copy); copy.textContent = text('rows.copied'); }
        catch (error) { copy.textContent = error.message; }
        setTimeout(() => {copy.textContent = text('rows.copy');}, 1500);
      });
      item.querySelector('.overflow-where').append(copy);
      item.dataset.search = `${row.sheet} ${row.id} ${row.text}`.toLowerCase();
      list.append(item);
      return item;
    });
    const update = () => {
      const wanted = filter.value.trim().toLowerCase();
      let shown = 0;
      for (const item of items) {
        const match = !wanted || item.dataset.search.includes(wanted);
        item.classList.toggle('hidden', !match);
        shown += match;
      }
      count.textContent = text('rows.count', {shown, total: rows.length});
    };
    filter.addEventListener('input', update);
    update();
    body.append(filter, count, list);
    setTimeout(() => filter.focus(), 0);
  }, true);
}
// Rows the sheet leaves untranslated: the patch went ahead, they stay in English.
function renderUntranslated() {
  const box = $('patch-untranslated');
  box.classList.toggle('hidden', !patchUntranslated.length);
  box.replaceChildren();
  if (!patchUntranslated.length) return;
  const bySheet = new Map();
  for (const row of patchUntranslated) bySheet.set(row.sheet, (bySheet.get(row.sheet) || 0) + 1);
  const sheets = [...bySheet].sort((a, b) => b[1] - a[1]);
  const list = elt('ul', 'untranslated-sheets');
  for (const [sheet, count] of sheets.slice(0, 5)) list.append(elt('li', '', text('patch.untranslatedSheet', {sheet, count})));
  if (sheets.length > 5) list.append(elt('li', '', text('patch.untranslatedMore', {count: sheets.length - 5})));
  const saved = elt('span', 'untranslated-saved');
  const save = actionButton('button', text('patch.exportUntranslated'), async () => {
    try {
      const file = await window.vees.exportUntranslated(patchUntranslated);
      if (file) saved.textContent = text('patch.exported', {path: file});
    } catch (error) {showPatchError(error.message);}
  });
  const actions = elt('div', 'untranslated-actions');
  const rows = patchUntranslated.map(row => ({sheet: row.sheet, id: text('rows.row', {row: row.row}), copy: String(row.row), text: row.source || ''}));
  actions.append(actionButton('button primary', text('patch.viewAll', {count: rows.length}),
    () => showRows(text('patch.untranslatedTitle'), rows)), save, saved);
  const body = elt('div', 'untranslated-body');
  body.append(elt('strong', '', text('patch.untranslated', {count: patchUntranslated.length})), list, actions);
  box.append(body);
}
function renderMeasure() {
  breadcrumbs($('measure-breadcrumb'), [engine().name]);
  showValue($('measure-file'), measure.image?.path || '', 'measure.noImage');
  if ($('measure-text').value !== measure.text) $('measure-text').value = measure.text;
  fillSelect($('measure-font'), Object.entries(MEASURE_FONTS).map(([value, n]) => [value, text('measure.fontOption', {n})]), measure.font);
  fillSelect($('measure-screen'), MEASURE_SCREENS.map(value => [value, text(`measure.screen.${value}`)]), measure.screen);
  $('measure-stage').classList.toggle('hidden', !measure.image);
  if (!measure.image) {
    $('measure-result').classList.add('hidden');
    $('measure-img')?.remove();
    return;
  }
  const img = ensureMeasureImage();
  if (img.dataset.src !== measure.image.path) {img.src = measure.image.dataUrl; img.dataset.src = measure.image.path;}
  $('measure-canvas').classList.toggle('zoomed', measure.zoomed);
  $('measure-zoom').textContent = text(measure.zoomed ? 'measure.zoomOut' : 'measure.zoomIn');
  const next = MEASURE_POINTS[measure.points.length];
  $('measure-instruction').textContent = text(next ? `measure.click.${next}` : 'measure.click.done');
  $('measure-step-mark').textContent = next ? String(measure.points.length + 1) : '✓';
  $('measure-step-mark').classList.toggle('done', !next);
  renderMeasureMarks();
  renderMeasureResult();
}
// What windows.json already holds for this project, one row per screen.
async function loadMeasureSaved() {
  try { measure.saved = await window.vees.measureSaved(); } catch { measure.saved = {}; }
  if (page === 'measure') {renderMeasureSaved(); renderMeasureResult();}
}
function renderMeasureSaved() {
  const box = $('measure-saved');
  const screens = MEASURE_SCREENS;
  const any = screens.some(screen => measure.saved[screen]);
  box.classList.toggle('hidden', !any);
  box.replaceChildren();
  if (!any) return;
  const table = elt('table');
  const head = elt('tr');
  for (const key of ['screen', 'width', 'font', 'when']) head.append(elt('th', '', text(`measure.col.${key}`)));
  table.append(head);
  for (const screen of screens) {
    const saved = measure.saved[screen];
    const row = elt('tr');
    row.append(elt('td', '', text(`measure.screen.${screen}`)));
    if (saved) {
      row.append(elt('td', 'number', String(saved.ceiling)),
        elt('td', 'muted', MEASURE_FONTS[saved.font] ? text('measure.fontOption', {n: MEASURE_FONTS[saved.font]}) : saved.font),
        elt('td', 'muted', measuredWhen(saved.measuredAt)));
    } else {
      const empty = elt('td', 'muted', text('measure.notMeasured'));
      empty.colSpan = 3;
      row.append(empty);
    }
    table.append(row);
  }
  box.append(elt('h2', '', text('measure.savedTitle')), elt('div', 'pick-hint', text('measure.savedHint')), table);
}
async function saveMeasurement(ceiling) {
  const [start, end, edge] = measure.points;
  try {
    measure.saved = await window.vees.measureSave(measure.screen, {
      ceiling, font: measure.font, fontFile: measure.widths.font, line: measure.widths.line,
      lineUnits: measure.widths.widths[measure.font], pixels: {start, end, edge}, image: measure.image.path});
    measure.justSaved = measure.screen;
  } catch (error) {
    measure.error = error.message.replace(/^Error invoking remote method '[^']+': (Error: )?/, '');
  }
  renderMeasureSaved();
  renderMeasureResult();
}
function fillSelect(select, options, value) {
  select.replaceChildren(...options.map(([optionValue, label]) => {
    const option = elt('option', '', label);
    option.value = optionValue;
    return option;
  }));
  select.value = value;
}
// Vertical lines at each clicked x, and dashed spans for the line and the box.
function ensureMeasureImage() {
  let img = $('measure-img');
  if (!img) {
    img = document.createElement('img');
    img.id = 'measure-img';
    img.addEventListener('click', measureClick);
    img.addEventListener('load', renderMeasureMarks);
    $('measure-frame').prepend(img);
  }
  const name = measure.image?.path?.split(/[\\/]/).pop();
  img.alt = name || text('measure.image');
  return img;
}
function renderMeasureMarks() {
  const marks = $('measure-marks');
  const img = $('measure-img');
  marks.replaceChildren();
  const width = img?.naturalWidth;
  if (!width) return;
  const at = x => `${(x / width) * 100}%`;
  measure.points.forEach((x, index) => {
    const mark = elt('div', `measure-mark ${MEASURE_POINTS[index]}`);
    mark.style.left = at(x);
    mark.append(elt('span', '', text(`measure.mark.${MEASURE_POINTS[index]}`)));
    marks.append(mark);
  });
  const [start, end, edge] = measure.points;
  for (const [cls, to] of [['line', end], ['box', edge]]) {
    if (start === undefined || to === undefined) continue;
    const span = elt('div', `measure-span ${cls}`);
    span.style.left = at(Math.min(start, to));
    span.style.width = `${(Math.abs(to - start) / width) * 100}%`;
    marks.append(span);
  }
}
async function measureWidths() {
  const wanted = measure.text.trim();
  if (!wanted || (measure.widthsFor === wanted && measure.widths) || measure.busy) return;
  measure.busy = true; measure.error = '';
  renderMeasureResult();
  try {
    measure.widths = await window.vees.measureLine(wanted);
    measure.widthsFor = wanted;
  } catch (error) {
    measure.widths = null; measure.widthsFor = '';
    measure.error = error.message.replace(/^Error invoking remote method '[^']+': (Error: )?/, '');
  }
  measure.busy = false;
  if (page === 'measure') renderMeasureResult();
  // The text may have changed while the fonts were being read.
  if (measure.text.trim() !== wanted) measureWidths();
}
// Box width in font units = (edge - start) / (pixels per unit), the scale read off the line.
function renderMeasureResult() {
  const box = $('measure-result');
  box.replaceChildren();
  box.className = '';
  if (!measure.image || measure.points.length < 3) {box.classList.add('hidden'); return;}
  const say = (cls, message) => {box.className = `notice ${cls}`; box.append(elt('div', '', message));};
  if (!measure.text.trim()) return say('', text('measure.needText'));
  if (measure.busy) return say('hint', text('measure.working'));
  if (measure.error) return say('missing', text('measure.failed', {message: measure.error}));
  if (!measure.widths) {measureWidths(); return say('hint', text('measure.working'));}
  const [start, end, edge] = measure.points;
  if (!(end > start && edge > end)) return say('missing', text('measure.order'));
  const units = measure.widths.widths[measure.font];
  const pixels = end - start;
  const scale = pixels / units;
  const ceiling = Math.round((edge - start) / scale);
  box.className = 'done-card';
  const details = elt('ul', 'measure-details');
  details.append(
    elt('li', '', text('measure.lineUnits', {units, font: text('measure.fontOption', {n: MEASURE_FONTS[measure.font]}), pixels: Math.round(pixels)})),
    elt('li', '', text('measure.scale', {scale: scale.toFixed(4), edge: Math.round(edge - start)})));
  if (measure.widths.lines > 1) details.append(elt('li', '', text('measure.lines', {count: measure.widths.lines})));
  box.append(elt('div', 'measure-number', text('measure.result', {ceiling})), details);
  const screenName = text(`measure.screen.${measure.screen}`);
  const current = measure.saved[measure.screen];
  const saveRow = elt('div', 'measure-save-row');
  if (measure.justSaved === measure.screen && current?.ceiling === ceiling) {
    saveRow.append(elt('strong', '', text('measure.saved', {screen: screenName, ceiling})));
  } else {
    saveRow.append(actionButton('button primary', current ? text('measure.replace', {value: current.ceiling, screen: screenName})
      : text('measure.save', {screen: screenName}), () => saveMeasurement(ceiling)));
  }
  saveRow.append(elt('span', 'pick-hint', text('measure.saveHint')));
  box.append(saveRow);
  if (measure.widths.stock) {
    const warn = elt('div', 'notice');
    warn.append(elt('div', '', text('measure.stock')));
    box.append(warn);
  }
}
// A date when the file holds one, else what it says ("probe build" for numbers measured that way).
function measuredWhen(value) {
  const date = new Date(value);
  return value && !Number.isNaN(date.getTime()) ? date.toLocaleString(language() === 'vi' ? 'vi-VN' : 'en-GB') : (value || '');
}
async function chooseMeasureImage() {
  try {
    const image = await window.vees.chooseImage();
    if (!image) return;
    measure.image = image;
    measure.points = [];
    renderMeasure();
  } catch (error) {showError(error.message);}
}
function measureClick(event) {
  measure.justSaved = '';
  if (measure.points.length >= MEASURE_POINTS.length) return;
  const img = $('measure-img');
  const rect = img.getBoundingClientRect();
  // Clicks land on the scaled image; keep positions in the screenshot's own pixels.
  measure.points.push((event.clientX - rect.left) * img.naturalWidth / rect.width);
  renderMeasure();
}
// The advanced options, built from PATCH_OPTIONS and saved as they change.
function renderPatchOptions(force = false) {
  const box = $('patch-options');
  const options = patchState().options || {};
  const spec = PATCH_OPTIONS[engine().id] || [];
  const on = spec.filter(([key, kind]) => kind === 'bool' ? options[key] : kind === 'number' ? options[key] > 0
    : Array.isArray(kind) ? options[key] && options[key] !== kind[0] : String(options[key] || '').trim()).length;
  $('patch-advanced-count').textContent = on ? text('patch.advancedOn', {count: on}) : '';
  if (!force && box.contains(document.activeElement)) return;   // keep the field being typed in
  if (patchSheets.path !== patchState().sheetPath) loadSheetNames();
  box.replaceChildren();
  for (const [key, kind] of spec) {
    const id = `patch-opt-${key}`;
    const label = elt('label', '', text(`patch.opt.${key}`));
    label.htmlFor = id;
    if (kind === 'sheets' || kind === 'sheet') {
      const field = elt('div', `field ${kind === 'sheets' ? 'wide' : ''}`);
      field.append(label, sheetPicker(key, kind, options[key] || '', id), elt('div', 'help', text(`patch.opt.${key}.hint`)));
      box.append(field);
      continue;
    }
    let input;
    if (kind === 'bool') {
      input = elt('input'); input.type = 'checkbox'; input.checked = !!options[key];
    } else if (Array.isArray(kind)) {
      input = elt('select');
      for (const choice of kind) {const option = elt('option', '', choice); option.value = choice; input.append(option);}
      input.value = options[key] || kind[0];
    } else {
      input = elt(kind === 'lines' ? 'textarea' : 'input');
      if (kind !== 'lines') input.type = kind === 'number' ? 'number' : 'text';
      if (kind === 'number') input.min = '0';
      input.value = kind === 'number' ? (options[key] || '') : (options[key] || '');
    }
    input.id = id;
    input.addEventListener('change', () => savePatchOption(key, kind === 'bool' ? input.checked : input.value));
    const field = elt('div', `field ${kind === 'bool' ? 'toggle-field' : ''} ${kind === 'lines' ? 'wide' : ''}`);
    const help = elt('div', 'help', text(`patch.opt.${key}.hint`));
    if (kind === 'bool') {const words = elt('div'); words.append(label, help); field.append(input, words);}
    else field.append(label, input, help);
    box.append(field);
  }
}
// The worksheet names of the chosen workbook, fetched when the file changes.
async function loadSheetNames() {
  const file = patchState().sheetPath;
  if (patchSheets.path === file) return;
  patchSheets = {path: file, names: null, error: ''};
  if (!isXlsx(file)) return;
  try { patchSheets.names = await window.vees.sheetNames(); }
  catch (error) { patchSheets.error = error.message.replace(/^Error invoking remote method '[^']+': (Error: )?/, ''); }
  if (page === 'patch' && patchState().sheetPath === file) renderPatchOptions(true);
}
// Ticks for 'sheets' (several, Otomate) or a list for 'sheet' (one, Unity).
function sheetPicker(key, kind, value, id) {
  if (!isXlsx(patchState().sheetPath)) return elt('div', 'sheet-empty', text('sheets.needFile'));
  if (patchSheets.error) return elt('div', 'sheet-empty', text('sheets.failed', {message: patchSheets.error}));
  if (!patchSheets.names) {loadSheetNames(); return elt('div', 'sheet-empty', text('sheets.loading'));}
  if (kind === 'sheet') {
    const select = elt('select');
    select.id = id;
    for (const [optionValue, label] of [['', text('sheets.first')], ...patchSheets.names.map(name => [name, name])]) {
      const option = elt('option', '', label); option.value = optionValue; select.append(option);
    }
    select.value = patchSheets.names.includes(value) ? value : '';
    select.addEventListener('change', () => savePatchOption(key, select.value));
    return select;
  }
  // applyvi patches only the numbered worksheets, so only those are offered.
  const names = patchSheets.names.filter(name => /^\d+$/.test(name));
  const ticked = new Set(value.split(/[\n,]/).map(name => name.trim()).filter(name => names.includes(name)));
  const picker = elt('div', 'sheet-picker');
  const tools = elt('div', 'sheet-tools');
  const filter = elt('input');
  filter.type = 'search'; filter.id = id; filter.placeholder = text('sheets.filter');
  const count = elt('span', 'sheet-count');
  const grid = elt('div', 'sheet-grid');
  const boxes = names.map(name => {
    const row = elt('label');
    const tick = elt('input'); tick.type = 'checkbox'; tick.checked = ticked.has(name); tick.value = name;
    row.append(tick, elt('span', '', name));
    grid.append(row);
    return tick;
  });
  const save = () => {
    const chosen = boxes.filter(tick => tick.checked).map(tick => tick.value);
    count.textContent = chosen.length ? text('sheets.count', {n: chosen.length, total: names.length}) : text('sheets.allNote', {total: names.length});
    savePatchOption(key, chosen.join(', '));
  };
  for (const tick of boxes) tick.addEventListener('change', save);
  filter.addEventListener('input', () => {
    const wanted = filter.value.trim();
    for (const tick of boxes) tick.parentElement.classList.toggle('hidden', !!wanted && !tick.value.includes(wanted));
  });
  // Select all ticks only what the filter shows, so a filter then Select all picks a group.
  const all = actionButton('button', text('sheets.all'), () => {for (const tick of boxes) if (!tick.parentElement.classList.contains('hidden')) tick.checked = true; save();});
  const none = actionButton('button', text('sheets.clear'), () => {for (const tick of boxes) tick.checked = false; save();});
  count.textContent = ticked.size ? text('sheets.count', {n: ticked.size, total: names.length}) : text('sheets.allNote', {total: names.length});
  tools.append(filter, all, none, count);
  picker.append(tools, grid);
  return picker;
}
async function savePatchOption(key, value) {
  const options = {...(patchState().options || {}), [key]: value};
  const saved = await window.vees.setPatch({options});
  state.settings = saved.settings;
  renderPatchOptions();
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
// Make game font: a row per stock .ffu, each with the TTF/OTF to render it from.
function renderFonts() {
  const unpack = tools().find(item => item.id === 'cpk-unpack');
  $('fonts-unpack').classList.toggle('hidden', !unpack || fontPage.templates.length > 0);
  if (unpack) $('fonts-unpack-tool').textContent = toolText(unpack, 'title');
  const list = fontPage.templates;
  showValue($('fonts-stock-value'), list.length ? text('fonts.ffuCount', {count: list.length}) : '', 'fonts.noFfu');
  $('fonts-stock-value').title = list.map(item => item.path).join('\n');
  const table = $('fonts-table');
  table.replaceChildren();
  table.classList.toggle('hidden', !list.length);
  for (const item of list) table.append(fontRow(item));
  showValue($('fonts-output-value'), fontPage.output, 'patch.noOutput');
  $('fonts-pick-ffu').disabled = running;
  $('fonts-pick-output').disabled = running;
  updateFontsReady();
  renderFontsResult();
}
function fontRow(item) {
  const row = elt('div', 'font-row');
  const about = elt('div');
  const role = item.info?.error ? text('fonts.notFfu')
    : [text(`fonts.role.${fontRole(item.path) || 'other'}`), item.info ? text('fonts.cell', {cell: item.info.cell}) : ''].filter(Boolean).join(' · ');
  about.append(elt('div', 'font-name mono', baseName(item.path)), elt('div', 'font-role', role));
  // The first font is the main one; the others draw what it lacks, in order.
  const chain = elt('div', 'font-chain');
  const slots = item.fonts.length ? item.fonts : [null];
  slots.forEach((font, index) => {
    const pick = elt('div', 'pick-row');
    const value = elt('div', 'pick-value mono');
    showValue(value, font?.path || '', 'fonts.noFont');
    if (index) value.prepend(elt('span', 'font-fallback', text('fonts.fallback')));
    pick.append(value);
    if (!index) {
      const choose = actionButton('button', text('fonts.pickFont'), () => chooseSourceFont(item, 0));
      choose.disabled = running || !!item.info?.error;
      pick.append(choose);
    }
    if (font) {
      const clear = actionButton('button', text('fonts.clear'), () => {item.fonts.splice(index, 1); fontPage.result = null; renderFonts();});
      clear.disabled = running;
      pick.append(clear);
    }
    chain.append(pick);
  });
  if (item.fonts.length) {
    const add = actionButton('link-button', text('fonts.addFallback'), () => chooseSourceFont(item, item.fonts.length));
    add.disabled = running;
    chain.append(add);
  }
  row.append(about, chain);
  if (item.fonts.length) row.append(fontStatus(item));
  return row;
}
function fontStatus(item) {
  const fonts = item.fonts;
  if (fonts.some(font => font.coverage?.error)) return elt('div', 'font-status bad', text('fonts.notFont'));
  const missing = chainMissing(fonts);
  if (missing === null) return elt('div', 'font-status', text('fonts.checking'));
  const names = fonts.map(font => font.coverage.name).join(' + ');
  const total = fonts[0].coverage.total;
  if (!missing) return elt('div', 'font-status good', text('fonts.coverageOk', {font: names, total}));
  return elt('div', 'font-status bad', text('fonts.coverageMissing',
    {font: names, count: [...missing].length, total, chars: [...missing].join(' ')}));
}
async function chooseStockFonts() {
  try {
    const first = fontPage.templates[0]?.path || '';
    const files = (await window.vees.chooseFfu(first)).sort((a, b) => baseName(a).localeCompare(baseName(b)));
    if (!files.length) return;
    const infos = await window.vees.ffuInfo(files);
    // Choosing again keeps the fonts already picked for files that are still there.
    const before = new Map(fontPage.templates.map(item => [item.path, item]));
    fontPage.templates = files.map((file, index) => ({path: file, info: infos[index], fonts: before.get(file)?.fonts || []}));
    if (!fontPage.outputChosen) fontPage.output = defaultOutput(files);
    fontPage.result = null;
    renderFonts();
  } catch (error) {showFontsError(error.message);}
}
// Puts a font at `index` in the row's chain: 0 replaces the main font, the
// chain's length adds a fallback.
async function chooseSourceFont(item, index) {
  try {
    const last = item.fonts[index]?.path || fontPage.templates.flatMap(other => other.fonts).pop()?.path || '';
    const selected = await window.vees.choosePath('file', last, [{name: 'Fonts (TTF, OTF)', extensions: ['ttf', 'otf', 'ttc']}]);
    if (!selected) return;
    const font = {path: selected, coverage: null};
    item.fonts[index] = font;
    fontPage.result = null;
    renderFonts();
    try { font.coverage = await window.vees.fontInfo(selected); } catch (error) { font.coverage = {error: 'not-font', message: error.message}; }
    renderFonts();
  } catch (error) {showFontsError(error.message);}
}
async function chooseFontsOutput() {
  try {
    const selected = await window.vees.choosePath('dir', fontPage.output, []);
    if (!selected) return;
    fontPage.output = selected;
    fontPage.outputChosen = true;
    fontPage.result = null;
    renderFonts();
  } catch (error) {showFontsError(error.message);}
}
function updateFontsReady() {
  const problem = fontJobProblem(fontPage.templates, fontPage.output);
  const count = fontPage.templates.filter(item => item.fonts.length).length;
  $('fonts-ready').textContent = running ? text('fonts.working') : text(problem ? 'fonts.notReady' : 'fonts.ready', {count});
  $('fonts-ready-dot').className = `dot${problem || running ? '' : ' ready'}`;
  $('fonts-reason').textContent = problem && !running ? text(`fonts.need.${problem}`) : '';
  $('fonts-run').disabled = running || !!problem;
  $('fonts-stop').disabled = !running;
}
function pathText(file) {
  const node = elt('span', 'mono');
  for (const part of String(file).split(/([\\/])/)) {
    node.append(part);
    if (part === '/' || part === '\\') node.append(document.createElement('wbr'));
  }
  return node;
}
function revealButton(target, onError, className = 'button') {
  const button = actionButton(className, '', async () => {
    try {
      const error = await window.vees.revealPath(target);
      if (error) onError(error);
    } catch (error) { onError(error.message); }
  });
  const showKey = state.platform === 'darwin' ? 'run.show.darwin' : state.platform === 'win32' ? 'run.show.win32' : 'run.show';
  button.append(icon('folder'), elt('bdi', '', text(showKey)));
  return button;
}
function renderRunReveal() {
  const box = $('run-reveal');
  const current = tool();
  const show = !!(runReveal && current && runReveal.id === current.id && !running);
  box.classList.toggle('hidden', !show);
  box.replaceChildren();
  if (!show) return;
  const body = elt('div', 'hint-body');
  if (runReveal.path) {
    const words = elt('span');
    words.append(elt('strong', '', text('run.saved')), pathText(runReveal.path));
    body.append(words, revealButton(runReveal.path, showError, runReveal.next ? 'button' : 'button primary'));
  }
  const next = runReveal.next && tools().find(item => item.id === runReveal.next);
  if (next) body.append(actionButton('button primary', text('run.next', {tool: toolText(next, 'title')}), () => openTool(next.id)));
  box.append(body);
}
function showFontsError(message) {
  fontPage.result = {error: message};
  renderFontsResult();
}
function renderFontsResult() {
  const box = $('fonts-result');
  const result = fontPage.result;
  box.replaceChildren();
  box.className = 'notice hidden';
  if (!result) return;
  if (result.error || result.failed) {
    box.className = 'notice missing';
    box.append(elt('span', '', result.error || text('fonts.failed', {file: result.failed})));
  } else if (result.signal) {
    box.className = 'notice';
    box.append(elt('span', '', text('fonts.stopped')));
  } else {
    box.className = 'notice done';
    const body = elt('div', 'hint-body');
    body.append(elt('span', '', text('fonts.done', {files: result.made.join(', ')})));
    if (result.output) body.append(revealButton(result.output, showError));
    const repack = tools().find(item => item.id === 'cpk-repack');
    if (repack) {
      const open = actionButton('button', '', () => openToolWith('cpk-repack',
        {archive: result.repack.archive, 'output CPK': result.repack.output, 'replacement folder': result.repack.folder}, true));
      open.append(elt('bdi', '', toolText(repack, 'title')), icon('arrow'));
      body.append(open);
    }
    box.append(body);
  }
}
async function startFonts() {
  if (running) return;
  fontPage.result = null;
  // The advanced settings, kept like any tool's values so they survive a restart.
  captureValues();
  const options = Object.fromEntries(Object.entries(formValues[FONT_TOOL] || {}).filter(([name]) => !MAPPED_ARGS.includes(name)));
  try {
    const reply = await window.vees.runFonts(fontPage.templates.map(item => ({template: item.path, fonts: item.fonts.map(font => font.path)})),
      fontPage.output, options);
    if (reply?.problem) showFontsError(text(`fonts.need.${reply.problem}`));
  } catch (error) {showFontsError(error.message);}
}
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
  if (page === 'measure') {
    if (!measureAfter[engine().id]) {page = 'form'; selectDefault(); return render();}
    renderMeasure();
    loadMeasureSaved();
  }
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
function dialogContent(title, build, wide = false) {
  $('info-dialog').classList.toggle('wide', wide);
  $('dialog-title').textContent = title;
  const body = $('dialog-body');body.replaceChildren();build(body);
  if (!$('info-dialog').open) $('info-dialog').showModal();
}
function paragraph(parent, text, cls = '') {parent.append(elt('p',cls,text));}
function action(parent, label, callback) {const b=elt('button','',label); b.type='button';b.addEventListener('click', callback);parent.append(b);}
async function showDocs() {
  try {
    const error = await window.vees.openDocumentation(language());
    if (error) showError(error);
  } catch (error) { showError(error.message); }
}
// The names pip installs, for the modules whose import name differs.
const PIP_NAMES = {PIL: 'Pillow', Crypto: 'pycryptodome', fontTools: 'fonttools'};
// Three cases, each with its own fix first: no Python that starts (install it),
// Python without the engine's packages (the app sets them up), or all ready.
function showPython() {
  const check = pythonCheck || {ok: false, found: false, missing: [], message: ''};
  if (!check.ok) pythonPrompted.add(state.settings.engine);
  const title = check.ok ? text('rail.python') : text(check.found ? 'python.packagesTitle' : 'python.missingTitle');
  dialogContent(title, body => {
    const actions = elt('div', 'dialog-actions');
    const add = (label, onClick, className = 'button') => {
      const node = elt('button', className, label);
      node.type = 'button';
      node.addEventListener('click', onClick);
      actions.append(node);
    };
    if (!check.found && !check.ok) {
      paragraph(body, text('python.notFound', {engine: engine().name, path: state.settings.python}));
      if (check.message) paragraph(body, check.message.split(/\r?\n/).filter(Boolean).slice(-2).join('\n'), 'mono python-error');
      paragraph(body, text('python.install'));
      add(text('python.download'), () => window.vees.openPythonDownload(), 'button primary');
      add(text('python.recheck'), recheckPython);
      add(text('python.choose'), choosePython);
    } else if (!check.ok) {
      paragraph(body, text('python.missingPackages', {engine: engine().name, version: check.version,
        packages: check.missing.map(name => PIP_NAMES[name] || name).join(', ')}));
      paragraph(body, text('python.setupHow'));
      add(text('python.setup'), setupPython, 'button primary');
      add(text('python.choose'), choosePython);
    } else {
      paragraph(body, text('python.readyBody', {engine: engine().name, version: check.version}));
      paragraph(body, text('python.current', {path: state.settings.python}), 'mono');
      add(text('python.reinstall'), setupPython);
      add(text('python.choose'), choosePython);
    }
    if (!check.ok) add(text('update.later'), () => $('info-dialog').close(), 'button quiet');
    body.append(actions);
  });
  $('info-dialog').querySelector('.dialog-actions .primary')?.focus();
}
async function setupPython() {
  try {await window.vees.setupPython();$('info-dialog').close();}
  catch(error){showError(error.message);}
}
async function choosePython() {
  try {
    const result = await window.vees.choosePython();
    if (!result) return;
    state.settings.python = result.python;
    updatePython(result.check);
    if (result.check.ok) $('info-dialog').close(); else showPython();
  } catch(error){showError(error.message);}
}
async function recheckPython() {
  try {
    updatePython(await window.vees.checkPython());
    if (pythonCheck.ok) $('info-dialog').close(); else showPython();
  } catch(error){showError(error.message);}
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
  $('language-menu').addEventListener('keydown', event => {
    const items = [...$('language-menu').querySelectorAll('[role=menuitemradio]')];
    const index = items.indexOf(document.activeElement);
    if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp' && event.key !== 'Home' && event.key !== 'End') return;
    event.preventDefault();
    const next = event.key === 'ArrowDown' ? (index + 1) % items.length
      : event.key === 'ArrowUp' ? (index - 1 + items.length) % items.length
      : event.key === 'Home' ? 0 : items.length - 1;
    items[next]?.focus();
  });
  $('settings-button').addEventListener('click', () => toggleSettingsMenu());
  $('python-button').addEventListener('click', () => toggleSettingsMenu(false));
  $('check-updates').addEventListener('click', () => toggleSettingsMenu(false));
  document.addEventListener('click', event => {
    if (!$('language-switcher').contains(event.target)) toggleLanguageMenu(false);
    if (!$('settings-switcher').contains(event.target)) toggleSettingsMenu(false);
  });
  document.addEventListener('keydown', event => {if (event.key === 'Escape') {toggleLanguageMenu(false); toggleSettingsMenu(false);}});
  window.addEventListener('resize', () => {
    if (!$('language-menu').classList.contains('hidden')) placeLanguageMenu();
    if (!$('settings-menu').classList.contains('hidden')) placeSettingsMenu();
  });
  document.querySelector('.sidebar').addEventListener('scroll', () => {
    if (!$('language-menu').classList.contains('hidden')) placeLanguageMenu();
    if (!$('settings-menu').classList.contains('hidden')) placeSettingsMenu();
  }, {passive: true});
  $('theme-toggle').addEventListener('click', toggleTheme);
  bindSidebarResize();
  $('measure-pick').addEventListener('click', chooseMeasureImage);
  $('measure-redo').addEventListener('click', () => {measure.points = []; measure.justSaved = ''; renderMeasure();});
  $('measure-zoom').addEventListener('click', () => {measure.zoomed = !measure.zoomed; renderMeasure();});
  $('measure-text').addEventListener('input', event => {measure.text = event.target.value; renderMeasureResult();});
  $('measure-font').addEventListener('change', event => {measure.font = event.target.value; renderMeasureResult();});
  $('measure-screen').addEventListener('change', event => {measure.screen = event.target.value; measure.justSaved = ''; renderMeasureResult();});
  $('patch-done-measure-open').addEventListener('click', () => showPage('measure'));
  $('patch-titles-open').addEventListener('click', () => openTool('filltitles-prefixes'));
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
  $('python-status').addEventListener('click',showPython);
  $('dialog-close').addEventListener('click',()=>$('info-dialog').close());
  $('clear-log').addEventListener('click',()=>setLog(''));
  $('tool-form').addEventListener('submit',event=>event.preventDefault());
  $('fonts-unpack-open').addEventListener('click', () => openToolWith('cpk-unpack', {filter: 'font'}));
  $('fonts-pick-ffu').addEventListener('click', chooseStockFonts);
  $('fonts-pick-output').addEventListener('click', chooseFontsOutput);
  $('fonts-run').addEventListener('click', startFonts);
  $('fonts-stop').addEventListener('click', () => window.vees.cancel());
  $('run-button').addEventListener('click',async()=>{
    if(running)return;
    captureValues();
    const current = tool();
    const values = {...formValues[current.id]};
    applyOffer = null;
    const flag = confirmFlag(current);
    if (flag) {delete values[flag]; applyOffer = {id: current.id, values, output: '', flag};}
    try {
      runRequest = {id: current.id, values};
      await window.vees.run(current.id,values);
    } catch(error){applyOffer = null; runRequest = null; showError(error.message);}
  });
  $('cancel-button').addEventListener('click',async()=>{await window.vees.cancel();});
  window.vees.on('run-start',event=>{
    running=true;runReveal=null;render();setLog(`$ ${event.command.map(x=>/\s/.test(String(x))&&/\s/.test(x)?JSON.stringify(x):x).join(' ')}\n\n`);
    if (event.id === 'patch') {$('patch-log').textContent = ''; patchStage = 'working'; patchPhase = 0;}
    status('status.running','running');
    render();
  });
  window.vees.on('run-output',event=>{
    setLog(currentLog+event.text);
    if (applyOffer) applyOffer.output += event.text;
    if (page === 'patch') {
      $('patch-log').textContent += event.text;
      $('patch-log-card').classList.remove('hidden');
      const phase = String(event.text).match(/^(prepare|check|create):/m);
      if (phase) {patchPhase = PHASES.indexOf(phase[1]); renderTasks();}
    }
  });
  window.vees.on('run-end',async event=>{
    running=false;const ok=event.code===0;
    setLog(`${currentLog}\n${ok?text('log.success'):event.signal?text('status.stopped'):text('log.exit', {code: event.code})}\n`);
    status(ok?'status.complete':event.signal?'status.stopped':'status.failed',ok?'success':'failed');
    // A run that held back and is about to ask has written nothing yet.
    const asking = !!(applyOffer && ok && !event.id && applyOffer.output.includes(applyOffer.flag));
    if (!event.id && !asking) {
      const current = tool();
      const values = current && runRequest?.id === current.id ? runRequest.values : {};
      const target = ok && current ? outputTarget(current, values) : '';
      let kind = '';
      try { kind = target ? await window.vees.pathKind(target) : ''; } catch { kind = ''; }
      // The tool that follows this one gets its fields now, and a button to it.
      const next = ok && current ? tools().find(item => item.follows?.tool === current.id && handedOn(item, values)) : null;
      if (next) formValues[next.id] = {...(formValues[next.id] || state.settings.values[next.id] || {}), ...handedOn(next, values)};
      runReveal = (kind || next) && current ? {id: current.id, path: kind ? target : '', next: next?.id} : null;
    }
    if (event.id === 'patch') applyPatchResult(event);
    else {
      if (event.id === 'fonts') fontPage.result = event;
      render();
    }
    const offer = applyOffer;
    applyOffer = null;
    if (asking) offerApply(offer);
    window.vees.state().then(fresh=>{state.settings=fresh.settings;state.workspace=fresh.workspace;updatePython(fresh.python);}).catch(()=>{});
  });
  $('tour-button').addEventListener('click', tour.start);
  // A Python prompt opened above goes first; the tour waits until it is closed.
  whenNoDialog(() => tour.firstRun());
}
function chooseLanguage(next) {
  if (languageChange().workbookPath) return;
  window.vees.setLanguage(next).then(result => {state.settings = result.settings; render();});
}
async function chooseWorkspace() {
  try {
    const result = await window.vees.chooseWorkspace();
    // Every page reads the project folder: its missing files, its saved widths.
    if (result) {state.workspace = result.workspace;updatePython(result.python);render();}
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
  } else if (result.code === 0 && result.complete !== false && !result.error) {
    patchStage = 'done';
    patchUntranslated = result.untranslated || [];
    patchResult = result;
    showPatchError('');
  } else if (result.findings && result.findings.length) {
    patchStage = 'issues';
    const list = $('finding-list');
    list.replaceChildren();
    for (const finding of result.findings) list.append(elt('li', '', `${finding.sheet || ''} · ${finding.row}`));
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
start().catch(error=>{document.body.textContent=`Unable to start OTOME TRANSLATOR: ${error.message}`;});
