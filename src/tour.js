// First-run tour: dims the window and lights up one part of it at a time,
// with a card that explains it. Shown once; the sidebar button replays it.
const tour = (() => {
  const DONE_KEY = 'otm-tour-done';
  // Each step lights up the first visible match; a step with none is skipped,
  // and a step without a target shows its card in the middle of the window.
  const STEPS = [
    {key: 'welcome'},
    {key: 'workspace', target: ['.workspace-card']},
    {key: 'engine', target: ['.engine-section']},
    {key: 'groups', target: ['.navigation']},
    {key: 'tools', target: ['.tool-panel']},
    {key: 'main', target: ['.main']},
    {key: 'settings', target: ['.sidebar-bottom']},
    {key: 'done'}
  ];
  const PAD = 6;
  const GAP = 14;
  let root = null;
  let spot, card, title, body, count, back, next;
  let steps = [];
  let index = 0;
  let returnFocus = null;

  function say(key, values) { return t(key, document.documentElement.lang, values); }
  function visible(node) {
    if (!node) return false;
    const box = node.getBoundingClientRect();
    return box.width > 0 && box.height > 0;
  }
  function targetOf(step) {
    for (const selector of step.target || []) {
      const node = document.querySelector(selector);
      if (visible(node)) return node;
    }
    return null;
  }

  function build() {
    root = document.createElement('div');
    root.className = 'tour';
    root.innerHTML = `
      <div class="tour-blocker"></div>
      <div class="tour-spot"></div>
      <section class="tour-card" role="dialog" aria-modal="true" aria-labelledby="tour-title" aria-describedby="tour-body">
        <div class="tour-count"></div>
        <h2 id="tour-title"></h2>
        <p id="tour-body"></p>
        <div class="tour-actions">
          <button type="button" class="link-button tour-skip"></button>
          <button type="button" class="button tour-back"></button>
          <button type="button" class="button primary tour-next"></button>
        </div>
      </section>`;
    spot = root.querySelector('.tour-spot');
    card = root.querySelector('.tour-card');
    title = root.querySelector('#tour-title');
    body = root.querySelector('#tour-body');
    count = root.querySelector('.tour-count');
    back = root.querySelector('.tour-back');
    next = root.querySelector('.tour-next');
    root.querySelector('.tour-skip').addEventListener('click', finish);
    back.addEventListener('click', () => go(index - 1));
    next.addEventListener('click', () => index === steps.length - 1 ? finish() : go(index + 1));
    document.body.append(root);
  }

  function onKey(event) {
    if (event.key === 'Escape') finish();
    else if (event.key === 'ArrowRight') go(index + 1);
    else if (event.key === 'ArrowLeft') go(index - 1);
    else if (event.key === 'Tab') {
      // Keep focus inside the card while the rest of the window is dimmed.
      const buttons = [...card.querySelectorAll('button:not(.hidden)')];
      const at = buttons.indexOf(document.activeElement);
      const to = event.shiftKey ? (at <= 0 ? buttons.length - 1 : at - 1) : (at + 1) % buttons.length;
      buttons[to].focus();
    } else return;
    event.preventDefault();
    event.stopPropagation();
  }

  function render() {
    const step = steps[index];
    const last = index === steps.length - 1;
    count.textContent = say('tour.count', {step: index + 1, total: steps.length});
    title.textContent = say(`tour.${step.key}.title`);
    body.textContent = say(`tour.${step.key}.body`);
    root.querySelector('.tour-skip').textContent = say('tour.skip');
    root.querySelector('.tour-skip').classList.toggle('hidden', last);
    back.textContent = say('tour.back');
    back.classList.toggle('hidden', index === 0);
    next.textContent = say(last ? 'tour.finish' : index === 0 ? 'tour.start' : 'tour.next');
    place();
  }

  // Fit the light around the target, then put the card beside it: right, below,
  // above or left, whichever has room first, kept inside the window.
  function place() {
    if (!root) return;
    const target = targetOf(steps[index]);
    const width = window.innerWidth;
    const height = window.innerHeight;
    root.classList.toggle('centered', !target);
    const cardBox = card.getBoundingClientRect();
    if (!target) {
      Object.assign(spot.style, {left: `${width / 2}px`, top: `${height / 2}px`, width: '0px', height: '0px'});
      card.style.left = `${(width - cardBox.width) / 2}px`;
      card.style.top = `${(height - cardBox.height) / 2}px`;
      return;
    }
    const box = target.getBoundingClientRect();
    const left = Math.max(box.left - PAD, 4);
    const top = Math.max(box.top - PAD, 4);
    const right = Math.min(box.right + PAD, width - 4);
    const bottom = Math.min(box.bottom + PAD, height - 4);
    Object.assign(spot.style, {left: `${left}px`, top: `${top}px`, width: `${right - left}px`, height: `${bottom - top}px`});
    const options = [
      [right + GAP, top, width - right - GAP >= cardBox.width],
      [left, bottom + GAP, height - bottom - GAP >= cardBox.height],
      [left, top - GAP - cardBox.height, top - GAP >= cardBox.height],
      [left - GAP - cardBox.width, top, left - GAP >= cardBox.width]
    ];
    // Nothing fits beside a large area, so the card sits over its lower right corner.
    const [x, y] = options.find(option => option[2]) || [right - cardBox.width - GAP, bottom - cardBox.height - GAP];
    card.style.left = `${Math.min(Math.max(x, 12), width - cardBox.width - 12)}px`;
    card.style.top = `${Math.min(Math.max(y, 12), height - cardBox.height - 12)}px`;
  }

  function go(to) {
    if (to < 0 || to >= steps.length) return;
    index = to;
    targetOf(steps[index])?.scrollIntoView({block: 'nearest'});
    render();
    next.focus();
  }

  function start() {
    if (root) return;
    returnFocus = document.activeElement;
    steps = STEPS.filter(step => !step.target || targetOf(step));
    index = 0;
    build();
    document.addEventListener('keydown', onKey, true);
    document.addEventListener('languagechange', render);
    window.addEventListener('resize', place);
    document.addEventListener('scroll', place, true);
    go(0);
  }

  function finish() {
    if (!root) return;
    try { localStorage.setItem(DONE_KEY, '1'); } catch {}
    document.removeEventListener('keydown', onKey, true);
    document.removeEventListener('languagechange', render);
    window.removeEventListener('resize', place);
    document.removeEventListener('scroll', place, true);
    root.remove();
    root = null;
    returnFocus?.focus?.();
  }

  // Called once the page has its first render.
  function firstRun() {
    let done = false;
    try { done = localStorage.getItem(DONE_KEY) === '1'; } catch {}
    if (!done) start();
  }

  return {start, firstRun};
})();
