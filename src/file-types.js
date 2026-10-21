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
  ['Keys', ['keys'], /\.keys\b/i]
];

function filtersFor(arg) {
  const words = `${arg.name} ${arg.help || ''}`;
  const matches = fileTypes.filter(([, , pattern]) => pattern.test(words));
  if (!matches.length) return [];
  return [
    {name: matches.map(([name]) => name).join(' / '), extensions: [...new Set(matches.flatMap(([, extensions]) => extensions))]},
    {name: 'All files', extensions: ['*']}
  ];
}

// Loaded by the tests through require, and by the page as a plain script.
if (typeof module !== 'undefined') module.exports = {filtersFor};
