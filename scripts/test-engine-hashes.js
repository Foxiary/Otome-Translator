// Every earlier committed version of a file the app copies into a project must
// be in its engine's src/engine-update-<id>.json, for the engines kept in this
// repository. A version missing from the list is one a project can hold and
// never be brought up from: that is how an rrlib project kept an old patch.py
// beside a new sprite.py. Otomate's list follows its submodule pin instead.
const {execFileSync} = require('node:child_process');
const path = require('node:path');

try {
  execFileSync('git', ['-C', path.resolve(__dirname, '..'), 'rev-parse', '--git-dir'], {stdio: 'ignore'});
} catch {
  console.warn('engine-hashes: not a git checkout, skipped');
  process.exit(0);
}
const {inRepoEngines, inRepoHashes, outFor} = require('./update-engine-hashes');

const problems = [];
for (const engine of inRepoEngines()) {
  const recorded = require(outFor(engine));
  for (const [file, hashes] of Object.entries(inRepoHashes(engine))) {
    const missing = hashes.filter(hash => ![].concat(recorded[file] || []).includes(hash));
    if (missing.length) problems.push(`${engine.id}: ${file} (${missing.length} earlier version${missing.length > 1 ? 's' : ''})`);
  }
}
if (problems.length) {
  console.error('engine-hashes: earlier versions missing from src/engine-update-<engine>.json:');
  for (const line of problems) console.error(`  ${line}`);
  console.error('Run: node scripts/update-engine-hashes.js');
  process.exit(1);
}
console.log('engine-hashes assertions passed');
