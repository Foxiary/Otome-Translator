function isXlsx(name) {
  return typeof name === 'string' && /\.xlsx$/i.test(name);
}

function successActions() {
  return ['open-folder', 'choose-another-file'];
}

function canSwitchEngine(running) {
  return !running;
}

function canOpenTools(running) {
  return !running;
}

function languageChange() {
  return {workbookPath: null};
}

module.exports = {isXlsx, successActions, canSwitchEngine, canOpenTools, languageChange};
