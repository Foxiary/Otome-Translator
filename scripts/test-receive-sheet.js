const assert = require('node:assert');
const crypto = require('node:crypto');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {spawnSync} = require('node:child_process');
const {normalizePatchSettings, setSheetPath} = require('../src/patch-settings');
const {entries} = require('../src/i18n');
const {browse, clearSearch, selectTool, toolsForEngine} = require('../src/tool-browser');
const {isXlsx, successActions, canSwitchEngine, languageChange} = require('../src/patch-ui');
const {recipeFor, planCommands, runRecipe, excludedIds} = require('../src/patch-recipe');
const otomate = require('../src/catalog-otomate').tools;
const unity = require('../src/catalog-unity').tools;

const omitted = {workspaces: {otomate: '/projects/otomate'}, values: {build: {sheet: 'kept'}}};
const normalized = normalizePatchSettings(omitted, ['otomate', 'unity']);
assert.equal(normalized.language, 'en');
assert.equal(normalized.workspaces.otomate, '/projects/otomate');
assert.deepEqual(normalized.values.build, {sheet: 'kept'});
assert.equal(normalized.patch.otomate.sheetPath, '');
assert.equal(normalized.patch.otomate.outputPath, '');
assert.equal(normalized.patch.otomate.group, null);
assert.equal(normalized.patch.unity.group, null);

const kept = normalizePatchSettings({
  language: 'vi',
  workspaces: {otomate: '/keep'},
  values: {},
  patch: {otomate: {sheetPath: '/sheet.xlsx', outputPath: '/out', group: 'Sheets'}}
}, ['otomate', 'unity']);
assert.equal(kept.language, 'vi');
assert.equal(kept.workspaces.otomate, '/keep');
assert.equal(kept.patch.otomate.sheetPath, '/sheet.xlsx');

const strings = entries();
for (const [key, value] of Object.entries(strings)) {
  assert.ok(value.en && value.vi, key);
  assert.equal(typeof value.en, 'string');
  assert.ok(!/[/\\]/.test(value.en + value.vi), key);
}
assert.deepEqual(Object.keys(require('../src/i18n')), ['t', 'entries']);

const nine = Array.from({length: 9}, (_, index) => ({
  id: `tool-${index}`, engine: 'otomate', group: index === 8 ? 'Fonts' : 'Sheets',
  title: index === 3 ? 'Tìm khung' : `Tool ${index}`,
  description: 'purpose', script: 'tools/x.py', prefix: []
}));
const fonts = browse(nine, {group: 'Fonts'});
assert.equal(fonts.total, 1);
const allSheets = browse(nine, {group: 'Sheets'});
assert.equal(allSheets.total, 8);
const paged = browse(nine, {group: null, query: 'tool', page: 1});
assert.equal(paged.tools.length, 8);
const pagedNext = browse(nine, {group: null, query: 'tool', page: 2});
assert.equal(pagedNext.tools.length, 1);
assert.equal(browse(nine, {group: 'Fonts', query: 'tim'}).tools[0].title, 'Tìm khung');
assert.equal(browse(nine, {group: 'Sheets', query: 'tool-8'}).tools[0].group, 'Fonts');
assert.equal(clearSearch('Sheets'), 'Sheets');
assert.equal(browse(nine, {group: null}).total, 0);

const mixed = [
  {id: 'build', engine: 'otomate', group: 'Build', title: 'Build', description: '', script: 'build.py', prefix: []},
  {id: 'unity-sheet-apply', engine: 'unity', group: 'Text', title: 'Apply', description: '', script: 'tools/jsonsheet.py', prefix: ['apply']}
];
assert.ok(!toolsForEngine(mixed, 'unity').some(tool => tool.id === 'build'));

for (const id of ['translate-glossary', 'build', 'ffugen']) {
  const tool = otomate.find(item => item.id === id);
  assert.ok(tool.note, id);
  assert.equal(selectTool(tool).runRequest, null);
  assert.ok(selectTool(tool).caution);
  assert.ok(selectTool(tool).command);
}
for (const id of ['unity-romfs', 'unity-tmpfont-add']) {
  const tool = unity.find(item => item.id === id);
  assert.ok(tool.note, id);
  assert.equal(selectTool(tool).runRequest, null);
}

assert.deepEqual(recipeFor('otomate').map(step => step.id), ['filltitles-fill', 'quarong', 'applyvi']);
assert.deepEqual(recipeFor('unity').map(step => step.id), ['empty-scan', 'unity-sheetfit', 'unity-sheet-apply']);
for (const engine of ['otomate', 'unity']) {
  for (const id of excludedIds()) assert.ok(!recipeFor(engine).some(step => step.id === id), id);
}

const original = '/home/translator/sheet.xlsx';
const copy = {ok: true, path: '/out/runs/1/sheet.xlsx', runDirectory: '/out/runs/1'};
const planned = planCommands({engine: 'otomate', originalPath: original, copy, outputPath: '/out'});
for (const command of planned) assert.ok(!command.outputs.includes(original));
assert.deepEqual(planCommands({engine: 'otomate', originalPath: original, copy: {ok: false}, outputPath: '/out'}), []);

const base = {originalPath: original, copy, outputPath: '/out', runStep: () => ({code: 0})};
assert.equal(runRecipe('otomate', {...base, findings: [{sheet: 'Dialogue', row: 24}]}).createCalled, false);
assert.equal(runRecipe('otomate', {...base, checkExit: 1}).createCalled, false);
assert.equal(runRecipe('otomate', {...base, reportReadable: false}).createCalled, false);
assert.equal(runRecipe('otomate', {...base, findings: [{sheet: 'Dialogue', row: 24}]}).skip, false);

const confirmed = runRecipe('otomate', {...base, outputHasPatch: true, confirmed: true});
assert.equal(confirmed.createCalled, true);
assert.equal(confirmed.complete, true);
const declined = runRecipe('otomate', {...base, outputHasPatch: true, confirmed: false});
assert.equal(declined.createCalled, false);
assert.equal(declined.complete, false);

const cancelled = runRecipe('otomate', {...base, cancelAfterPrepare: true});
assert.equal(cancelled.runDirectory, '/out/runs/1');
assert.equal(cancelled.createCalled, false);

const missing = runRecipe('otomate', {...base, missingSetup: true});
assert.equal(missing.error, 'setup');
assert.equal(missing.createCalled, false);
assert.ok(!missing.calledIds.includes('applyvi'));

assert.equal(isXlsx('chapter.csv'), false);
assert.equal(isXlsx('chapter.xlsx'), true);
assert.equal(isXlsx('CHAPTER.XLSX'), true);
assert.deepEqual(successActions(), ['open-folder', 'choose-another-file']);
assert.equal(canSwitchEngine(true), false);
assert.equal(canSwitchEngine(false), true);
assert.equal(languageChange().workbookPath, null);

const separated = setSheetPath({workspaces: {}, values: {}}, ['otomate', 'unity'], 'otomate', '/otomate.xlsx');
assert.equal(separated.patch.otomate.sheetPath, '/otomate.xlsx');
assert.equal(separated.patch.unity.sheetPath, '');

const python = spawnSync('python3', [path.join(__dirname, 'test_sheet_scan.py')], {encoding: 'utf8'});
if (python.status !== 0) {
  console.error(python.stdout);
  console.error(python.stderr);
  process.exit(python.status || 1);
}

console.log('receive-sheet assertions passed');
