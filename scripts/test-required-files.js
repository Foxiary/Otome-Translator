const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {missingFiles} = require('../src/required-files');

const workspace = fs.mkdtempSync(path.join(os.tmpdir(), 'otm-required-'));
const touch = file => {
  fs.mkdirSync(path.dirname(path.join(workspace, file)), {recursive: true});
  fs.writeFileSync(path.join(workspace, file), '');
};
const paths = id => missingFiles(id, workspace).map(item => item.path);

try {
  // Without fonts.json the build cannot know which fonts it needs.
  assert.deepEqual(paths('build'), ['fonts.json']);

  fs.writeFileSync(path.join(workspace, 'fonts.json'), JSON.stringify({cpk: 'SYSTEM.cpk', fonts: {
    'a.ffu': {source: 'Font/A.ttf'}, 'b.ffu': {source: 'Font/B.ttf'}, 'c.ffu': {source: 'Font/A.ttf'}
  }}));
  assert.deepEqual(paths('build'), ['SYSTEM.cpk', 'Font/A.ttf', 'Font/B.ttf']);
  touch('SYSTEM.cpk'); touch('Font/A.ttf');
  assert.deepEqual(paths('build'), ['Font/B.ttf']);
  touch('Font/B.ttf');
  assert.deepEqual(paths('build'), []);

  // An accepted alternative counts as present.
  assert.deepEqual(paths('quarong'), ['STORY.cpk', 'dist/SYSTEM.cpk']);
  touch('STORY.cpk'); touch('work/out/SYSTEM.cpk');
  assert.deepEqual(paths('quarong'), []);

  assert.deepEqual(paths('chuadich'), ['work/jp/CONTENTS/STORY.cpk']);
  assert.deepEqual(paths('patch:otomate'), ['work/jp/CONTENTS/STORY.cpk']);

  // A Unity bundle is matched by its extension, whatever the game names it.
  assert.deepEqual(paths('patch:unity'), ['*.bundle, *.assets', 'text-boxes.json']);
  touch('ui_text.Bundle'); touch('text-boxes.json');
  assert.deepEqual(paths('patch:unity'), []);
  // Tools that take every file from the form need nothing here.
  assert.deepEqual(paths('cpk-list'), []);
  assert.deepEqual(missingFiles('build', ''), []);
} finally {
  fs.rmSync(workspace, {recursive: true, force: true});
}
console.log('required-files assertions passed');
