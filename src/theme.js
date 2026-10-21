// Runs in <head> so the saved theme applies before the page paints.
(() => {
  let theme = 'dark';
  try { theme = localStorage.getItem('otm-theme') === 'light' ? 'light' : 'dark'; } catch {}
  document.documentElement.dataset.theme = theme;
})();
