// Defaults for the guided patch flow. Workspaces and saved tool forms stay as they are.

// The advanced options each engine's patch page offers, with the kind of value each takes.
const PATCH_OPTIONS = {
  otomate: {dryRun: 'bool', sheets: 'text', allowOverflow: 'bool'},
  unity: {dryRun: 'bool', sheetName: 'text', force: 'bool', packer: ['auto', 'lz4', 'lzma', 'none', 'original'], tokens: 'text'}
};

function cleanPatchOptions(engineId, options) {
  const kinds = PATCH_OPTIONS[engineId] || {};
  const source = options && typeof options === 'object' ? options : {};
  const out = {};
  for (const [key, kind] of Object.entries(kinds)) {
    const value = source[key];
    if (kind === 'bool') out[key] = value === true;
    else if (kind === 'number') out[key] = Number.isFinite(Number(value)) && Number(value) > 0 ? Math.floor(Number(value)) : 0;
    else if (kind === 'text') out[key] = typeof value === 'string' ? value : '';
    else out[key] = kind.includes(value) ? value : kind[0];
  }
  return out;
}
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
      group: typeof current.group === 'string' && current.group ? current.group : null,
      options: cleanPatchOptions(id, current.options)
    };
  }
  return next;
}

function setSheetPath(settings, engineIds, engineId, sheetPath) {
  const next = normalizePatchSettings(settings, engineIds);
  next.patch[engineId] = {...next.patch[engineId], sheetPath};
  return next;
}

module.exports = {normalizePatchSettings, setSheetPath, cleanPatchOptions, PATCH_OPTIONS};
