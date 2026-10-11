// Defaults for the guided patch flow. Workspaces and saved tool forms stay as they are.
function normalizePatchSettings(settings, engineIds) {
  const next = {
    ...settings,
    workspaces: {...(settings.workspaces || {})},
    values: {...(settings.values || {})},
    patch: {...(settings.patch || {})}
  };
  next.language = next.language === 'vi' ? 'vi' : 'en';
  for (const id of engineIds) {
    const current = next.patch[id] || {};
    next.patch[id] = {
      sheetPath: typeof current.sheetPath === 'string' ? current.sheetPath : '',
      outputPath: typeof current.outputPath === 'string' ? current.outputPath : '',
      group: typeof current.group === 'string' && current.group ? current.group : null
    };
  }
  return next;
}

function setSheetPath(settings, engineIds, engineId, sheetPath) {
  const next = normalizePatchSettings(settings, engineIds);
  next.patch[engineId] = {...next.patch[engineId], sheetPath};
  return next;
}

module.exports = {normalizePatchSettings, setSheetPath};
