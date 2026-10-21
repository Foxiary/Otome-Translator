// Writes src/engine-update.json: for every engine file the app copies into a
// project folder, the SHA-256 of each earlier version of it in VE-ES's history.
// main.js replaces a project's copy only when it matches one of these, so an
// untouched file is brought up to date from any earlier version while a file
// the user edited is left alone. Run after moving the engines/otomate pin:
//
//     node scripts/update-engine-hashes.js
//
// One hash per file was not enough: a project last opened with an in-between
// build kept that build's textwidth.py beside a newer applyvi.py, and the two
// no longer imported each other.
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const {execFileSync} = require('node:child_process');

const root = path.resolve(__dirname, '..');
const engine = path.join(root, 'engines', 'otomate');
const out = path.join(root, 'src', 'engine-update.json');
// What engines.js copies for Otomate (its `copy` list), as git paths.
const COPIED = ['tools/', 'build.py', 'fonts.json', 'DICH.md', 'CLAUDE.md', 'Font/'];

const git = (...args) => execFileSync('git', ['-C', engine, ...args], {encoding: 'buffer', maxBuffer: 1 << 28});
const sha256 = data => crypto.createHash('sha256').update(data).digest('hex');
const copied = file => COPIED.some(entry => entry.endsWith('/') ? file.startsWith(entry) : file === entry);

const previous = JSON.parse(fs.readFileSync(out, 'utf8'));
const files = git('ls-tree', '-r', '--name-only', 'HEAD').toString().trim().split('\n').filter(copied);
const hashes = {};
for (const file of files) {
  const current = sha256(git('show', `HEAD:${file}`));
  const commits = git('log', '--format=%H', 'HEAD', '--', file).toString().trim().split('\n').filter(Boolean);
  const seen = new Set();
  for (const commit of commits) {
    let data;
    try { data = git('show', `${commit}:${file}`); } catch { continue; }    // deleted in that commit
    const hash = sha256(data);
    if (hash !== current) seen.add(hash);
  }
  if (seen.size) hashes[file] = [...seen];
}
// requirements.txt is the app's own file; keep whatever was recorded for it.
if (previous['requirements.txt']) hashes['requirements.txt'] = [].concat(previous['requirements.txt']);
fs.writeFileSync(out, `${JSON.stringify(hashes, null, 2)}\n`);
const versions = Object.values(hashes).reduce((sum, list) => sum + list.length, 0);
console.log(`engine-update.json: ${Object.keys(hashes).length} files, ${versions} earlier versions`);
