// Shared update banner for the two desktop apps.
(() => {
  const api = window.ffu || window.vees;
  const byId = id => document.getElementById(id);
  const banner = byId('update-banner');
  const checkButton = byId('check-updates');
  const checkLabel = checkButton.querySelector('[data-i18n]') || checkButton;
  const openButton = byId('update-open');
  const dismissButton = byId('update-dismiss');
  const originalLabel = checkLabel.textContent;
  let latest = null;
  let shown = null;

  // Use the page's interface strings when it has them, English otherwise.
  function say(key, english, values = {}) {
    if (typeof t === 'function') return t(key, document.documentElement.lang, values);
    return english.replace(/\{(\w+)\}/g, (match, name) => name in values ? String(values[name]) : match);
  }

  function render(result, manual) {
    latest = result;
    if (!manual && (result.status !== 'available' || result.dismissed)) {
      banner.classList.add('hidden');
      shown = null;
      return;
    }
    shown = result;
    banner.className = `update-banner ${result.status === 'available' ? '' : result.status === 'error' ? 'error' : 'info'}`;
    openButton.classList.toggle('hidden', result.status !== 'available');
    if (result.status === 'available') {
      byId('update-title').textContent = say('update.available', 'Otome Translator {version} is available', {version: result.latestVersion});
      byId('update-message').textContent = result.title || say('update.release', 'A new release is available.');
    } else if (result.status === 'current') {
      byId('update-title').textContent = say('update.current', 'Otome Translator is up to date');
      byId('update-message').textContent = say('update.version', 'This app is version {version}.', {version: result.currentVersion});
    } else {
      byId('update-title').textContent = say('update.failed', 'Could not check for updates');
      byId('update-message').textContent = `${result.message || say('update.offline', 'Check your internet connection and try again.')}`;
    }
  }

  checkButton.addEventListener('click', async () => {
    const label = checkLabel.textContent;
    checkButton.disabled = true;
    checkLabel.textContent = say('update.checking', 'Checking…');
    try { render(await api.checkUpdates(), true); }
    catch (error) { render({status: 'error', message: error.message}, true); }
    finally {checkButton.disabled = false; checkLabel.textContent = label || originalLabel;}
  });
  openButton.addEventListener('click', async () => {
    if (latest?.status === 'available') await api.openUpdate();
  });
  dismissButton.addEventListener('click', async () => {
    if (latest?.status === 'available') await api.dismissUpdate(latest.tag);
    banner.classList.add('hidden');
    shown = null;
  });
  document.addEventListener('languagechange', () => {if (shown) render(shown, true);});
  api.on('update-status', result => render(result, false));
  api.checkUpdates().then(result => render(result, false)).catch(() => {});
})();
