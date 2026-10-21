// Files some tools read from fixed places in the project folder rather than
// from a form field. The form and the patch page warn about the ones that are
// not there yet.
const fs = require('node:fs');
const path = require('node:path');

function fontsConfig(workspace) {
  try { return JSON.parse(fs.readFileSync(path.join(workspace, 'fonts.json'), 'utf8')); }
  catch { return null; }
}

// Each entry: path relative to the project folder, `also` for accepted
// alternatives, `pattern` when any file whose name matches will do, and `hint`
// naming where the file comes from.
const STORY = {path: 'STORY.cpk', hint: 'game'};
const JP_STORY = {path: 'work/jp/CONTENTS/STORY.cpk', hint: 'jp'};
const BUILT_FONTS = {path: 'dist/SYSTEM.cpk', also: ['work/out/SYSTEM.cpk'], hint: 'built'};
const REQUIRED = {
  // build.py reads the CPK and every source font named in fonts.json.
  build(workspace) {
    const config = fontsConfig(workspace);
    if (!config) return [{path: 'fonts.json', hint: 'engine'}];
    const sources = Object.values(config.fonts || {}).map(font => font.source).filter(Boolean);
    return [{path: config.cpk || 'SYSTEM.cpk', hint: 'game'},
      ...[...new Set(sources)].map(source => ({path: source, hint: 'font'}))];
  },
  chuadich: () => [STORY, JP_STORY],
  // quarong.py measures with the built fonts and only falls back to the stock ones.
  quarong: () => [STORY, BUILT_FONTS],
  // The patch page runs quarong with the translators' sheet, which also reads the
  // Japanese script, then writes STORY.cpk's scripts with applyvi.
  'patch:otomate': () => [STORY, JP_STORY, BUILT_FONTS],
  'patch:unity': () => [{path: '*.bundle, *.assets', pattern: /\.(bundle|assets)$/i, hint: 'game'},
    {path: 'text-boxes.json', hint: 'boxes'}]
};

function present(item, workspace) {
  if (item.pattern) {
    try { return fs.readdirSync(workspace).some(name => item.pattern.test(name)); }
    catch { return false; }
  }
  return [item.path, ...(item.also || [])].some(file => fs.existsSync(path.join(workspace, file)));
}

function missingFiles(toolId, workspace) {
  const rule = REQUIRED[toolId];
  if (!rule || !workspace) return [];
  return rule(workspace).filter(item => !present(item, workspace))
    .map(({path: file, hint}) => ({path: file, hint}));
}

module.exports = {missingFiles};
