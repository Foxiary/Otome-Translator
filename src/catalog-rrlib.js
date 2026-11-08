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

const groups = ['Dump', 'Inspect', 'Patch', 'Sheets', 'Images', 'Executable', 'Fonts'];
const symbols = {Dump: '⇣', Inspect: '◎', Patch: '◈', Sheets: '▦', Images: '▣', Executable: '⌘', Fonts: 'Ａ'};
const summaries = {
  Dump: 'Take the whole game, or single files, out of your .nsp or .xci, using your prod.keys.',
  Inspect: 'Look inside the script index, the script archive and the scripts.',
  Patch: 'Write the translation sheet into the game, check a Vietnamese patch against the Japanese scripts and rebuild it.',
  Sheets: 'Turn the translation sheet into a list of tag fixes.',
  Images: 'Menu labels, buttons and help lines are painted into textures: take them out as images, redraw them and put them back.',
  Executable: 'Text built into the program file (exefs/main): dialog questions, quick save messages, button help, glossary and chapter titles.',
  Fonts: 'Redraw the Latin and Vietnamese letters of the game\'s fonts from a font file of your choice, and look at the result.'
};

const FONT = A('font', 'file', 'A font under romfs/spec_win/font, e.g. standard.font.memfs');
// The help names the source font's type and not the game file it is for: the
// file dialog takes its filter from these words (src/file-types.js).
const FAMILY = name => V(`--font-${name}`, 'file', `Font file (.ttf, .otf, .ttc) used only for the ${name} font and its outline, tried before Font`);
const SIZE = name => V(`--px-${name}`, 'number', `Letter size in pixels for the ${name} font and its outline only, over Size; the dry run prints the size that fits H and how much wider the letters come out`);
const FAMILIES = ['standard', 'extra', 'extra2', 'extra3', 'ui'].flatMap(name => [FAMILY(name), SIZE(name)]);

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

  // Two steps, the second filled in from the first: `follows` names the tool
  // whose last run gives these fields their values (renderer.js), so the
  // folder step 1 saved to is the folder step 2 reads.
  T('sprite-export', 'Images', 'Take a screen\'s images out', 'Menu labels, buttons and help lines are painted into images. Saves every piece of one screen as its own image in an empty folder, named after the part that draws it (新しく始める on the title menu is mat_ttlm_com01_off, its help line mat_ttlm_com01_setu), plus a cells_<screen>.csv with where each one sits. Redraw the pieces you translate in that folder, then use "Put redrawn images back": the app fills in this screen and folder there.', 'tools/sprite.py', ['export'],
    [SCREEN, A('output folder', 'dir', 'Best an empty folder: the images are saved here. If it already holds images, the app asks before replacing them, and copies the ones you redrew to .bak first. Leave it empty to only see the list', true),
      B('--overwrite', 'Replace images already in the folder'),
      // Set by the app from the keep-or-replace questions, never typed.
      {...V('--keep', 'text', 'Files already in the folder to leave as they are, one per line', false, true), hidden: true}]),
  {...T('sprite-import', 'Images', 'Put redrawn images back', 'Reads the folder "Take a screen\'s images out" saved to, after you redrew pieces in it: each piece that differs from the game is pasted back at its place. A piece drawn bigger, for a longer Vietnamese label, gets an empty place in the same image, and the game still draws it centred where the old one was. The screen is rebuilt into Out and checked, untouched files byte for byte. Once step 1 has run, the screen and the folder are filled in for you.', 'tools/sprite.py', ['import'],
    [SCREEN, A('image folder', 'dir', 'The folder step 1 saved to (filled in for you), with the pieces you redrew saved over the same files: same name, PNG. A piece may be bigger than before if its text needs the room'),
      V('--out', 'dir', 'Where the rebuilt screen is written: romfs/spec_win/ssdata inside your mod. An older file there is first copied to .bak beside it', true), B('--apply', 'Write the files')]),
  follows: {tool: 'rrlib-sprite-export', fields: {screen: 'screen', 'image folder': 'output folder'}}},
  T('sprite-check', 'Images', 'Check a screen\'s files', 'Rebuilds one screen unchanged, which has to match byte for byte, and packs every texture the tools can write again.', 'tools/sprite.py', ['check'],
    [SCREEN]),

  // Two steps like the images: the list step 1 saves is the list step 2 reads.
  T('exetext-export', 'Executable', 'List the program\'s text', 'Dialog questions (前回と同じ名前を使用します｡), quick save messages, button help, glossary entries and chapter titles are built into the program file (exefs/main), not the scripts: the translation sheet has no rows for them, and the Vietnamese font shows them as wrong letters. Saves every Japanese line of the program to a list (.csv) with an empty vi_text column to translate; the note column says what to keep (%d, {B}, line breaks). Then use "Write the program\'s text into the game": the app fills in this program and list there.', 'tools/exetext.py', ['export'],
    [A('main', 'file', 'exefs/main of your mod (or the Japanese one)'),
      A('list', 'save', 'Where to save the list (.csv; .xlsx needs openpyxl). Leave it empty to only see it', true),
      V('--map', 'file', 'Font encoding (.json): on a program this tool already wrote, fills vi_text with what is in it')]),
  {...T('exetext-import', 'Executable', 'Write the program\'s text into the game', 'Writes the vi_text column of the list into exefs/main, encoded for the mod\'s Vietnamese font, and checks the result. Each translation goes to a new area at the end of the program and everything that pointed at the Japanese line points at it instead, so a translation may be longer than the Japanese. To change translations, run it again on the main it wrote: it starts from the original each time.', 'tools/exetext.py', ['import'],
    [A('main', 'file', 'exefs/main of your mod, translated before or not (filled in from step 1)'),
      A('list', 'file', 'The list from step 1 with vi_text filled in (.csv, or .xlsx with openpyxl)'),
      V('--map', 'file', 'Font encoding (.json), saved by "Write the sheet into the game" (its Map field)', true),
      V('--out', 'dir', 'Where the new main goes: exefs inside your mod. An older main there is first copied to main.bak', true),
      V('--report', 'save', 'CSV of every row and what was done with it'), B('--apply', 'Write the file')],
    'Runs as a dry run first and asks before writing. A line the program builds some other way keeps its Japanese: try each screen in the game.'),
  follows: {tool: 'rrlib-exetext-export', fields: {main: 'main', list: 'list'}}},
  T('exetext-check', 'Executable', 'Check the program\'s text', 'Lists the Japanese lines found in exefs/main and what points at them, then moves them all to the new area unchanged and checks that every pointer still reads the same line and that undoing it gives the program back byte for byte. Nothing is written.', 'tools/exetext.py', ['check'],
    [A('main', 'file', 'exefs/main')]),

  T('font-gen', 'Fonts', 'Make the Vietnamese font', 'Redraws the ASCII and Vietnamese letters of every font in the Japanese font folder from the font file you choose (.ttf/.otf), sized so they match the game\'s letters, and builds the outline fonts from them. Kana and kanji stay as they are. With Map, each Vietnamese letter is drawn on the kana code the mod\'s scripts use for it, so the scripts built today show the new typeface; letters the map lacks (Ể, Ổ) get codes of their own, and Map out saves the result for "Write the sheet into the game" (Use map) and the program text tools.', 'tools/font.py', ['gen'],
    [V('--template', 'dir', 'The Japanese romfs/spec_win/font folder', true), V('--out', 'dir', 'romfs/spec_win/font inside your mod. An older file there is first copied to .bak beside it', true),
      V('--font', 'file', 'Font file with Vietnamese letters (.ttf, .otf; file.ttc#1 picks a face). Repeat for fallbacks', true, true),
      ...FAMILIES,
      // Required here: today's scripts carry Vietnamese on kana codes, and a font
      // built without the map leaves those cells Japanese (the game then shows
      // ば for ộ). Unicode-only builds stay possible from the command line.
      V('--map', 'file', 'Font encoding (.json), the file the Map field saves when writing the translation into the game. Without it the Vietnamese letters of today\'s scripts show as kana', true),
      V('--map-out', 'save', 'Save the encoding of the new font (.json), for Use map'),
      V('--px', 'number', 'Letter size in pixels for every font; empty fits the height of H to each of the game\'s fonts'),
      V('--chars', 'text', 'More characters to draw under their own code'),
      B('--no-latin', 'Keep the game\'s ASCII letters, draw only the Vietnamese ones'),
      V('--outline-radius', 'number', 'Outline width in pixels; empty measures it on the Japanese fonts'), B('--apply', 'Write the files')],
    'Runs as a dry run first and asks before writing. It says when the letters come out wider than the game\'s, which can push long lines out of the box: try the result in the game.'),
  T('font-preview', 'Fonts', 'Preview a font', 'Draws your text with the game\'s fonts into an image, the way the game lays it out. Choose one font file, or the font folder to draw the text with the four fonts of the settings screen (一 二 三 四), one under another, each with its outline. Use it to look at the fonts before trying them in the game.', 'tools/font.py', ['preview'],
    [A('font', 'path', 'A font under romfs/spec_win/font, e.g. standard.font.memfs, or the folder itself for the four fonts of the settings screen (一 二 三 四), each with its outline'),
      A('text', 'text', 'Text to draw; \\n starts a new line'), A('image', 'save', 'Image to save (.png)'),
      V('--outline', 'file', 'The matching outline font, e.g. standard_outline.font.memfs; not needed with a folder'), V('--map', 'file', 'Font encoding (.json): encode the text with it first, as the scripts are; needed for fonts built with a Map')]),
  T('font-export', 'Fonts', 'Take a font\'s images out', 'Saves every texture of one font as a PNG and a glyphs.tsv listing each character with its place and width. Nothing is changed.', 'tools/font.py', ['export'],
    [FONT, A('output folder', 'dir')]),
  T('font-check', 'Fonts', 'Check the fonts', 'Reads every font in a folder and writes it back unchanged; each copy has to match its file byte for byte.', 'tools/font.py', ['check'],
    [A('folder', 'dir', 'A romfs/spec_win/font folder')])
];

module.exports = {tools, groups, symbols, summaries};
