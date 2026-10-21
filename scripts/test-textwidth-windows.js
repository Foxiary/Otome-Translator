// Runs scripts/test_textwidth_windows.py with whichever Python this machine calls
// python3 or python: Windows installs often have only the second.
const {spawnSync} = require('node:child_process');
const path = require('node:path');

const script = path.join(__dirname, 'test_textwidth_windows.py');
for (const python of ['python3', 'python']) {
  const result = spawnSync(python, [script], {encoding: 'utf8'});
  if (result.error || result.status === null) continue;
  process.stdout.write(result.stdout);
  process.stderr.write(result.stderr);
  process.exit(result.status);
}
console.error('test-textwidth-windows: no Python found');
process.exit(1);
