# -*- coding: utf-8 -*-
"""applysheet.py - write the translation sheet into the game's scripts.

    python applysheet.py --sheet sheet.xlsx --jp jp/romfs/common --mod <mod folder> --out out/
    python applysheet.py ... --apply --report rows.csv

--sheet  the translation sheet downloaded as .xlsx: one tab per script, with
         columns record_id, command, script, const_index, jp_text, vi_text
--jp     folder holding the JP script.memfs + script.membody (nsp.py romfs)
--mod    the VI mod folder the new scripts are for. Its font decides how the
         text is encoded, its exefs/main may redirect reads, and its scripts
         keep every string the sheet has no row for (speaker names, choices).
--out    where the new script.memfs + script.membody go; an existing file is
         kept as .bak

Without --apply it builds, verifies and reports, and writes nothing.

A row is matched to the game by script + const_index (the KUV string index);
its jp_text only confirms the match. A cell becomes game text the way the VI
builder made it, which reproduces 93.6% of the 02/10 strings byte for byte
where their text is still the sheet's:

  1. NFC; 「」『』“” and zero-width spaces dropped, " written as ' and the
     ideographic space as a space - no 02/10 string carries any of them;
     the sheet's doubled line breaks (its form of the game's \\r\\n) folded
  2. each paragraph wrapped at 62 visible characters (tags.builder_wrap)
  3. letters encoded for the patch font, which puts Vietnamese letters on
     kana code points (ệ -> る)

Unlike that builder it keeps the cell's #P, #T and #KW. Then the same pass as
patch.py: #P a cell lost is put back from JP, lines JP draws off-screen stay
untagged, the archive is rebuilt and opened again to check it.

The font encoding is learnt from the mod: rows whose cell the mod already
carries line up letter for letter with its string. --map saves it as JSON,
--use-map reads one instead.

A row not written keeps the mod's string, so a build is never worse than the
mod. The report says why: jp_text that does not match the game, a cell that
is still the JP line, a cell with kana left in it other than っ/ッ (the font
gives those codes to Vietnamese letters, so they would show as the wrong
letter), a second row for a string already written with another
translation. Written rows note letters the font has no code for and #T / #KW
the cell lost against JP - those need a translator.

Needs openpyxl.
"""
import argparse
import collections
import csv
import json
import os
import re
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kuv       # noqa: E402
import memfs     # noqa: E402
import patch     # noqa: E402
import tags      # noqa: E402
from sheetfix import read_sheet   # noqa: E402

DROP = dict.fromkeys(map(ord, '「」『』“”​'), None)
SUBST = (('"', "'"), ('　', ' '))
JAPANESE = re.compile('[぀-ヿ㐀-䶿一-鿿]')
# っ/ッ stay in VI on purpose (a gasp, 「っ――!!」): the 02/10 patch keeps them in
# 228 strings and the font draws them. Any other kana sits on a code the font
# gives to a Vietnamese letter, so it would show as the wrong letter.
SOUNDS = set('っッ')
SHARE = 0.8       # a letter's code must cover this much of its sightings


def prepare(cell):
    """A sheet cell as game text, before the font encoding."""
    t = unicodedata.normalize('NFC', cell).translate(DROP)
    for a, b in SUBST:
        t = t.replace(a, b)
    t = re.sub(r'\n{2,}', '\n', t.replace('\r\n', '\n').replace('\r', '\n'))
    return tags.builder_wrap(t)


def script_strings(arc):
    """{script name: strings} for the chunk the game loads for each entry."""
    out = {}
    for p in arc.entries:
        raw = arc.raw(p)
        nm = kuv.name(raw)
        if nm:
            out[nm] = kuv.parse(raw)[1]
    return out


def learn_font(rows, jp_strs, mod_strs):
    """The mod font's encoding, from rows whose text the mod already carries.

    A row counts when its prepared cell and the mod string are as long once
    tags and whitespace are gone, and every ASCII letter and digit lines up.
    -> ({character: code}, characters the mod's translated strings use)"""
    seen = set()
    for s, vs in mod_strs.items():
        js = jp_strs.get(s, [])
        for i, v in enumerate(vs):
            if i < len(js) and v != js[i]:
                seen.update(v)
    flat = lambda t: ''.join(tags.HIDDEN.sub('', t).split())
    count = collections.defaultdict(collections.Counter)
    for r in rows:
        vs = mod_strs.get(r['script'])
        if not r['vi'] or vs is None or r['ci'] >= len(vs):
            continue
        a, b = flat(prepare(r['vi'])), flat(vs[r['ci']])
        if len(a) != len(b) or any(x.isascii() and x.isalnum() and x != y for x, y in zip(a, b)):
            continue
        for x, y in zip(a, b):
            if not x.isascii():
                count[x][y] += 1
    fmap = {}
    for x, c in count.items():
        y, n = c.most_common(1)[0]
        if y != x and n >= SHARE * sum(c.values()):
            fmap[x] = y
    return fmap, seen


def encode(text, fmap, seen):
    """-> (text in the font's codes, [(character, what was done)] for unknown ones)."""
    out = []; unknown = []
    for ch in text:
        if ch in fmap:
            out.append(fmap[ch])
        elif ch.isascii() or ch in seen:
            out.append(ch)
        elif ch.lower() != ch and (ch.lower() in fmap or ch.lower() in seen):
            # a capital the old patch never used: its small letter at least shows
            out.append(fmap.get(ch.lower(), ch.lower())); unknown.append((ch, 'lower'))
        else:
            out.append(ch); unknown.append((ch, 'kept'))
    return ''.join(out), unknown


def plan(rows, jp_strs, fmap, seen):
    """Which game string each row writes. -> ({script: {index: text}}, report)."""
    key = lambda t: re.sub(r'[\r\n]', '', t).strip()
    flat = lambda t: ''.join(tags.HIDDEN.sub('', t).split())
    writes =collections.defaultdict(dict); report = []; first = {}
    for r in rows:
        js = jp_strs.get(r['script'])
        ci = r['ci']
        if js is None:
            report.append(dict(r=r, action='skip', why='no-script')); continue
        if ci >= len(js) or key(js[ci]) != key(r['jp']):
            report.append(dict(r=r, action='skip', why='jp-mismatch')); continue
        if not r['vi'] or not r['vi'].strip():
            report.append(dict(r=r, action='skip', why='empty')); continue
        text = prepare(r['vi'])
        if not js[ci].endswith('\n'):
            text = text.rstrip('\n')          # a trailing break only where JP has one
        k = (r['script'], ci)
        if k in first:
            if prepare(first[k]['vi']) != text:
                report.append(dict(r=r, action='skip', why='duplicate', other=first[k]))
            continue
        # a gasp (「っ！」) reads the same in both: only other kana or kanji count
        left = sorted(set(JAPANESE.findall(tags.HIDDEN.sub('', text))) - SOUNDS)
        if left and flat(text) == flat(js[ci].translate(DROP)):
            report.append(dict(r=r, action='skip', why='untranslated')); continue
        if left:
            report.append(dict(r=r, action='skip', why='japanese', chars=''.join(left))); continue
        enc, unknown = encode(text, fmap, seen)
        first[k] = r
        writes[r['script']][ci] = enc
        lost = [t for t in tags.losses(js[ci], text) if t != '#P']   # build() puts #P back
        report.append(dict(r=r, action='write', unknown=unknown, lost=lost))
    return writes, report


def build(jp, mod, writes):
    """-> (membody, memfs, patch.build report) with the rows written in."""
    def edit(nm, strs):
        if nm not in writes:
            return strs
        strs = list(strs)
        for i, t in writes[nm].items():
            strs[i] = t
        return strs
    return patch.build(jp, mod, edit=edit)


WHY = {'no-script': 'Không có script này trong game',
       'jp-mismatch': 'jp_text không khớp chuỗi JP trong game (sheet của bản khác?) - giữ chuỗi của bản mod',
       'empty': 'vi_text trống - giữ chuỗi của bản mod',
       'untranslated': 'vi_text vẫn là câu JP (chưa dịch) - giữ chuỗi của bản mod',
       'japanese': 'vi_text còn sót chữ Nhật (%s): font dùng các ô đó cho chữ Việt nên sẽ hiện sai - giữ chuỗi của bản mod',
       'duplicate': 'Cùng một câu game với tab %s dòng %s nhưng dịch khác - chỉ dùng được dòng kia'}


def write_report(path, report, restored):
    with open(path, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f)
        w.writerow(['tab', 'dòng', 'record_id', 'script', 'const_index', 'kết quả', 'ghi chú'])
        for x in report:
            r = x['r']; notes = []
            if x['action'] == 'skip':
                args = {'duplicate': lambda: (x['other']['tab'], x['other']['row']), 'japanese': lambda: (x['chars'],)}
                notes.append(WHY[x['why']] % args.get(x['why'], tuple)())
            else:
                for ch, how in x['unknown']:
                    notes.append('Font chưa có chữ %s (%s)' % (ch, 'dùng chữ thường' if how == 'lower' else 'để nguyên'))
                for t in x['lost']:
                    notes.append('Mất %s so với JP - cần sửa trong sheet' % t)
                how = restored.get((r['script'], r['ci']))
                if how:
                    notes.append('Đã trả #P theo JP (%s)' % how)
            if x['action'] == 'write' and not notes:
                continue
            w.writerow([r['tab'], r['row'], r['rid'], r['script'], r['ci'],
                        'ghi' if x['action'] == 'write' else 'bỏ qua', '; '.join(notes)])


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--sheet', required=True, help='translation sheet (.xlsx)')
    ap.add_argument('--jp', required=True, help='folder with the JP script.memfs/membody')
    ap.add_argument('--mod', required=True, help='VI mod folder (font, exe, names)')
    ap.add_argument('--out', required=True, help='output folder')
    ap.add_argument('--exe', help='patched exefs/main (default: <mod>/exefs/main if present)')
    ap.add_argument('--map', help='save the learnt font encoding to this JSON file')
    ap.add_argument('--use-map', help='read the font encoding from this JSON file')
    ap.add_argument('--report', help='CSV of every row skipped or needing a look')
    ap.add_argument('--apply', action='store_true', help='write the files')
    a = ap.parse_args()

    exe = a.exe or patch.find_exe(a.mod)
    redirects = memfs.load_redirects(exe)
    jp = memfs.Archive(*patch.find_pair(a.jp))
    mod = memfs.Archive(*patch.find_pair(a.mod), redirects=redirects)
    rows = read_sheet(a.sheet)
    jp_strs, mod_strs = script_strings(jp), script_strings(mod)
    print('sheet: %d dong, %d tab; exe: %s, %d doan chuyen huong' % (
        len(rows), len(set(r['tab'] for r in rows)), exe or 'khong co', len(redirects)))

    fmap, seen = learn_font(rows, jp_strs, mod_strs)
    if a.use_map:
        with open(a.use_map, encoding='utf-8') as f:
            fmap = json.load(f)
        print('font: doc %d chu tu %s' % (len(fmap), a.use_map))
    else:
        print('font: hoc duoc %d chu tu ban mod' % len(fmap))
    if a.map:
        with open(a.map, 'w', encoding='utf-8') as f:
            json.dump(fmap, f, ensure_ascii=False, indent=0, sort_keys=True)
        print('font -> %s' % a.map)

    writes, report = plan(rows, jp_strs, fmap, seen)
    why = collections.Counter(x['why'] for x in report if x['action'] == 'skip')
    print('ghi %d chuoi vao %d script; bo qua: jp khong khop %d, chua dich %d, con sot chu Nhat %d, '
          'trung cau dich khac %d, trong %d' % (
              sum(len(w) for w in writes.values()), len(writes), why['jp-mismatch'], why['untranslated'],
              why['japanese'], why['duplicate'], why['empty']))
    unknown = collections.Counter(ch for x in report if x['action'] == 'write' for ch, _ in x['unknown'])
    if unknown:
        print('font chua co: %s' % ', '.join('U+%04X x%d' % (ord(ch), n) for ch, n in unknown.most_common()))
    lost = collections.Counter(t for x in report if x['action'] == 'write' for t in x['lost'])
    print('can sua trong sheet: mat #T %d, mat #KW %d' % (lost['#T'], lost['#KW']))

    body, mem, rep = build(jp, mod, writes)
    restored = dict(((r['script'], r['idx']), r['how']) for r in rep['rows'] if r['how'] not in ('offscreen',))
    print('tra #P: %d chuoi; bo tag ngoai man hinh: %d' % (
        sum(1 for r in rep['rows'] if r['how'] in ('single', 'multi')), len(rep['stripped'])))
    print('noi rong u16 -> u32: %s' % (', '.join(rep['widened']) or 'khong'))
    print('membody %d -> %d byte, memfs %d -> %d byte' % (len(mod.body), len(body), len(mod.memfs), len(mem)))

    problems = patch.verify(body, mem, jp, redirects)
    if problems:
        print('KIEM TRA LOI:'); [print('  ' + x) for x in problems]
        return 1
    print('kiem tra: OK (code giong JP, so chuoi khop, khong con #P mat ngoai cac cau ngoai man hinh)')
    if a.report:
        write_report(a.report, report, restored)
        print('bao cao -> %s' % a.report)
    if not a.apply:
        print('chay thu - them --apply de ghi vao %s' % a.out)
        return 0
    patch.write_files(a.out, (('script.membody', body), ('script.memfs', mem)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
