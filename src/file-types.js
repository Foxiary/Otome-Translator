// File dialog filters, read from the words an argument already uses to describe itself.
const fileTypes = [
  ['Excel workbook', ['xlsx'], /xlsx|workbook|\bsheet\b|incoming|\bmerged\b|batch/i],
  ['CSV', ['csv'], /\bcsv\b/i],
  ['PNG image', ['png'], /\bpng\b/i],
  ['FFU font', ['ffu'], /\bffu\b/i],
  ['Font', ['ttf', 'otf', 'ttc'], /\bttf\b|\bttc\b/i],
  ['CPK', ['cpk'], /\bcpk\b|\barchive\b/i],
  ['TID', ['tid'], /\btid\b/i],
  ['DAT', ['dat'], /\bdat\b/i],
  ['GBIN/GSTR', ['gbin', 'gstr'], /\bgbin\b|\bgstr\b/i],
  ['NSP', ['nsp'], /\bnsp\b/i],
  ['XCI', ['xci'], /\bxci\b/i],
  ['Keys', ['keys'], /\.keys\b/i],
  ['MemFS', ['memfs'], /\.memfs\b/i],
  ['MemBody', ['membody'], /\.membody\b/i],
  ['TAT script', ['tat'], /\.tat\b/i]
];

function wordsOf(arg) { return `${arg.name} ${arg.help || ''}`; }

function filtersFor(arg) {
  const matches = fileTypes.filter(([, , pattern]) => pattern.test(wordsOf(arg)));
  if (!matches.length) return [];
  const specific = {name: matches.map(([name]) => name).join(' / '), extensions: [...new Set(matches.flatMap(([, extensions]) => extensions))]};
  // A screen opens only when its data file sits beside the .memfs, so the dialog
  // lists that type and nothing else.
  if (companionFor(arg)) return [specific];
  return [specific, {name: 'All files', extensions: ['*']}];
}

// The extension that must sit beside the chosen file, or '' when the file stands alone.
function companionFor(arg) {
  return /\.memfs\b/i.test(wordsOf(arg)) && /next to it/i.test(wordsOf(arg)) ? 'membody' : '';
}

// Where a screen's files live, under the project folder and under game/.
function startCandidates(arg) {
  if (!companionFor(arg) || !/romfs\/spec_win\/ssdata/.test(arg.help || '')) return [];
  return ['game/romfs/spec_win/ssdata', 'romfs/spec_win/ssdata'];
}

// The sibling path a chosen file would need, or '' when the name has no extension to swap.
function companionPath(file, extension) {
  if (typeof file !== 'string' || !/^[a-z0-9]+$/i.test(extension || '')) return '';
  const slash = Math.max(file.lastIndexOf('/'), file.lastIndexOf('\\'));
  const base = file.slice(slash + 1);
  const dot = base.lastIndexOf('.');
  if (dot <= 0) return '';
  const other = `${base.slice(0, dot)}.${extension}`;
  if (other.toLowerCase() === base.toLowerCase()) return '';
  return file.slice(0, slash + 1) + other;
}

// Loaded by the tests through require, and by the page as a plain script.
if (typeof module !== 'undefined') module.exports = {filtersFor, companionFor, startCandidates, companionPath};
