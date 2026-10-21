// windows.json in the project folder: text box widths measured from screenshots,
// one per kind of screen, for the width check to compare lines against.
const fs = require('node:fs');
const path = require('node:path');

const FILE = 'windows.json';
// The kinds of screen the measure page offers. The names follow the ceilings in
// engines/otomate/tools/textwidth.py so the width check can map them directly.
const SCREENS = ['dialogue', 'framed', 'backlog', 'narration'];
const COMMENT = 'Text box widths in font units, measured from screenshots on the Measure text boxes page. '
  + 'ceiling is the furthest a line may reach on that screen; the other fields record how it was measured.';

function readWindows(workspace) {
  if (!workspace) return {};
  try {
    const data = JSON.parse(fs.readFileSync(path.join(workspace, FILE), 'utf8'));
    return data && typeof data.windows === 'object' && data.windows ? data.windows : {};
  } catch {
    return {};
  }
}

function finite(value) { return typeof value === 'number' && Number.isFinite(value); }

// Replaces the entry for one screen and keeps the rest of the file as it was.
function saveWindow(workspace, screen, entry) {
  if (!workspace) throw new Error('Choose a project folder first.');
  if (!SCREENS.includes(screen)) throw new Error(`Unknown screen: ${screen}`);
  const ceiling = Math.round(entry?.ceiling);
  if (!finite(ceiling) || ceiling <= 0) throw new Error('The box width must be a positive number.');
  const file = path.join(workspace, FILE);
  let data = {};
  try { data = JSON.parse(fs.readFileSync(file, 'utf8')) || {}; } catch {}
  const pixels = entry.pixels || {};
  data._comment = COMMENT;
  data.windows = {...(typeof data.windows === 'object' && data.windows ? data.windows : {}), [screen]: {
    ceiling,
    font: String(entry.font || ''),
    fontFile: String(entry.fontFile || ''),
    line: String(entry.line || ''),
    lineUnits: finite(entry.lineUnits) ? entry.lineUnits : null,
    pixels: Object.fromEntries(['start', 'end', 'edge'].map(key => [key, finite(pixels[key]) ? Math.round(pixels[key] * 10) / 10 : null])),
    image: String(entry.image || ''),
    measuredAt: new Date().toISOString()
  }};
  fs.writeFileSync(file, `${JSON.stringify(data, null, 2)}\n`, 'utf8');
  return data.windows;
}

module.exports = {FILE, SCREENS, readWindows, saveWindow};
