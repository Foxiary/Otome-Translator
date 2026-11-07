const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {syncEngineFiles, sha256} = require('../src/engine-copy');

const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'engine-copy-'));
try {
  const engine = path.join(tmp, 'engine');
  const project = path.join(tmp, 'project');
  const write = (file, text) => { fs.mkdirSync(path.dirname(file), {recursive: true}); fs.writeFileSync(file, text); };
  const read = rel => fs.readFileSync(path.join(project, rel), 'utf8');
  write(path.join(engine, 'tools', 'patch.py'), 'v1\n');
  write(path.join(engine, 'tools', 'rson.py'), 'r1\n');
  write(path.join(engine, 'tools', '__pycache__', 'patch.pyc'), 'x');
  write(path.join(engine, 'README.md'), 'readme 1\n');
  const entries = [[path.join(engine, 'tools'), 'tools'], [path.join(engine, 'README.md'), 'README.md'],
    [path.join(engine, 'missing.md'), 'missing.md']];

  // A new project gets every file, never __pycache__, and a record of what was written.
  let run = syncEngineFiles(project, entries);
  assert.deepEqual(run.added.sort(), ['README.md', 'tools/patch.py', 'tools/rson.py']);
  assert.ok(!fs.existsSync(path.join(project, 'tools', '__pycache__')));
  assert.equal(run.record['tools/patch.py'], sha256('v1\n'));
  let record = run.record;

  // The engine moves on: untouched copies follow it, an edited one stays.
  write(path.join(engine, 'tools', 'patch.py'), 'v2\n');
  write(path.join(engine, 'tools', 'rson.py'), 'r2\n');
  write(path.join(project, 'tools', 'rson.py'), 'r1 with my fix\n');
  run = syncEngineFiles(project, entries, {}, record);
  assert.deepEqual(run.updated, ['tools/patch.py']);
  assert.deepEqual(run.kept, ['tools/rson.py']);
  assert.equal(read('tools/patch.py'), 'v2\n');
  assert.equal(read('tools/rson.py'), 'r1 with my fix\n');
  assert.equal(run.record['tools/rson.py'], sha256('r1\n'));       // still what the app wrote
  record = run.record;

  // A project with no record (copied by an older app) is brought up from a
  // listed earlier version, CRLF checkouts of it included; anything else is kept.
  const other = path.join(tmp, 'older-project');
  write(path.join(other, 'tools', 'patch.py'), 'v1\r\n');
  write(path.join(other, 'tools', 'rson.py'), 'r0\n');
  write(path.join(other, 'README.md'), 'readme 1\n');
  run = syncEngineFiles(other, entries, {'tools/patch.py': [sha256('v1\n')]});
  assert.deepEqual(run.updated, ['tools/patch.py']);
  assert.deepEqual(run.kept, ['tools/rson.py']);
  assert.equal(fs.readFileSync(path.join(other, 'tools', 'patch.py'), 'utf8'), 'v2\n');
  // A file already current is recorded, so the next change reaches it.
  assert.equal(run.record['README.md'], sha256('readme 1\n'));
  assert.equal(run.record['tools/rson.py'], undefined);

  // Nothing changed: nothing to do.
  run = syncEngineFiles(project, entries, {}, record);
  assert.deepEqual([run.added, run.updated], [[], []]);
} finally {
  fs.rmSync(tmp, {recursive: true, force: true});
}
console.log('engine-copy assertions passed');
