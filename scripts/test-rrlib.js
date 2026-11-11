// Runs scripts/test_rrlib.py, test_rrlib_font.py, test_rrlib_wrap.py and test_rrlib_sheet.py (engines/rrlib
// tools on synthetic files) with whichever Python this machine calls python3 or python:
// Windows installs often have only the second.
const {spawnSync} = require('node:child_process');
const path = require('node:path');

const scripts = ['test_rrlib.py', 'test_rrlib_font.py', 'test_rrlib_wrap.py', 'test_rrlib_sheet.py'].map(name => path.join(__dirname, name));
for (const python of ['python3', 'python']) {
  const probe = spawnSync(python, ['--version'], {encoding: 'utf8'});
  if (probe.error || probe.status === null) continue;
  let status = 0;
  for (const script of scripts) {
    const result = spawnSync(python, [script], {encoding: 'utf8'});
    process.stdout.write(result.stdout);
    process.stderr.write(result.stderr);
    if (result.status !== 0) status = result.status === null ? 1 : result.status;
  }
  process.exit(status);
}
console.error('test-rrlib: no Python found');
process.exit(1);
