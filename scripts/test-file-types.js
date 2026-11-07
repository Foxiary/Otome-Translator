const assert = require('node:assert/strict');
const {filtersFor, companionFor, companionPath, startCandidates} = require('../src/file-types');

const extensions = arg => filtersFor(arg)[0]?.extensions || [];

assert.deepEqual(extensions({name: 'workbook'}), ['xlsx']);
assert.deepEqual(extensions({name: '--font', help: 'FFU used for width checks'}), ['ffu']);
assert.deepEqual(extensions({name: '--font', help: 'Font chain in priority order; use path#face for TTC'}), ['ttf', 'otf', 'ttc']);
assert.deepEqual(extensions({name: 'scripts', help: 'STORY CPK or DAT folder'}), ['cpk', 'dat']);
assert.deepEqual(extensions({name: 'NSP or XCI'}), ['nsp', 'xci']);
assert.deepEqual(extensions({name: '--keys', help: 'prod.keys; defaults to the one in Ryujinx/system'}), ['keys']);
assert.deepEqual(extensions({name: '--report', help: 'Overflow CSV'}), ['csv']);
assert.deepEqual(extensions({name: 'memfs', help: 'script.memfs'}), ['memfs']);
assert.deepEqual(extensions({name: 'membody', help: 'script.membody'}), ['membody']);
assert.deepEqual(extensions({name: 'file', help: '.tat script'}), ['tat']);
// Files without a fixed extension are not filtered.
assert.deepEqual(filtersFor({name: 'NSO (main)'}), []);
assert.deepEqual(filtersFor({name: 'bundle or .assets'}), []);
// A typed file can still be overridden, except a screen: only its .memfs can run,
// and only when the data file sits next to it.
assert.deepEqual(filtersFor({name: 'workbook'})[1], {name: 'All files', extensions: ['*']});
const screen = {name: 'screen', kind: 'file', help: 'A screen\'s .memfs under romfs/spec_win/ssdata, e.g. ttlm_nam.memfs (title menu); its data file must sit next to it'};
assert.deepEqual(filtersFor(screen), [{name: 'MemFS', extensions: ['memfs']}]);
assert.equal(companionFor(screen), 'membody');
assert.equal(companionFor({name: 'memfs', help: 'script.memfs'}), '');
assert.deepEqual(startCandidates(screen), ['game/romfs/spec_win/ssdata', 'romfs/spec_win/ssdata']);
assert.deepEqual(startCandidates({name: 'memfs', help: 'script.memfs'}), []);
assert.equal(companionPath('/ssdata/ttlm_nam.memfs', 'membody'), '/ssdata/ttlm_nam.membody');
assert.equal(companionPath('C:\\ssdata\\ttlm_nam.memfs', 'membody'), 'C:\\ssdata\\ttlm_nam.membody');
assert.equal(companionPath('/ssdata/ttlm_nam.membody', 'membody'), '');
assert.equal(companionPath('/ssdata/ttlm_nam', 'membody'), '');
