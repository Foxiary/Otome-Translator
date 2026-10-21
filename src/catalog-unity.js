// Tools of the Unity engine (engines/unity/tools). Ids carry a `unity-` prefix so
// they never collide with the Otomate catalog in saved form values.
const A = (name, kind = 'text', help = '', optional = false) => ({name, kind, help, positional: true, required: !optional});
const V = (name, kind = 'text', help = '', required = false, repeat = false) => ({name, kind, help, required, repeat});
const B = (name, help = '') => ({name, kind: 'bool', help});
const T = (id, group, title, description, script, prefix, args, note = '') => ({id: `unity-${id}`, group, title, description, script, prefix, args, note});

const DRY = 'Only shows what would change until you tick Apply. If you save over the original file, a .bak backup is kept.';
const UV = V('--unity-version', 'text', 'Fallback Unity version for files that carry none, e.g. 2021.3.0f1');
const PACKER = V('--packer', 'text', 'auto (lz4 for bundles, none for .assets), lz4, lzma, none, original');

const groups = ['Dump', 'Inspect', 'Text', 'Layout', 'Fonts', 'Executable', 'Release'];
const symbols = {Dump: '⇣', Inspect: '◎', Text: '▦', Layout: '▭', Fonts: 'Aa', Executable: '⌘', Release: '◈'};
const summaries = {
  Dump: 'Copy the game’s files out of your .nsp, using your prod.keys.',
  Inspect: 'See what a Unity file holds before you change it.',
  Text: 'Translate the game’s text through a sheet, or fix a word directly.',
  Layout: 'Make translated text fit its box: size, wrapping, shrink to fit.',
  Fonts: 'Add Vietnamese letters to the game’s fonts, or swap a font.',
  Executable: 'Change text built into the game’s code. For advanced users.',
  Release: 'Package the mod for players.'
};

const tools = [
  T('exefs', 'Dump', 'Take out the game\'s program', 'Copies the game\'s program files (main) out of a game or update file (.nsp), so text in the code can be patched later.', 'tools/switchfs.py', ['exefs'],
    [A('NSP', 'file'), A('output folder', 'dir'), V('--keys', 'file', 'prod.keys; defaults to the one in Ryujinx/system')]),
  T('romfs', 'Dump', 'Extract game files', 'Copies all the game\'s data files out of a game or DLC file (.nsp). These are the files you translate.', 'tools/switchfs.py', ['romfs'],
    [A('NSP', 'file'), A('output folder', 'dir'), V('--keys', 'file', 'prod.keys; defaults to the one in Ryujinx/system'), B('--list', 'Only list the files'), V('--show', 'number', 'How many file names to print')],
    'Update files are not supported; use the base game.'),
  T('nso', 'Dump', 'Unpack the program file', 'Unpacks the program file (main) into one plain file, needed to build code patches.', 'tools/switchfs.py', ['nso'],
    [A('NSO (main)', 'file'), A('output flat image', 'save')]),

  T('ls', 'Inspect', 'See what\'s inside a file', 'Lists what a Unity data file (bundle or .assets) holds: texts, fonts, images, and so on. Nothing is changed.', 'tools/unityls.py', [],
    [A('bundle or .assets', 'file'), V('--type', 'text', 'Only this type, e.g. TextAsset, Font, MonoBehaviour'), V('--name', 'text', 'Only names matching this glob'), B('--summary', 'Count objects per type'), UV]),

  T('text-dump', 'Text', 'Export text files', 'Saves each text inside a Unity file as a .txt file in a folder, exactly as stored, so you can edit it.', 'tools/textasset.py', ['dump'],
    [A('bundle or .assets', 'file'), A('output folder', 'dir'), V('--name', 'text', 'Only names matching this glob'), UV]),
  T('text-import', 'Text', 'Import edited text files', 'Puts the .txt files you edited back into the Unity file. Files you didn\'t change are left alone.', 'tools/textasset.py', ['import'],
    [A('bundle or .assets', 'file'), A('folder from Dump', 'dir'), V('--out', 'save', 'Output file', true), PACKER, B('--apply', 'Write the file'), UV], 'If the text is JSON, keep its brackets and quotes intact. ' + DRY),
  T('text-replace', 'Text', 'Replace a word', 'Swaps one word or phrase for another inside one text, for quick fixes without a sheet.', 'tools/textasset.py', ['replace'],
    [A('bundle or .assets', 'file'), A('TextAsset name'), A('old text'), A('new text'), V('--count', 'number', 'Refuse unless it occurs exactly this many times'), V('--out', 'save', 'Output file', true), PACKER, B('--apply', 'Write the file'), UV], DRY),
  T('sheet-export', 'Text', 'Export text to sheet', 'Copies the game\'s text into an Excel file with ID, original text and an empty Translation column.', 'tools/jsonsheet.py', ['export'],
    [A('bundle or .assets', 'file'), A('output XLSX', 'save'), V('--name', 'text', 'Only TextAssets matching this glob'), V('--key', 'text', 'Only values whose key matches this regex, e.g. ^(jp|text)$'), V('--path', 'text', 'Only JSON pointers matching this regex'), B('--all', 'Keep empty and letter-less values'), B('--nested', 'Open strings that are themselves JSON, such as choice lists'), UV]),
  T('sheet-apply', 'Text', 'Apply sheet', 'Writes the Translation column of your sheet back into the game\'s text, keeping everything else as it was.', 'tools/jsonsheet.py', ['apply'],
    [A('bundle or .assets', 'file'), A('translated XLSX', 'file'), V('--out', 'save', 'Output file', true), V('--sheet-name', 'text', 'Worksheet (default: first)'), V('--token', 'text', 'Regex that must occur equally often in Source and Translation, one per line', false, true), B('--force', 'Write even where Source no longer matches the file'), PACKER, B('--apply', 'Write the file'), UV],
    'Rows whose original text no longer matches the game are skipped. Write <empty> to make a text blank. ' + DRY),

  T('tmp-list', 'Layout', 'Find text boxes', 'Lists the text boxes on screen with their size, font size and line wrapping, so you can find one that is too small.', 'tools/tmp.py', ['list'],
    [A('bundle or .assets', 'file'), V('--text', 'text', 'Only components whose text matches this regex'), V('--object', 'text', 'Only GameObjects matching this glob'), V('--nodes-from', 'file', 'UI bundle to borrow the TMP type tree from (.assets files)'), UV]),
  T('tmp-set', 'Layout', 'Adjust text box', 'Changes one text box: its size and position, font size, shrink to fit, wrapping and spacing. Use the ID from Find text boxes.', 'tools/tmp.py', ['set'],
    [A('bundle or .assets', 'file'), A('path id', 'number'), V('--width', 'number', 'Box width'), V('--height', 'number', 'Box height'), V('--x', 'number', 'Box position x'), V('--y', 'number', 'Box position y'), V('--font-size', 'number'), V('--auto-size', 'text', 'on or off'), V('--size-min', 'number', 'Smallest auto-size'), V('--size-max', 'number', 'Largest auto-size; keep the original size'), V('--wrap', 'text', 'on or off'), V('--overflow', 'number', '0 overflow, 1 ellipsis, 2 masking, 3 truncate, 4 scroll, 5 page'), V('--char-spacing', 'number'), V('--line-spacing', 'number'), V('--margin', 'text', 'left,top,right,bottom'), V('--nodes-from', 'file', 'UI bundle to borrow the TMP type tree from'), V('--out', 'save', 'Output file', true), PACKER, B('--apply', 'Write the file'), UV], DRY),

  T('tmpfont-info', 'Fonts', 'Check fonts for missing letters', 'Lists the game\'s text fonts and which letters they are missing, for example Vietnamese letters.', 'tools/tmpfont.py', ['info'],
    [A('bundle or .assets', 'file'), V('--charset', 'text', 'vietnamese or latin', false, true), V('--text', 'text', 'Characters to check'), V('--sheet', 'file', 'XLSX whose column C to check'), UV]),
  T('tmpfont-verify', 'Fonts', 'Test the letter maker', 'Redraws a few letters the font already has and compares them with the originals. Run it once per game before using Add letters to font.', 'tools/tmpfont.py', ['verify'],
    [A('bundle or .assets', 'file'), A('font asset name'), A('source TTF', 'file'), V('--face-index', 'number'), V('--sample', 'number', 'How many glyphs to compare'), UV]),
  T('tmpfont-add', 'Fonts', 'Add letters to font', 'Draws missing letters, such as Vietnamese, into a font that cannot draw new letters by itself.', 'tools/tmpfont.py', ['add'],
    [A('bundle or .assets', 'file'), A('font asset name'), A('TTF to draw from', 'file'), V('--face-index', 'number'), V('--charset', 'text', 'vietnamese or latin', false, true), V('--text', 'text', 'Characters to add'), V('--sheet', 'file', 'Add every character used in column C'), B('--replace', 'Re-bake characters that already exist, so old and new letters match'), V('--preview', 'save', 'PNG of a sample line'), V('--preview-text', 'text'), V('--out', 'save', 'Output file', true), PACKER, B('--apply', 'Write the file'), UV],
    'Run Test the letter maker on this font first. ' + DRY),
  T('font-list', 'Fonts', 'List fonts', 'Lists the fonts stored in a Unity file and how many letters each has.', 'tools/font.py', ['list'],
    [A('bundle or .assets', 'file'), UV]),
  T('font-extract', 'Fonts', 'Save font', 'Saves a font from the game as a normal .ttf file.', 'tools/font.py', ['extract'],
    [A('bundle or .assets', 'file'), A('font name'), A('output TTF', 'save'), UV]),
  T('font-replace', 'Fonts', 'Replace font', 'Puts a different .ttf font into the game in place of an existing one. Text that draws from it changes too.', 'tools/font.py', ['replace'],
    [A('bundle or .assets', 'file'), A('font name'), A('new TTF', 'file'), V('--out', 'save', 'Output file', true), PACKER, B('--apply', 'Write the file'), UV],
    'The same font is often copied into several files; replace every copy. ' + DRY),
  T('font-coverage', 'Fonts', 'Check a font\'s letters', 'Tells you which letters a .ttf font cannot draw, using a language, your own text, or the translations in a sheet.', 'tools/font.py', ['coverage'],
    [A('TTF', 'file'), V('--charset', 'text', 'vietnamese or latin', false, true), V('--text', 'text', 'Characters to check'), V('--sheet', 'file', 'XLSX whose column C to check')]),

  T('il2cpp-find', 'Executable', 'Find text in the game code', 'Searches the text built into the game\'s code (global-metadata.dat).', 'tools/il2cpp.py', ['find'],
    [A('global-metadata.dat', 'file'), A('text'), B('--contains', 'Substring match instead of equality')]),
  T('il2cpp-patch', 'Executable', 'Change text in the game code', 'Replaces one piece of text in the game\'s code. The new text cannot be longer than the old one, and accented letters take more room than plain ones.', 'tools/il2cpp.py', ['patch'],
    [A('global-metadata.dat', 'file'), A('old text'), A('new text'), V('--out', 'save', 'Output file', true), B('--apply', 'Write the file')],
    'The change only works for this exact version of the game. ' + DRY),
  T('ips32', 'Executable', 'Build code patch', 'Makes a code patch file (.ips) from a list of changes, checking each one against the game first. For advanced users.', 'tools/ips32.py', [],
    [A('NSO (main)', 'file'), A('output folder', 'dir'), V('--patch', 'text', 'RVA:OLDHEX:NEWHEX, one per line', true, true), V('--flat', 'file', 'Flat image (default: main.flat beside the NSO)'), B('--apply', 'Write the .ips')],
    'Offsets are RVAs, not the dump.cs Offset column. ' + DRY),

  T('release', 'Release', 'Package release', 'Zips the finished mod so players can install it on Ryujinx or on a modded Switch (Atmosphere).', 'tools/release.py', [],
    [V('--title-id', 'text', 'Base game title id, 16 hex digits', true), V('--romfs', 'dir', 'Mod RomFS folder', true), V('--exefs', 'dir', 'Mod ExeFS folder (.ips)'), V('--aoc', 'text', 'DLC as TITLEID=folder, one per line', false, true), V('--name', 'text', 'Mod folder name', true), V('--version', 'text', 'Release label', true), V('--out-dir', 'dir', 'Where to write the zips', true), B('--build', 'Write the zips (otherwise print the plan)')], 'Only shows the plan until you tick Build.')
];

module.exports = {tools, groups, symbols, summaries};
