const assert = require('node:assert/strict');
const {FONT_ROLES, MAPPED_ARGS, fontRole, ffugenArgs, argValue, withOverrides, chainMissing, defaultOutput, fontJobProblem} = require('../src/font-map');
const {engines} = require('../src/engines');
const {entries} = require('../src/i18n');

// The ADV fonts get the stock outline and the tone-mark lift; sysfont cannot draw an outline.
assert.deepEqual(ffugenArgs({cell: 88, outline: true}, 75), ['--cell', '88', '--glow', '0.4', '--px', '75', '--stroke', '2', '--mark-lift', '3']);
assert.deepEqual(ffugenArgs({cell: 37, outline: false}, 29), ['--cell', '37', '--glow', '0.4', '--px', '29']);
// No fitted size leaves ffugen to auto-fit.
assert.deepEqual(ffugenArgs({cell: 37, outline: false}), ['--cell', '37', '--glow', '0.4']);

// A setting filled in by hand takes the automatic one's place; switches are added.
const auto = ffugenArgs({cell: 88, outline: true}, 75);
assert.deepEqual(withOverrides(auto, ['--px', '70', '--no-vn']),
  ['--cell', '88', '--glow', '0.4', '--stroke', '2', '--mark-lift', '3', '--px', '70', '--no-vn']);
assert.deepEqual(withOverrides(auto, []), auto);
assert.equal(argValue(['--cell', '88', '--px', '70'], '--px'), '70');
assert.equal(argValue(['--cell', '88'], '--px'), undefined);

// Every ffugen argument the rows do not fill in shows as an advanced setting.
const ffugen = engines.find(engine => engine.id === 'otomate').tools.find(tool => tool.id === 'ffugen');
for (const name of MAPPED_ARGS) assert.ok(ffugen.args.some(arg => arg.name === name), name);
assert.ok(ffugen.args.filter(arg => !MAPPED_ARGS.includes(arg.name)).every(arg => !arg.required));

// A fallback font covers what the main one lacks; a letter is missing only if no font has it.
const covered = missing => ({coverage: {vn: 146 - missing.length, total: 146, missing}});
assert.equal(chainMissing([covered('ăằ')]), 'ăằ');
assert.equal(chainMissing([covered('ăằ'), covered('ằ')]), 'ằ');
assert.equal(chainMissing([covered('ăằ'), covered('')]), '');
assert.equal(chainMissing([covered('ă'), {coverage: null}]), null);

// The output folder is filled in next to the originals, never on top of them.
assert.equal(defaultOutput(['D:\\VE\\font\\advfont1.ffu', 'D:\\VE\\font\\sysfont.ffu']), 'D:\\VE\\font\\vn');
assert.equal(defaultOutput(['/home/me/font/advfont1.ffu']), '/home/me/font/vn');
assert.equal(defaultOutput([]), '');
assert.equal(fontRole('D:\\x\\AdvFont2.ffu'), 'option2');
assert.equal(fontRole('other.ffu'), null);

const font = {path: 'C:\\f.ttf', ...covered('')};
const ffu = (path, extra = {}) => ({path, info: {cell: 88, outline: true}, fonts: [font], ...extra});
const out = 'D:\\VE\\font\\vn';
assert.equal(fontJobProblem([], out), 'ffu');
assert.equal(fontJobProblem([ffu('D:\\a\\advfont1.ffu'), ffu('D:\\b\\advfont1.ffu')], out), 'duplicate');
assert.equal(fontJobProblem([ffu('D:\\VE\\font\\x.ffu', {info: {error: 'not-ffu'}})], out), 'invalid');
assert.equal(fontJobProblem([ffu('D:\\VE\\font\\advfont1.ffu', {fonts: []})], out), 'font');
assert.equal(fontJobProblem([ffu('D:\\VE\\font\\advfont1.ffu', {fonts: [font, {path: 'x', coverage: {error: 'not-font'}}]})], out), 'badFont');
assert.equal(fontJobProblem([ffu('D:\\VE\\font\\advfont1.ffu')], ''), 'output');
assert.equal(fontJobProblem([ffu('D:\\VE\\font\\advfont1.ffu')], 'd:/ve/FONT/'), 'sameFolder');
assert.equal(fontJobProblem([ffu('D:\\VE\\font\\advfont1.ffu'), ffu('D:\\VE\\font\\advfont2.ffu', {fonts: []})], out), null);
// A font still being checked does not block; main reads the files again before running.
assert.equal(fontJobProblem([ffu('D:\\VE\\font\\advfont1.ffu', {fonts: [{path: 'C:\\f.ttf', coverage: null}]})], out), null);

// Every reason and role the page can show has its words in both languages.
const strings = entries();
for (const key of ['ffu', 'duplicate', 'invalid', 'font', 'badFont', 'output', 'sameFolder']) assert.ok(strings[`fonts.need.${key}`]?.vi, key);
for (const role of [...Object.values(FONT_ROLES), 'other']) assert.ok(strings[`fonts.role.${role}`]?.vi, role);
console.log('font-map assertions passed');
