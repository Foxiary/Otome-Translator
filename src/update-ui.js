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

  // Floating notice for manual checks, visible whichever view is open.
  const toast = document.createElement('div');
  toast.className = 'update-toast';
  toast.setAttribute('role', 'status');
  const toastBody = document.createElement('div');
  const closeToast = document.createElement('button');
  closeToast.type = 'button';
  closeToast.className = 'update-toast-close';
  closeToast.innerHTML = '<svg class="icon"><use href="#i-close"/></svg>';
  toast.append(toastBody, closeToast);
  document.body.appendChild(toast);
  let toastTimer = null;

  function hideToast() {
    clearTimeout(toastTimer);
    toast.classList.remove('open');
  }
  // Auto-hide, but never while the pointer is resting on the notice.
  function scheduleHide() {
    clearTimeout(toastTimer);
    toastTimer = setTimeout(hideToast, 6000);
  }

  function notify(result) {
    const title = document.createElement('strong');
    const message = document.createElement('p');
    if (result.status === 'available') {
      title.textContent = say('update.available', 'Otome Translator {version} is available', {version: result.latestVersion});
      message.textContent = say('update.installed', 'Installed version: {version}.', {version: result.currentVersion});
    } else if (result.status === 'current') {
      title.textContent = say('update.current', 'Otome Translator is up to date');
      message.textContent = say('update.version', 'This app is version {version}.', {version: result.currentVersion});
    } else {
      title.textContent = say('update.failed', 'Could not check for updates');
      message.textContent = result.message || say('update.offline', 'Check your internet connection and try again.');
    }
    toastBody.replaceChildren(title, message);
    closeToast.title = closeToast.ariaLabel = say('tools.close', 'Close');
    toast.className = `update-toast ${result.status === 'available' ? '' : result.status === 'error' ? 'error' : 'info'}`;
    void toast.offsetWidth; // restart the entrance animation on repeat checks
    toast.classList.add('open');
    if (!toast.matches(':hover')) scheduleHide();
  }
  toast.addEventListener('mouseenter', () => clearTimeout(toastTimer));
  toast.addEventListener('mouseleave', () => {if (toast.classList.contains('open')) scheduleHide();});
  closeToast.addEventListener('click', event => {
    event.stopPropagation();
    hideToast();
  });
  toast.addEventListener('click', async () => {
    hideToast();
    if (latest?.status === 'available') await api.openUpdate();
  });

  checkButton.addEventListener('click', async () => {
    const label = checkLabel.textContent;
    checkButton.disabled = true;
    checkLabel.textContent = say('update.checking', 'Checking…');
    let result;
    try { result = await api.checkUpdates(); }
    catch (error) { result = {status: 'error', message: error.message}; }
    finally {checkButton.disabled = false; checkLabel.textContent = label || originalLabel;}
    render(result, true);
    notify(result);
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
