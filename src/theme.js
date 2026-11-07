// Runs in <head> so the saved theme applies before the page paints.
(() => {
  let theme = 'dark';
  try { theme = localStorage.getItem('otm-theme') === 'light' ? 'light' : 'dark'; } catch {}
  document.documentElement.dataset.theme = theme;
  let width = 250;
  try {
    const saved = Number(localStorage.getItem('otm-sidebar-width'));
    if (Number.isFinite(saved)) width = Math.min(480, Math.max(200, Math.round(saved)));
  } catch {}
  document.documentElement.style.setProperty('--sidebar-width', `${width}px`);
})();
