# -*- coding: utf-8 -*-
"""extractsheet.py - build the translation sheet (.xlsx) from the game's scripts.

    python extractsheet.py --jp jp/romfs/common --out sheet.xlsx
    python extractsheet.py --jp jp/romfs/common --exe jp/exefs/main --old old_sheet.xlsx --out sheet.xlsx
    python extractsheet.py --jp jp/romfs/common --mod <mod folder> --map font.json --out sheet.xlsx

--jp    folder holding the JP script.memfs + script.membody (nsp.py romfs)
--out   the workbook to write (.xlsx). An existing file is kept as .bak.
--exe   exefs/main: adds the 'exe' tab (exetext.py export), the program's text
--old   an earlier sheet: its vi_text, speaker_vi and note are carried over
        by script + const_index, its route_note by route prefix, and its
        other tabs (notes, glossary, ...) copied as values after the scripts
--mod   a VI mod folder (romfs/common, exefs/main): fills vi_text and
        speaker_vi from its scripts, decoded with --map (applysheet.py --map);
        a cell from --old wins over the mod's string

The layout is the one applysheet.py and sheetfix.py read: an 'Index' tab,
then one tab per script, named after it, with

  record_id, category, route_note, script, command, speaker_jp, speaker_vi,
  jp_text, vi_text, source_preview_jp, note, choice_index, choice_label,
  block_index, body_offset, rz_kind, call_offset, argc, arg_position,
  const_index, const_offset, speaker_const_index, speaker_const_offset,
  all_args_json, push_offsets_json, opcode_bytes_hex

A row is one call in the script's code that shows text:

  NameMess(speaker, text)        dialogue   (speaker left out when blank)
  GuideMess(text)                narration
  SltAdd(index, label, text)     choice
  Mov GAMESTR_DictWords, key     system_optional - a glossary key, never
                                 shown; applysheet writes it from the exe tab

const_index is the KUV string index of the text (kuv.py strings); offsets
are hex positions in the uncompressed .tat (call_offset = the 2b 2c call,
const_offset = the string in the pool), block_index the entry's place in
script.memfs, body_offset its chunk in script.membody, rz_kind the top 16
bits of the chunk's uncompressed size. jp_text is the game string with
\\r\\n written as \\n; the same string reached by two calls gets two rows.
record_id numbers the rows across all scripts in script.memfs order.
A line with nothing to translate is left out: no letter, kana or kanji in
the text nor in the speaker (the heroine's 「……！」, a narration of dots).

Nothing in the game is changed. Needs openpyxl.
"""
import argparse
import collections
import json
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kuv     # noqa: E402
import memfs   # noqa: E402

COLUMNS = ('record_id', 'category', 'route_note', 'script', 'command', 'speaker_jp', 'speaker_vi',
           'jp_text', 'vi_text', 'source_preview_jp', 'note', 'choice_index', 'choice_label',
           'block_index', 'body_offset', 'rz_kind', 'call_offset', 'argc', 'arg_position',
           'const_index', 'const_offset', 'speaker_const_index', 'speaker_const_offset',
           'all_args_json', 'push_offsets_json', 'opcode_bytes_hex')
INDEX_COLUMNS = ('sheet_index', 'sheet_name', 'script', 'route_prefix', 'route_note', 'record_count',
                 'core_count', 'optional_count', 'top_speakers', 'choice_sample', 'block_index',
                 'body_offset', 'rz_kind')
# command -> (category, argc, which argument is the text)
COMMANDS = {'NameMess': ('dialogue', 2, 1), 'GuideMess': ('narration', 1, 0), 'SltAdd': ('choice', 3, 2)}
DICT_VAR = 'GAMESTR_DictWords'
TRANSLATED = ('vi_text', 'speaker_vi', 'note')
SCRIPT_TABS = set(COLUMNS)


def sheet_text(s):
    """A game string as the sheet shows it: \\r\\n as a blank line, as the
    sheet has always had it (applysheet folds it back)."""
    return s.replace('\r\n', '\n\n')


def one_line(s):
    return re.sub(r'\n[\n 　]*', ' ', s)


TAG = re.compile(r'#(P\([^)]*\)|T[012]|KW|R\([^)]*\)|C\([^)]*\))')


def has_words(s):
    """A letter, kana or kanji once tags and ${FirstName} are taken off."""
    return bool(re.search(r'\w', TAG.sub('', s or '').replace('${FirstName}', '')))


def blank(s):
    return not s.strip(' 　')


def calls(raw):
    """[(function, [arg indices], call position in code, [push positions])]:
    kuv.calls plus where each argument was pushed."""
    h, strs, _ = kuv.parse(raw)
    c = kuv.code(raw)
    out = []; stack = []; i = 0
    while i < len(c):
        if c[i] == 0x0e and i + 5 <= len(c):
            v = struct.unpack('>I', c[i + 1:i + 5])[0]
            if v < len(strs):
                stack.append((v, i)); i += 5; continue
        if c[i:i + 2] == b'\x2b\x2c' and i + 4 <= len(c):
            argc = c[i + 2]
            if stack:
                args = stack[-1 - argc:-1] if argc else []
                out.append((strs[stack[-1][0]], [a for a, _ in args], i, [p for _, p in args]))
            stack = []; i += 4; continue
        i += 1
    return out


def script_rows(raw, block, body_offset, size):
    """The sheet rows of one script, record_id and route_note left empty."""
    h, strs, _ = kuv.parse(raw)
    base, table, pool = h[18], h[10], h[16]
    name = kuv.name(raw)

    def soff(i):
        return '0x%x' % (pool + struct.unpack_from('<I', raw, table + 8 * i)[0])

    rows = []
    for fn, args, at, pushes in calls(raw):
        if fn in COMMANDS:
            cat, argc, ti = COMMANDS[fn]
            if len(args) != argc:
                continue
        elif fn == 'Mov' and len(args) == 2 and strs[args[0]] == DICT_VAR:
            cat, ti = 'system_optional', 1
        else:
            continue
        t = args[ti]
        speaker = strs[args[0]] if fn == 'NameMess' else None
        if not has_words(strs[t]) and not has_words(speaker):
            continue      # 「……」 of the heroine or ？？？, a narration of dots: nothing to translate
        r = dict.fromkeys(COLUMNS)
        r.update(category=cat, script=name, command=fn, jp_text=sheet_text(strs[t]),
                 block_index=block, body_offset='0x%x' % body_offset, rz_kind='%04x' % (size >> 16),
                 call_offset='0x%x' % (base + at), argc=len(args), const_index=t, const_offset=soff(t),
                 all_args_json=json.dumps([one_line(strs[a]) for a in args], ensure_ascii=False),
                 push_offsets_json=json.dumps(['0x%x' % (base + p) for p in pushes]))
        first = pushes[0] if pushes else at
        r['opcode_bytes_hex'] = ' '.join('%02x' % b for b in kuv.code(raw)[first:at + 4])
        preview = r['jp_text']
        if fn == 'NameMess' and not blank(strs[args[0]]):
            r.update(speaker_jp=strs[args[0]], speaker_const_index=args[0], speaker_const_offset=soff(args[0]))
            preview = '%s\n%s' % (strs[args[0]], preview)
        elif fn == 'NameMess':
            r.update(speaker_const_index=args[0], speaker_const_offset=soff(args[0]))
        elif fn == 'SltAdd':
            r.update(choice_index=strs[args[0]], choice_label=strs[args[1]])
            preview = '%s\n%s' % (strs[args[1]], preview)
        elif fn == 'Mov':
            r['arg_position'] = 1
        r['source_preview_jp'] = preview
        rows.append(r)
    return rows


def route_prefix(name):
    m = re.match(r'(EV\d+)', name)
    return m.group(1) if m else 'SYSTEM'


def extract(arc):
    """{script name: rows} in membody order, with record_id filled."""
    keys = list(arc.entries)
    out = collections.OrderedDict(); rid = 0
    for p in keys:
        off, size = arc.entries[p].vals
        c = arc.chunks[arc.loaded(p)]
        if not kuv.is_kuv(c.raw):
            continue
        rows = script_rows(c.raw, keys.index(p), c.pos, len(c.raw))
        for r in rows:
            rid += 1
            r['record_id'] = rid
        if rows:
            out[kuv.name(c.raw)] = rows
    return out


def mod_strings(mod):
    """{script name: strings} the mod's game loads."""
    common = os.path.join(mod, 'romfs', 'common')
    exe = os.path.join(mod, 'exefs', 'main')
    arc = memfs.Archive(os.path.join(common, 'script.memfs'), os.path.join(common, 'script.membody'),
                        memfs.load_redirects(exe if os.path.exists(exe) else None))
    out = {}
    for p in arc.entries:
        raw = arc.raw(p)
        if kuv.is_kuv(raw):
            out[kuv.name(raw)] = kuv.parse(raw)[1]
    return out


def fill_from_mod(scripts, mstrs, fmap):
    import exetext
    n = 0
    for name, rows in scripts.items():
        strs = mstrs.get(name)
        if strs is None:
            continue
        for r in rows:
            ci = r['const_index']
            if ci >= len(strs) or sheet_text(strs[ci]) == r['jp_text']:
                continue
            r['vi_text'] = exetext.decode(sheet_text(strs[ci]), fmap); n += 1
            si = r['speaker_const_index']
            if r['speaker_jp'] and si < len(strs) and strs[si] != r['speaker_jp']:
                r['speaker_vi'] = exetext.decode(strs[si], fmap)
    return n


def read_old(path):
    """(cells {(script, const_index): [row values]}, routes {prefix: note}, workbook)."""
    import openpyxl
    wb = openpyxl.load_workbook(path, data_only=True)
    cells = collections.defaultdict(list); routes = {}
    for ws in wb.worksheets:
        it = ws.iter_rows(values_only=True)
        hdr = next(it, None)
        if not hdr:
            continue
        ix = dict((h, i) for i, h in enumerate(hdr) if h)
        if 'route_prefix' in ix and 'route_note' in ix:
            for r in it:
                if r[ix['route_prefix']] and r[ix['route_note']]:
                    routes.setdefault(r[ix['route_prefix']], r[ix['route_note']])
            continue
        if not all(k in ix for k in ('script', 'const_index', 'vi_text')):
            continue
        for r in it:
            sc, ci = r[ix['script']], r[ix['const_index']]
            if sc is None or ci is None:
                continue
            try:
                ci = int(float(ci))
            except ValueError:
                continue
            cells[(str(sc), ci)].append(dict((k, r[ix[k]]) for k in TRANSLATED if k in ix))
    return cells, routes, wb


def carry_over(scripts, cells):
    """Fill the translated columns from the old sheet; the k-th row of a
    string takes the k-th old row. -> (rows filled, old keys not found)."""
    n = 0; used = set()
    for rows in scripts.values():
        seen = collections.Counter()
        for r in rows:
            key = (r['script'], r['const_index'])
            old = cells.get(key)
            if not old:
                continue
            used.add(key)
            o = old[min(seen[key], len(old) - 1)]; seen[key] += 1
            got = False
            for k in TRANSLATED:
                if o.get(k) not in (None, ''):
                    r[k] = o[k]; got = True
            n += got
    return n, [k for k in cells if k not in used]


def index_rows(scripts, routes):
    out = []
    for i, (name, rows) in enumerate(scripts.items(), 1):
        sp = collections.Counter(r['speaker_jp'] for r in rows if r['speaker_jp'])
        choices = [r['jp_text'] for r in rows if r['category'] == 'choice']
        opt = sum(1 for r in rows if r['category'] == 'system_optional')
        pre = route_prefix(name)
        out.append((i, name[:-4] if name.endswith('.tat') else name, name, pre, routes.get(pre),
                    len(rows), len(rows) - opt, opt,
                    '; '.join('%s:%d' % kv for kv in sp.most_common(8)) or None,
                    ' | '.join(choices) or None, rows[0]['block_index'], rows[0]['body_offset'], rows[0]['rz_kind']))
    return out


def tab_name(name):
    t = name[:-4] if name.endswith('.tat') else name
    return re.sub(r'[\\/*?:\[\]]', '_', t)[:31]


def write_book(path, scripts, routes, exe_rows=None, old_wb=None):
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Index'
    ws.append(list(INDEX_COLUMNS))
    for r in index_rows(scripts, routes):
        ws.append(list(r))
    ws.freeze_panes = 'A2'
    names = set(['Index'])
    for name in sorted(scripts):
        ws = wb.create_sheet(tab_name(name)); names.add(ws.title)
        ws.append(list(COLUMNS))
        for r in scripts[name]:
            r['route_note'] = routes.get(route_prefix(name))
            ws.append([r[k] for k in COLUMNS])
        ws.freeze_panes = 'A2'
        for col, w in (('H', 50), ('I', 50), ('J', 30), ('K', 30)):
            ws.column_dimensions[col].width = w
    if old_wb is not None:
        for ows in old_wb.worksheets:
            if ows.title in names or ows.title == 'exe':
                continue
            hdr = next(ows.iter_rows(values_only=True), None) or ()
            if 'const_index' in hdr:
                continue          # an old script tab the game no longer has
            ws = wb.create_sheet(ows.title); names.add(ws.title)
            for r in ows.iter_rows(values_only=True):
                ws.append(list(r))
    if exe_rows is not None:
        import exetext
        ws = wb.create_sheet('exe')
        ws.append(list(exetext.COLUMNS))
        for r in exe_rows:
            ws.append(list(r))
        ws.freeze_panes = 'A2'
    if os.path.exists(path):
        os.replace(path, path + '.bak')
    wb.save(path)


def exe_tab(path, old_wb):
    """The exe tab: exetext export rows, vi_text/note carried from the old exe tab."""
    import exetext
    exe = exetext.open_exe(path)
    old = {}
    if old_wb is not None and 'exe' in old_wb.sheetnames:
        it = old_wb['exe'].iter_rows(values_only=True)
        hdr = next(it, None) or ()
        ix = dict((h, i) for i, h in enumerate(hdr) if h)
        if 'address' in ix and 'vi_text' in ix:
            for r in it:
                if r[ix['address']]:
                    old[str(r[ix['address']])] = r
    rows = []
    for a, s in sorted(exe.strings.items()):
        addr = '0x%x' % a
        vi, note = '', exetext.notes(s)
        o = old.get(addr)
        if o is not None:
            vi = o[ix['vi_text']] or ''
            if 'note' in ix and o[ix['note']]:
                note = o[ix['note']]
        rows.append((addr, exetext.ref_text(exe.refs[a]), s, vi, note))
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--jp', required=True, help='folder with the JP script.memfs and script.membody')
    ap.add_argument('--out', required=True, help='workbook to write (.xlsx)')
    ap.add_argument('--exe', help='exefs/main, for the exe tab')
    ap.add_argument('--old', help='an earlier sheet (.xlsx) to carry translations over from')
    ap.add_argument('--mod', help='VI mod folder to fill vi_text from (needs --map)')
    ap.add_argument('--map', help='font encoding (.json) from applysheet.py --map')
    a = ap.parse_args()
    if a.mod and not a.map:
        ap.error('--mod needs --map to read the mod\'s Vietnamese letters')
    try:
        import openpyxl  # noqa: F401
    except ImportError:
        raise SystemExit('openpyxl is needed (pip install openpyxl)')
    arc = memfs.Archive(os.path.join(a.jp, 'script.memfs'), os.path.join(a.jp, 'script.membody'))
    scripts = extract(arc)
    total = sum(len(r) for r in scripts.values())
    kinds = collections.Counter(r['category'] for rows in scripts.values() for r in rows)
    print('%d scripts, %d rows (%s)' % (len(scripts), total, ', '.join('%s %d' % kv for kv in sorted(kinds.items()))))
    if a.mod:
        import exetext
        n = fill_from_mod(scripts, mod_strings(a.mod), exetext.load_map(a.map))
        print('mod: %d rows filled with its Vietnamese text' % n)
    routes, old_wb = {}, None
    if a.old:
        cells, routes, old_wb = read_old(a.old)
        n, lost = carry_over(scripts, cells)
        print('old sheet: %d rows carried over' % n)
        if lost:
            print('  %d rows of the old sheet are no longer in the game (e.g. %s)' % (
                len(lost), ', '.join('%s #%d' % k for k in lost[:3])))
    exe_rows = exe_tab(a.exe, old_wb) if a.exe else None
    if exe_rows is not None:
        print('exe tab: %d strings' % len(exe_rows))
    write_book(a.out, scripts, routes, exe_rows, old_wb)
    print('written to %s' % a.out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
