// Shared update banner and dialog for the two desktop apps.
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

  // Update dialog: shown for manual checks, and once per release when the
  // background check finds one the user has not skipped.
  const dialog = document.createElement('dialog');
  dialog.className = 'update-dialog';
  dialog.innerHTML = '<div class="dialog-header"><h2></h2><button class="icon-button" type="button"><svg class="icon"><use href="#i-close"/></svg></button></div>'
    + '<div class="dialog-body"><p></p></div><div class="update-dialog-actions"></div>';
  document.body.appendChild(dialog);
  const dialogTitle = dialog.querySelector('h2');
  const dialogMessage = dialog.querySelector('.dialog-body p');
  const dialogClose = dialog.querySelector('.dialog-header button');
  const dialogActions = dialog.querySelector('.update-dialog-actions');
  let dialogResult = null;
  let promptedTag = null;

  function action(label, className, onClick) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = className;
    button.textContent = label;
    button.addEventListener('click', onClick);
    return button;
  }

  function fillDialog() {
    const result = dialogResult;
    dialog.classList.toggle('error', result.status === 'error');
    dialogClose.title = dialogClose.ariaLabel = say('tools.close', 'Close');
    if (result.status === 'available') {
      dialogTitle.textContent = say('update.available', 'Otome Translator {version} is available', {version: result.latestVersion});
      dialogMessage.textContent = say('update.installed', 'Installed version: {version}.', {version: result.currentVersion});
      dialogActions.replaceChildren(
        action(say('update.later', 'Later'), 'button', () => dialog.close()),
        action(say('update.view', 'View changes ↗'), 'button primary', async () => {
          dialog.close();
          await api.openUpdate();
        }));
    } else {
      if (result.status === 'current') {
        dialogTitle.textContent = say('update.current', 'Otome Translator is up to date');
        dialogMessage.textContent = say('update.version', 'This app is version {version}.', {version: result.currentVersion});
      } else {
        dialogTitle.textContent = say('update.failed', 'Could not check for updates');
        dialogMessage.textContent = result.message || say('update.offline', 'Check your internet connection and try again.');
      }
      dialogActions.replaceChildren(action(say('tools.close', 'Close'), 'button primary', () => dialog.close()));
    }
  }

  function notify(result) {
    dialogResult = result;
    if (result.status === 'available') promptedTag = result.tag;
    fillDialog();
    if (!dialog.open) dialog.showModal();
    dialogActions.lastChild.focus();
  }
  dialogClose.addEventListener('click', () => dialog.close());

  // The background check opens the dialog only for a release not yet shown.
  function onBackground(result) {
    render(result, false);
    if (result.status === 'available' && !result.dismissed && result.tag !== promptedTag) notify(result);
  }

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
  document.addEventListener('languagechange', () => {
    if (shown) render(shown, true);
    if (dialog.open) fillDialog();
  });
  api.on('update-status', onBackground);
  api.checkUpdates().then(onBackground).catch(() => {});
})();
