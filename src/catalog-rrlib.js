// Tools of the rrlib engine (engines/rrlib/tools), the engine Matsurika no Kei
// -kEi- Tenmei Iniden runs on. Ids carry an `rrlib-` prefix so they never collide
// with the other catalogs in saved form values.
const A = (name, kind = 'text', help = '', optional = false) => ({name, kind, help, positional: true, required: !optional});
const V = (name, kind = 'text', help = '', required = false, repeat = false) => ({name, kind, help, required, repeat});
const B = (name, help = '') => ({name, kind: 'bool', help});
const T = (id, group, title, description, script, prefix, args, note = '') => ({id: `rrlib-${id}`, group, title, description, script, prefix, args, note});

const KEYS = V('--keys', 'file', 'prod.keys; defaults to ~/.switch/prod.keys');
const EXE = V('--exe', 'file', 'Patched exefs/main, to follow the read redirects it carries');

const SCREEN = A('screen', 'file', 'A screen\'s .memfs under romfs/spec_win/ssdata, e.g. ttlm_nam.memfs (title menu); its data file must sit next to it');

const groups = ['Dump', 'Inspect', 'Patch', 'Sheets', 'Images'];
const symbols = {Dump: '⇣', Inspect: '◎', Patch: '◈', Sheets: '▦', Images: '▣'};
const summaries = {
  Dump: 'Take the whole game, or single files, out of your .nsp or .xci, using your prod.keys.',
  Inspect: 'Look inside the script index, the script archive and the scripts.',
  Patch: 'Write the translation sheet into the game, check a Vietnamese patch against the Japanese scripts and rebuild it.',
  Sheets: 'Turn the translation sheet into a list of tag fixes.',
  Images: 'Menu labels, buttons and help lines are painted into textures: take them out as images, redraw them and put them back.'
};

const tools = [
  // Runs in the app (src/game-extract.js), the extractor the project set-up uses.
  {...T('extract', 'Dump', 'Take out the whole game', 'Copies every data file (RomFS) and the program files (ExeFS) out of the game file (.nsp or .xci) into romfs/ and exefs/ inside the folder you choose, the same as setting up a project from scratch. About 5.7 GB for this game, mostly voice.', null, [],
    [A('game', 'file', 'Game file (.nsp or .xci)'), A('output folder', 'dir', 'An empty folder, or one without romfs/ and exefs/ yet'), V('--keys', 'file', 'prod.keys; defaults to the one chosen before, or ~/.switch/prod.keys')],
    'Update files are not supported; use the base game. Stop removes what was taken out so far.'), builtin: 'extract-game'},
  T('romfs', 'Dump', 'Take chosen files out of the game', 'Copies chosen data files (for example common/script.memfs and common/script.membody) out of the game file (.nsp), without unpacking all 5 GB of it. Tick List to see every file name first.', 'tools/nsp.py', ['romfs'],
    [A('NSP', 'file'), A('output folder', 'dir'), A('path', 'text', 'One file path inside the game, e.g. common/script.memfs; * matches any part', true), B('--list', 'Only list the file names'), KEYS],
    'Update files are not supported; use the base game.'),
  T('exefs', 'Dump', 'Take out the game\'s program', 'Copies the game\'s program files (main, sdk, ...) out of the game file (.nsp).', 'tools/nsp.py', ['exefs'],
    [A('NSP', 'file'), A('output folder', 'dir'), KEYS]),

  T('memfs-list', 'Inspect', 'List the scripts', 'Shows every script in script.memfs with where it sits in script.membody, which copy the game really loads, and the chunks nothing points at. Nothing is changed.', 'tools/memfs.py', ['list'],
    [A('memfs', 'file', 'script.memfs'), A('membody', 'file', 'script.membody'), EXE]),
  T('memfs-unpack', 'Inspect', 'Unpack the scripts', 'Saves every script of the archive as a .tat file you can open with the script tools.', 'tools/memfs.py', ['unpack'],
    [A('memfs', 'file', 'script.memfs'), A('membody', 'file', 'script.membody'), A('output folder', 'dir'), EXE]),
  T('memfs-check', 'Inspect', 'Check the script archive', 'Checks that every script in the archive opens and rebuilds byte for byte. Use it when you suspect a broken file.', 'tools/memfs.py', ['check'],
    [A('memfs', 'file', 'script.memfs'), A('membody', 'file', 'script.membody'), EXE]),
  T('rson-dump', 'Inspect', 'Show the script index', 'Prints the script index (script.memfs) as text: every file name with its place and size.', 'tools/rson.py', ['dump'],
    [A('file', 'file', 'script.memfs')]),
  T('rson-check', 'Inspect', 'Check the script index', 'Reads the script index and writes it back; the copy has to match the file byte for byte.', 'tools/rson.py', ['check'],
    [A('file', 'file', 'script.memfs')]),
  T('kuv-strings', 'Inspect', 'Show a script\'s lines', 'Lists every line of one script (.tat), numbered as the translation sheet numbers them.', 'tools/kuv.py', ['strings'],
    [A('file', 'file', '.tat script'), V('--grep', 'text', 'Only lines containing this text'), V('--from', 'number', 'First line number'), V('--to', 'number', 'Last line number')]),
  T('kuv-calls', 'Inspect', 'Show a script\'s commands', 'Lists the commands of one script (.tat) with the lines they show, such as NameMess, GuideMess, KW and WinClear.', 'tools/kuv.py', ['calls'],
    [A('file', 'file', '.tat script'), V('--grep', 'text', 'Only commands mentioning this text'), V('--from', 'number', 'First line number'), V('--to', 'number', 'Last line number')]),
  T('kuv-check', 'Inspect', 'Check a script', 'Checks that one script (.tat) opens and rebuilds byte for byte.', 'tools/kuv.py', ['check'],
    [A('file', 'file', '.tat script')]),
  T('exehook', 'Inspect', 'Find redirects in the program', 'Lists the script reads a patched program file (exefs/main) sends elsewhere. An earlier patch used them for three prologue scripts.', 'tools/exehook.py', [],
    [A('main', 'file', 'exefs/main')]),

  T('apply', 'Patch', 'Write the sheet into the game', 'Writes the translation sheet (.xlsx) into script.memfs and script.membody: each line is wrapped and encoded for the mod\'s Vietnamese font, with its tags exactly as the sheet has them, and the result is checked. Check the tags with Check a patch. Lines the sheet has no row for (names, choices) keep the mod\'s text.', 'tools/applysheet.py', [],
    [V('--sheet', 'file', 'Translation sheet (.xlsx)', true), V('--jp', 'dir', 'Folder with the Japanese script.memfs and script.membody', true),
      V('--mod', 'dir', 'Vietnamese mod folder (with romfs/ and exefs/): its font, program and names are kept', true), V('--out', 'dir', 'Output folder', true), EXE,
      V('--report', 'save', 'CSV of the rows not written and the lines to look at'), V('--map', 'save', 'Save the font encoding learnt from the mod (.json)'),
      V('--use-map', 'file', 'Read the font encoding from a saved .json instead'), B('--apply', 'Write the files')],
    'Runs as a dry run first and asks before writing. A row left out keeps the mod\'s line; the report says why.'),
  T('audit', 'Patch', 'Check a patch', 'Compares a Vietnamese patch with the Japanese scripts: lost position, name and pause tags, lines hidden off-screen, broken headers. Nothing is changed.', 'tools/audit.py', [],
    [V('--jp', 'dir', 'Folder with the Japanese script.memfs and script.membody', true), V('--patch', 'dir', 'Vietnamese mod folder (with romfs/ and exefs/)', true), EXE, V('--csv', 'save', 'Every finding with its Japanese and Vietnamese text')]),
  T('patch', 'Patch', 'Rebuild the patch', 'Rebuilds script.memfs and script.membody: puts the lost #P position tags back, keeps lines Japanese draws off-screen visible, points every script straight at its data and checks the result.', 'tools/patch.py', [],
    [V('--jp', 'dir', 'Folder with the Japanese script.memfs and script.membody', true), V('--patch', 'dir', 'Vietnamese mod folder (with romfs/ and exefs/)', true), V('--out', 'dir', 'Output folder', true), EXE,
      B('--no-restore', 'Only rebuild, do not touch #P'), B('--keep-offscreen', 'Keep #P tags that put a line off-screen'), V('--report', 'save', 'CSV of every line touched'), B('--apply', 'Write the files')],
    'Runs as a dry run first and asks before writing. Try the result in the game before you share it.'),

  T('sheetfix', 'Sheets', 'Tag fixes for the sheet', 'Reads the translation sheet (.xlsx) and writes a workbook of fixes, by tab and row: #P tags to add, lines to leave untagged, and #T / #KW lines to fix by hand.', 'tools/sheetfix.py', [],
    [V('--sheet', 'file', 'Translation sheet (.xlsx)', true), V('--jp', 'dir', 'Folder with the Japanese script.memfs and script.membody', true), V('--out', 'save', 'Workbook to write (.xlsx)', true)]),

  T('sprite-export', 'Images', 'See and take out a screen\'s images', 'Lists the textures of one screen and every piece cut from them, named after the part that draws it (the menu label 新しく始める is mat_ttlm_com01_off, its help line mat_ttlm_com01_setu), with place and size. Choose a folder and each texture and each piece is also saved there as an image, plus cells.csv with the same list; redraw the pieces you want in any image editor, keeping their size.', 'tools/sprite.py', ['export'],
    [SCREEN, A('output folder', 'dir', 'Where the images go; leave it empty to only see the list', true)]),
  T('sprite-import', 'Images', 'Put redrawn images back', 'Reads the folder made by "See and take out a screen\'s images": every image that differs from the game is pasted back at its place, the screen\'s files are rebuilt and checked, untouched files byte for byte.', 'tools/sprite.py', ['import'],
    [SCREEN, A('image folder', 'dir', 'The folder you redrew, as it was taken out (file names unchanged)'),
      V('--out', 'dir', 'Where the rebuilt pair goes: romfs/spec_win/ssdata inside your mod', true), B('--apply', 'Write the files')],
    'Runs as a dry run first and asks before writing. Each image must keep its size; nothing outside it is drawn.'),
  T('sprite-check', 'Images', 'Check a screen\'s files', 'Rebuilds one screen unchanged, which has to match byte for byte, and packs every texture the tools can write again.', 'tools/sprite.py', ['check'],
    [SCREEN])
];

module.exports = {tools, groups, symbols, summaries};
