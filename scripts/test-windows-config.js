const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {FILE, readWindows, saveWindow} = require('../src/windows-config');

const workspace = fs.mkdtempSync(path.join(os.tmpdir(), 'otm-windows-'));
try {
  assert.deepEqual(readWindows(workspace), {});

  const framed = {ceiling: 2173.6, font: 'advfont1.ffu', fontFile: 'dist/SYSTEM.cpk', line: '2037 ---|', lineUnits: 2037,
    pixels: {start: 382.84, end: 1516.33, edge: 1592.81}, image: 'shot.png'};
  saveWindow(workspace, 'framed', framed);
  const saved = readWindows(workspace).framed;
  assert.equal(saved.ceiling, 2174);
  assert.deepEqual(saved.pixels, {start: 382.8, end: 1516.3, edge: 1592.8});
  assert.ok(saved.measuredAt);

  // Saving another screen keeps the first, and keys the file adds of its own survive.
  const file = path.join(workspace, FILE);
  const data = JSON.parse(fs.readFileSync(file, 'utf8'));
  fs.writeFileSync(file, JSON.stringify({...data, note: 'kept'}));
  saveWindow(workspace, 'backlog', {...framed, ceiling: 2430});
  const after = JSON.parse(fs.readFileSync(file, 'utf8'));
  assert.equal(after.note, 'kept');
  assert.deepEqual(Object.keys(after.windows).sort(), ['backlog', 'framed']);

  // Saving the same screen again replaces it.
  saveWindow(workspace, 'framed', {...framed, ceiling: 2180});
  assert.equal(readWindows(workspace).framed.ceiling, 2180);

  assert.throws(() => saveWindow(workspace, 'credits', framed), /Unknown screen/);
  assert.throws(() => saveWindow(workspace, 'framed', {...framed, ceiling: 0}), /positive/);
  assert.throws(() => saveWindow('', 'framed', framed), /project folder/);

  // A damaged file reads as empty rather than breaking the page.
  fs.writeFileSync(file, '{not json');
  assert.deepEqual(readWindows(workspace), {});
} finally {
  fs.rmSync(workspace, {recursive: true, force: true});
}
console.log('windows-config assertions passed');
