// SOURCE_COMMIT in src/main.js has to name the commit engines/otomate is
// pinned at: the update check compares VE-ES's newest commit against it.
// 1.4.1 shipped with the submodule moved and the constant not, and told every
// user that an update was waiting for the very engine it already carried.
const {execFileSync} = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const declared = fs.readFileSync(path.join(root, 'src', 'main.js'), 'utf8')
  .match(/const SOURCE_COMMIT = '([0-9a-f]{40})'/);
if (!declared) {
  console.error('check-source-commit: SOURCE_COMMIT not found in src/main.js');
  process.exit(1);
}

let pinned;
try {
  // The index, not HEAD, so a bump that is staged but not yet committed is
  // checked too. In CI the two are the same.
  pinned = execFileSync('git', ['ls-files', '-s', 'engines/otomate'], {cwd: root, encoding: 'utf8'})
    .trim().split(/\s+/)[1];
} catch {
  console.warn('check-source-commit: not a git checkout, skipped');
  process.exit(0);
}
if (!/^[0-9a-f]{40}$/.test(pinned || '')) {
  console.error('check-source-commit: engines/otomate is not a submodule in the index');
  process.exit(1);
}
if (declared[1] !== pinned) {
  console.error(`check-source-commit: SOURCE_COMMIT ${declared[1].slice(0, 7)} `
    + `but engines/otomate is pinned at ${pinned.slice(0, 7)}`);
  process.exit(1);
}
console.log(`check-source-commit: ${pinned.slice(0, 7)}`);
