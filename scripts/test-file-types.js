const assert = require('node:assert/strict');
const {filtersFor} = require('../src/file-types');

const extensions = arg => filtersFor(arg)[0]?.extensions || [];

assert.deepEqual(extensions({name: 'workbook'}), ['xlsx']);
assert.deepEqual(extensions({name: '--font', help: 'FFU used for width checks'}), ['ffu']);
assert.deepEqual(extensions({name: '--font', help: 'Font chain in priority order; use path#face for TTC'}), ['ttf', 'otf', 'ttc']);
assert.deepEqual(extensions({name: 'scripts', help: 'STORY CPK or DAT folder'}), ['cpk', 'dat']);
assert.deepEqual(extensions({name: 'NSP or XCI'}), ['nsp', 'xci']);
assert.deepEqual(extensions({name: '--keys', help: 'prod.keys; defaults to the one in Ryujinx/system'}), ['keys']);
assert.deepEqual(extensions({name: '--report', help: 'Overflow CSV'}), ['csv']);
// Files without a fixed extension are not filtered.
assert.deepEqual(filtersFor({name: 'NSO (main)'}), []);
assert.deepEqual(filtersFor({name: 'bundle or .assets'}), []);
// Every filter still lets the translator pick any file.
assert.deepEqual(filtersFor({name: 'workbook'})[1], {name: 'All files', extensions: ['*']});
