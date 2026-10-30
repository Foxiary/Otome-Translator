// Make game font: one stock .ffu per row, each given the TTF/OTF fonts to render
// from. The settings follow fonts.json, so a font made here draws like the ones
// the interface build makes.

// Where each stock file shows in Virche Evermore. Another game's files still work;
// they just show without a role.
const FONT_ROLES = {
  'sysfont.ffu': 'menu',
  'advfont1.ffu': 'option1',
  'advfont2.ffu': 'option2',
  'advfont3.ffu': 'option3',
  'advfont4.ffu': 'option4'
};
// The ffugen arguments the rows fill in. Every other one is an advanced setting.
const MAPPED_ARGS = ['--template', '--out', '--font'];

function baseName(file) { return String(file).split(/[\\/]/).pop(); }
function dirName(file) { return String(file).replace(/[\\/][^\\/]*$/, ''); }
function fontRole(file) { return FONT_ROLES[baseName(file).toLowerCase()] || null; }

// The outline radius ffugen draws for this stock file. Only a palette with a dark
// entry can draw the stock outline; those are the ADV fonts.
function strokeFor(info) { return info.outline ? 2 : 0; }

// ffugen flags for one stock file, from what font_info.py read out of it, and
// `px` from `font_info.py fit`: the largest size whose Vietnamese fits the cell.
function ffugenArgs(info, px) {
  // Keep the template's cell: the engine scales a glyph by 88/cell, so a taller
  // cell shrinks every line. glow softens the edge before the 4bpp quantise.
  const args = ['--cell', String(info.cell), '--glow', '0.4'];
  if (px) args.push('--px', String(px));
  // The ADV fonts are drawn at ~0.588, which is also what merges stacked tone marks.
  if (strokeFor(info)) args.push('--stroke', String(strokeFor(info)), '--mark-lift', '3');
  return args;
}

// The value given for `flag` in an argument list, or undefined.
function argValue(args, flag) {
  const index = args.indexOf(flag);
  return index >= 0 ? args[index + 1] : undefined;
}

// The automatic flags with the ones set by hand in their place. `auto` is
// flag/value pairs; `given` may also hold bare switches.
function withOverrides(auto, given) {
  const names = new Set(given.filter(item => /^--/.test(item)));
  const kept = [];
  for (let i = 0; i < auto.length; i += 2) if (!names.has(auto[i])) kept.push(auto[i], auto[i + 1]);
  return [...kept, ...given];
}

// The letters none of a row's fonts can draw, or null while one is still being checked.
function chainMissing(fonts) {
  if (fonts.some(font => !font.coverage || font.coverage.error)) return null;
  return [...fonts[0].coverage.missing].filter(ch => fonts.every(font => font.coverage.missing.includes(ch))).join('');
}

// The new files keep the stock names, ready for Repack CPK, in a folder of their own.
function defaultOutput(templates) {
  if (!templates.length) return '';
  const first = templates[0];
  return `${dirName(first)}${first.includes('\\') ? '\\' : '/'}vn`;
}

function samePath(a, b) {
  const clean = value => String(value).replace(/[\\/]+$/, '').replace(/\\/g, '/').toLowerCase();
  return clean(a) === clean(b);
}

// Why these choices cannot be made into fonts yet, or null when they can.
function fontJobProblem(templates, output) {
  if (!templates.length) return 'ffu';
  const names = templates.map(item => baseName(item.path).toLowerCase());
  if (new Set(names).size !== names.length) return 'duplicate';
  if (templates.some(item => !item.info || item.info.error)) return 'invalid';
  if (!templates.some(item => item.fonts.length)) return 'font';
  if (templates.some(item => item.fonts.some(font => font.coverage?.error))) return 'badFont';
  if (!String(output || '').trim()) return 'output';
  // Writing next to the stock files would replace them with the new ones.
  if (templates.some(item => samePath(dirName(item.path), output))) return 'sameFolder';
  return null;
}

// Loaded by main and the tests through require, and by the page as a plain script.
if (typeof module !== 'undefined') {
  module.exports = {FONT_ROLES, MAPPED_ARGS, baseName, fontRole, strokeFor, ffugenArgs, argValue, withOverrides,
    chainMissing, defaultOutput, fontJobProblem};
}
