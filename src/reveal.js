// Where a finished run left its files, taken from the arguments the tool already has.
// Empty when the run only printed, or was a dry run that has not written yet.
const SIDE_OUTPUTS = new Set(['--report', '--csv', '--map', '--preview', '--cpk']);

function filled(values, name) {
  return String(values?.[name] ?? '').trim();
}

function primaryOutput(arg) {
  if (!arg || (arg.kind !== 'dir' && arg.kind !== 'save')) return false;
  const name = String(arg.name).toLowerCase();
  return name === 'output' || name.startsWith('output ') || name === '--out' || name === '--out-dir';
}

function outputTarget(tool, values) {
  if (!tool || !values) return '';
  const args = tool.args || [];
  if (args.some(arg => arg.name === '--apply') && !values['--apply']) return '';
  if (values['--list'] || values['--dry-run']) return '';
  if (args.some(arg => arg.name === '--build') && !values['--build']) return '';
  const primary = args.find(arg => primaryOutput(arg) && filled(values, arg.name));
  if (primary) return filled(values, primary.name);
  const side = args.find(arg => SIDE_OUTPUTS.has(arg.name) && filled(values, arg.name));
  return side ? filled(values, side.name) : '';
}

// The image a run says it drew, as font.py gen --preview prints it on a dry
// run: "anh xem truoc -> <path>", maybe followed by two spaces and a note in
// brackets. The dialog that asks before writing shows it.
function previewOf(output) {
  return String(output || '').match(/^anh xem truoc -> (.+?)(?: {2}\(.*\))?\s*$/m)?.[1] || '';
}

if (typeof module !== 'undefined') module.exports = {outputTarget, previewOf};
