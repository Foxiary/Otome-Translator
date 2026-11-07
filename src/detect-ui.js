// Drop-a-game, the main way to pick the tools. Until an engine has been chosen
// once, the app opens on a start page that asks for the game; choosing the
// engine yourself sits under "Choose the engine yourself" for those who know
// it. Afterwards the sidebar names the engine in use, with the pickers and the
// full list folded under it; a game dropped anywhere on the window switches to
// its engine and fills the empty fields of its tools, and the sidebar card
// shows only to report what a drop found. The reading itself happens in the main process
// (detect-engine.js); everything here is the cards, the overlay and the switch.
// Loaded before renderer.js, so that the tour and the engine list are hooked
// before its start() runs: at load only the DOM is used; renderer.js's functions
// and state are reached later, from events.
(() => {
  const byId = id => document.getElementById(id);
  const cards = [byId('detect-card'), byId('start-detect')];
  const sideAdvanced = byId('engine-advanced');
  const startAdvanced = byId('start-advanced');
  let view = {kind: 'idle'};
  let started = false;

  const words = arg => `${arg.name} ${arg.help || ''}`;
  // Which of the files the main process found suits a field, by the field's own wording.
  const FILL_RULES = [
    ['nsp', arg => arg.kind === 'file' && /\bnsp\b/i.test(words(arg))],
    // Only fields that say they take an XCI: nsp.py of the rrlib engine reads NSPs alone.
    ['xci', arg => arg.kind === 'file' && /\bxci\b/i.test(words(arg))],
    ['memfs', arg => arg.kind === 'file' && (/^memfs$/i.test(arg.name) || /script\.memfs/i.test(arg.help || ''))],
    ['membody', arg => arg.kind === 'file' && /membody/i.test(words(arg))],
    ['exe', arg => arg.kind === 'file' && (/^(--exe|main)$/i.test(arg.name) || /exefs\/main/i.test(arg.help || ''))],
    ['mod', arg => arg.kind === 'dir' && /mod folder/i.test(arg.help || '')],
    ['jp', arg => arg.kind === 'dir' && /Japanese script\.memfs/i.test(arg.help || '')],
    ['tat', arg => arg.kind === 'file' && /\.tat\b/i.test(arg.help || '')],
    ['cpk', arg => ['file', 'path'].includes(arg.kind) && /\bcpk\b/i.test(words(arg))],
    ['assets', arg => arg.kind === 'file' && /bundle|\.assets/i.test(words(arg))]
  ];

  const known = id => !!id && state.engines.some(item => item.id === id);
  const engineName = id => state.engines.find(item => item.id === id)?.name || id;
  const baseName = input => input.split(/[\\/]/).filter(Boolean).pop() || input;
  const onStartPage = () => page === 'start';

  // ------------------------------------------------------------- choosing

  // The first-run tour explains the sidebar and the tools, which the start page
  // does not show yet: it waits for the first engine choice.
  const firstTour = tour.firstRun;
  let tourWaiting = false;
  tour.firstRun = () => {
    if (state && !state.settings.engineChosen) { tourWaiting = true; return; }
    firstTour();
  };

  async function markChosen() {
    if (!state.settings.engineChosen) {
      const saved = await window.vees.markEngineChosen();
      state.settings = saved.settings;
    }
    if (onStartPage()) { page = 'form'; selectDefault(); render(); }
    // Off the start page now: a Python that cannot run these tools is asked
    // about first, and the tour waits for that dialog to close.
    promptPython();
    if (tourWaiting) { tourWaiting = false; setTimeout(() => whenNoDialog(firstTour), 250); }
  }

  // For every tool of the engine, the fields a found file can fill. The tool to
  // open is the one with the most required fields filled; ties go to catalog order.
  function fillsFor(engineEntry, files) {
    const fills = [];
    for (const item of engineEntry.tools) {
      const values = {};
      let required = 0;
      for (const arg of item.args) {
        const rule = FILL_RULES.find(([key, test]) => files[key] && test(arg));
        if (!rule) continue;
        values[arg.name] = files[rule[0]];
        if (arg.required) required++;
      }
      if (Object.keys(values).length) fills.push({id: item.id, values, required});
    }
    return fills;
  }
  // Fill only what is empty, as openToolWith does: a field the user set keeps its value.
  function applyFills(result) {
    const fills = fillsFor(engine(), result.files || {});
    for (const {id, values} of fills) {
      const current = {...(formValues[id] || state.settings.values[id] || {})};
      for (const [name, value] of Object.entries(values)) {
        if (!String(current[name] ?? '').trim()) current[name] = value;
      }
      formValues[id] = current;
    }
    const best = [...fills].sort((a, b) => b.required - a.required)[0];
    if (best) openTool(best.id);
  }

  async function switchTo(result) {
    const before = state.settings.engine;
    if (before !== result.engine) {
      if (!canSwitchEngine(running)) return 'blocked';
      await switchEngine(result.engine);
      if (state.settings.engine !== result.engine) return 'blocked';
    }
    // On the start page the engine is only half the set-up: the project folder
    // comes next, and the tools open once it is settled.
    if (onStartPage()) projectStep(result);
    else { applyFills(result); await markChosen(); }
    return before === result.engine ? 'already' : 'switched';
  }

  async function chooseByHand(id) {
    if (id !== state.settings.engine) {
      await switchEngine(id);
      if (state.settings.engine !== id) return;
    }
    if (onStartPage()) projectStep(null);
    else await markChosen();
  }

  // Step two of the start page (project-ui.js), with what the drop told us.
  let pending = null;
  function projectStep(result) {
    pending = result;
    const container = result && ['nsp', 'xci'].includes(result.kind) ? result.input : null;
    window.otmProject.show({gameFile: container, modFolder: result?.files?.mod || null,
      gameName: result?.game || (result ? baseName(result.input) : '')});
  }
  window.otmStart = {
    // The project is settled (or put off): the tools open, their empty fields
    // pointing at the project first and at what was dropped otherwise.
    async finish(files) {
      const merged = {...(pending?.files || {}), ...files};
      pending = null;
      await markChosen();
      applyFills({files: merged});
    },
    back() { pending = null; view = {kind: 'idle'}; paint(); }
  };
  function openAdvanced() {
    const target = onStartPage() ? startAdvanced : sideAdvanced;
    target.open = true;
    target.querySelector('summary').focus();
  }

  // ------------------------------------------------------------- the cards

  function button(label, onClick, className = '') {
    const node = elt('button', className, label);
    node.type = 'button';
    node.addEventListener('click', onClick);
    return node;
  }
  function problemText(problem) {
    if (['keys', 'update', 'unsupported-container', 'missing'].includes(problem)) return text(`detect.problem.${problem}`);
    return text('detect.problem.other', {message: problem.replace(/^(nsp|xci): /, '')});
  }

  function paintIdle(card) {
    const head = elt('div', 'detect-head');
    head.append(icon('drop'));
    const copy = elt('div', 'detect-copy');
    copy.append(elt('div', 'detect-title', text('detect.drop')), elt('div', 'detect-hint', text('detect.dropHint')));
    head.append(copy);
    const actions = elt('div', 'detect-actions');
    actions.append(button(text('detect.pickFile'), () => pick('file'), card.id === 'start-detect' ? 'primary' : ''),
      button(text('detect.pickFolder'), () => pick('dir')));
    card.append(head, actions);
  }

  function paintBusy(card) {
    const head = elt('div', 'detect-head');
    head.append(icon('drop'));
    head.append(elt('div', 'detect-title', text('detect.working', {name: view.name})));
    card.append(head);
  }

  function paintResult(card) {
    const {result, outcome} = view;
    const head = elt('div', 'detect-head');
    const glyph = elt('span', 'engine-glyph');
    glyph.append(icon(known(result.engine) ? result.engine : 'search'));
    const copy = elt('div', 'detect-copy');
    copy.append(elt('div', 'detect-title', result.game || baseName(result.input)));
    const facts = [];
    if (result.engine) facts.push(text(result.confident ? 'detect.found' : 'detect.maybe', {engine: engineName(result.engine)}));
    if (result.titleId) facts.push(result.titleId);
    copy.append(elt('div', 'detect-hint', facts.join(' · ') || text('detect.none')));
    copy.title = result.input;
    head.append(glyph, copy);
    card.append(head);

    const actions = elt('div', 'detect-actions');
    if (outcome === 'switched' || outcome === 'already') {
      card.append(elt('p', 'detect-note', text(`detect.${outcome}`, {engine: engineName(result.engine)})));
    } else if (outcome === 'blocked') {
      card.append(elt('p', 'detect-problem', text('detect.blocked', {engine: engineName(result.engine)})));
    }
    if (result.problem) card.append(elt('p', 'detect-problem', problemText(result.problem)));
    if (!result.engine) card.append(elt('p', 'detect-note', text('detect.noneHint')));
    if (result.problem === 'keys') {
      actions.append(button(text('detect.chooseKeys'), async () => {
        if (await window.vees.chooseKeys()) inspect(result.input);
      }, 'primary'));
    }
    // Not sure, or the switch could not happen yet: let the user take it.
    const unchosen = !state.settings.engineChosen || result.engine !== state.settings.engine;
    if (known(result.engine) && (!result.confident || outcome === 'blocked') && unchosen) {
      actions.append(button(text('detect.use', {engine: engineName(result.engine)}), async () => {
        view.outcome = await switchTo(result);
        paint();
      }, 'primary'));
    }
    if (!result.engine || !result.confident) actions.append(button(text('detect.chooseByHand'), openAdvanced));
    // On the start page this asks for another game; in the sidebar, where a drop
    // works anywhere, it puts the report away.
    actions.append(button(text(card.id === 'start-detect' ? 'detect.again' : 'detect.dismiss'), () => { view = {kind: 'idle'}; paint(); }, 'quiet'));
    card.append(actions);

    const evidence = result.candidates[0]?.evidence || [];
    if (evidence.length) {
      const why = elt('details', 'detect-why');
      why.append(elt('summary', '', text('detect.evidence')));
      const list = elt('ul', '');
      for (const note of evidence) list.append(elt('li', 'mono', note));
      const others = result.candidates.slice(1).map(item => engineName(item.engine));
      why.append(list);
      if (others.length) why.append(elt('p', '', text('detect.others', {list: others.join(', ')})));
      card.append(why);
    }
  }

  // Both cards show the same state; only the one on screen is seen.
  function paint() {
    const kind = view.kind === 'result' ? (view.result.problem || !view.result.engine ? 'problem' : 'found') : view.kind;
    for (const card of cards) {
      card.replaceChildren();
      card.dataset.state = kind;
      card.setAttribute('aria-busy', String(view.kind === 'busy'));
      if (view.kind === 'busy') paintBusy(card);
      else if (view.kind === 'result') paintResult(card);
      else paintIdle(card);
    }
  }

  // The start page's own list: each engine as a choice, with what it is for.
  function paintStartEngines() {
    const box = $('start-engines');
    box.replaceChildren();
    for (const item of state.engines) {
      const choice = elt('button', 'start-engine');
      choice.type = 'button';
      const glyph = elt('span', 'engine-glyph');
      glyph.append(icon(item.id));
      const copy = elt('span', 'start-engine-copy');
      const purpose = text(`start.for.${item.id}`);
      copy.append(elt('span', 'start-engine-name', item.name),
        elt('span', 'start-engine-for', purpose === `start.for.${item.id}` ? item.subtitle : purpose));
      choice.append(glyph, copy, elt('span', 'start-engine-count', text('start.tools', {count: item.tools.length})));
      choice.addEventListener('click', () => chooseByHand(item.id));
      box.append(choice);
    }
  }

  async function inspect(input) {
    if (!input) return;
    view = {kind: 'busy', name: baseName(input)};
    paint();
    let result;
    try { result = await window.vees.detectEngine(input); }
    catch (error) { result = {input, kind: 'file', engine: null, confident: false, candidates: [], problem: error.message}; }
    let outcome = null;
    // A confident answer is acted on at once: dropping a game is the request.
    if (known(result.engine) && result.confident && !result.problem) outcome = await switchTo(result);
    view = {kind: 'result', result, outcome};
    paint();
  }
  async function pick(kind) {
    const input = await window.vees.chooseDetectInput(kind);
    if (input) inspect(input);
  }

  // ------------------------------------------------------------- the engine list

  // The summary names the engine in use. renderEngines() rebuilds the radios on
  // every render, so follow that instead of hooking into it. Its first rebuild
  // is also the first moment `state` exists: open the start page then if no
  // engine was ever chosen.
  function renderCurrent() {
    const current = engine();
    $('engine-current-glyph').replaceChildren(icon(current.id));
    $('engine-current-name').textContent = current.name;
    $('engine-current-for').textContent = current.subtitle;
  }
  // The folded panel offers the same pickers as the drop card; dropping works
  // anywhere in the window.
  byId('engine-pick-file').addEventListener('click', () => pick('file'));
  byId('engine-pick-folder').addEventListener('click', () => pick('dir'));
  new MutationObserver(() => {
    renderCurrent();
    if (started) return;
    started = true;
    paint();
    paintStartEngines();
    if (!state.settings.engineChosen) { page = 'start'; render(); }
  }).observe(byId('engines'), {childList: true});
  try { sideAdvanced.open = localStorage.getItem('otm-engine-advanced') === 'open'; } catch {}
  sideAdvanced.addEventListener('toggle', () => {
    try { localStorage.setItem('otm-engine-advanced', sideAdvanced.open ? 'open' : 'closed'); } catch {}
  });
  document.addEventListener('languagechange', () => { renderCurrent(); paint(); paintStartEngines(); });

  // ------------------------------------------------------------- dragging

  // The overlay shows while files are over the window. Counting enter and leave
  // keeps it from flickering as the pointer crosses child elements.
  let depth = 0;
  const carriesFiles = event => [...(event.dataTransfer?.types || [])].includes('Files');
  const overlay = show => $('drop-overlay').classList.toggle('hidden', !show);
  window.addEventListener('dragenter', event => {
    if (!carriesFiles(event)) return;
    event.preventDefault();
    depth++;
    overlay(true);
  });
  window.addEventListener('dragover', event => {
    // Without this the window would open the dropped file as a page.
    if (carriesFiles(event)) event.preventDefault();
  });
  window.addEventListener('dragleave', event => {
    if (!carriesFiles(event)) return;
    depth = Math.max(0, depth - 1);
    if (!depth) overlay(false);
  });
  window.addEventListener('drop', event => {
    if (!carriesFiles(event)) return;
    event.preventDefault();
    depth = 0;
    overlay(false);
    const file = event.dataTransfer.files[0];
    const input = file ? window.vees.pathForFile(file) : '';
    if (input) inspect(input);
  });

  // Exposed for the console and for checks that cannot fake a real drop.
  window.detectEngineFor = inspect;
})();
