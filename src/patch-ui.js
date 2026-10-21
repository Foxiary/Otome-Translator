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

// Loaded by main and the tests through require, and by the page as a plain script.
if (typeof module !== 'undefined') module.exports = {isXlsx, successActions, canSwitchEngine, canOpenTools, languageChange};
