// Writes, for every engine file the app copies into a project folder, the
// SHA-256 of each earlier version of it. src/engine-copy.js replaces a
// project's copy only when it matches one of these (or what the app itself
// wrote there last), so an untouched file is brought up to date from any
// earlier version while a file the user edited is left alone.
//
//     node scripts/update-engine-hashes.js
//
//   src/engine-update.json        Otomate, from the history of its submodule
//                                 (VE-ES); run after moving the engines/otomate pin
//   src/engine-update-<id>.json   the engines kept in this repository (rrlib,
//                                 unity), from this repository's history; run
//                                 after changing any file they copy - npm run
//                                 check fails until you do (test-engine-hashes.js)
//
// One hash per file was not enough: a project last opened with an in-between
// build kept that build's textwidth.py beside a newer applyvi.py, and the two
// no longer imported each other. An empty list was worse: rrlib projects kept
// the patch.py they started with beside a new sprite.py that imports from it.
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const {execFileSync} = require('node:child_process');

const root = path.resolve(__dirname, '..');
const SKIP = new Set(['__pycache__', '.git', '.DS_Store']);

const gitIn = cwd => (...args) => execFileSync('git', ['-C', cwd, ...args], {encoding: 'buffer', maxBuffer: 1 << 28});
const sha256 = data => crypto.createHash('sha256').update(data).digest('hex');
const lfHash = data => sha256(Buffer.from(data.toString('latin1').split('\r\n').join('\n'), 'latin1'));

// Hashes of every committed version of gitPath other than `current`.
function earlierVersions(git, gitPath, current, rev = []) {
  const commits = git('log', '--format=%H', ...rev, '--', gitPath).toString().trim().split('\n').filter(Boolean);
  const seen = new Set();
  for (const commit of commits) {
    let data;
    try { data = git('show', `${commit}:${gitPath}`); } catch { continue; }    // deleted in that commit
    const hash = sha256(data);
    if (hash !== current) seen.add(hash);
  }
  return seen;
}

function otomateHashes() {
  const engine = path.join(root, 'engines', 'otomate');
  const out = path.join(root, 'src', 'engine-update.json');
  // What engines.js copies for Otomate (its `copy` list), as git paths.
  const COPIED = ['tools/', 'build.py', 'fonts.json', 'DICH.md', 'CLAUDE.md', 'Font/'];
  const copied = file => COPIED.some(entry => entry.endsWith('/') ? file.startsWith(entry) : file === entry);
  const git = gitIn(engine);
  const previous = JSON.parse(fs.readFileSync(out, 'utf8'));
  const files = git('ls-tree', '-r', '--name-only', 'HEAD').toString().trim().split('\n').filter(copied);
  const hashes = {};
  for (const file of files) {
    const seen = earlierVersions(git, file, sha256(git('show', `HEAD:${file}`)), ['HEAD']);
    if (seen.size) hashes[file] = [...seen];
  }
  // requirements.txt is the app's own file; keep whatever was recorded for it.
  if (previous['requirements.txt']) hashes['requirements.txt'] = [].concat(previous['requirements.txt']);
  return {out, hashes};
}

// The engines whose files live in this repository rather than in a submodule.
function inRepoEngines() {
  const {engines} = require('../src/engines');
  const git = gitIn(root);
  return engines.filter(engine => {
    const first = git('ls-files', '-s', `engines/${engine.dir}`).toString().split('\n')[0];
    return first && !first.startsWith('160000');
  });
}

// {path in the project: [earlier hashes]} for one in-repository engine: every
// committed version of each file it copies that differs from the working tree.
function inRepoHashes(engine) {
  const git = gitIn(root);
  const base = `engines/${engine.dir}`;
  const files = [];
  const walk = (abs, rel) => {
    if (!fs.existsSync(abs) || SKIP.has(path.basename(abs))) return;
    if (fs.statSync(abs).isDirectory()) {
      for (const name of fs.readdirSync(abs).sort()) walk(path.join(abs, name), `${rel}/${name}`);
    } else files.push([rel, abs, `${base}/${rel}`]);
  };
  for (const name of engine.copy) walk(path.join(root, base, name), name);
  files.push(['requirements.txt', path.join(root, 'requirements.txt'), 'requirements.txt']);
  const hashes = {};
  for (const [rel, abs, gitPath] of files) {
    const seen = earlierVersions(git, gitPath, lfHash(fs.readFileSync(abs)));
    if (seen.size) hashes[rel] = [...seen].sort();
  }
  return hashes;
}

const outFor = engine => path.join(root, 'src', `engine-update-${engine.id}.json`);

if (require.main === module) {
  const write = (out, hashes) => {
    fs.writeFileSync(out, `${JSON.stringify(hashes, null, 2)}\n`);
    const versions = Object.values(hashes).reduce((sum, list) => sum + list.length, 0);
    console.log(`${path.basename(out)}: ${Object.keys(hashes).length} files, ${versions} earlier versions`);
  };
  const otomate = otomateHashes();
  write(otomate.out, otomate.hashes);
  for (const engine of inRepoEngines()) write(outFor(engine), inRepoHashes(engine));
}

module.exports = {inRepoEngines, inRepoHashes, outFor};
