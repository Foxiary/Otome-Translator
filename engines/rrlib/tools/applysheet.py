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
its jp_text only confirms the match, with dashes (―, —) left out and 《》
read as ": a find-and-replace on the whole sheet once took ―― out of
jp_text and once turned 《》 into ".

A cell becomes game text the way the VI builder made it, which reproduces
93.6% of the 02/10 strings byte for byte where their text is still the
sheet's:

  1. NFC; 「」『』“” and zero-width spaces dropped, " written as ' and the
     ideographic space as a space - no 02/10 string carries any of them;
     the sheet's doubled line breaks (its form of the game's \\r\\n) folded
  2. each paragraph wrapped at 62 visible characters (tags.builder_wrap)
  3. letters encoded for the patch font, which puts Vietnamese letters on
     kana code points (ệ -> る)

Step 2 counts characters, and the game never wraps or clips a line itself,
so a line of wide letters (…, 《》, ――), or a #P line placed far right, ran
out of its box, while most lines left room unused. By default the wrap
measures instead (overflow.fit_wrap): each paragraph is filled up to the
room of its boxes in the widest of the mod's four settings fonts - the
message window, or the screen from its #P x, and the backlog. A backlog
entry holds 3 lines (JP never has more), so a string still over 3 gets the
line breaks of its cell joined, block by block, where that saves lines.
--chars N caps lines at N characters as well (62: the old count, and a
paragraph that fits keeps its old breaks), --max-lines 0 keeps every break
of the cell, --fonts names another font folder, --chars-only wraps at 62
characters only (what the 93.6% above was measured with). The report names
each string that got more lines (one with #P may reach the line under it),
each cell whose breaks were joined, and each string still over 3 lines.

Tags are written as the cell has them: whether a line carries #P, #T or
#KW is the translator's call, made in the sheet. Unlike that builder nothing
is dropped and, unlike patch.py, no #P is put back - audit.py (and
sheetfix.py on the sheet) is the tool that checks tags. Two #P faults are
mended because the line is broken in game either way, and the report names
the cell (the 09/11 sheet: 27 and 4):
- a cell whose #P tags all put it off the screen loses them. JP draws a
  poem off-screen where the art already shows it (#P(520,1200)); the
  translation would be readable only in the backlog.
- '#P(1110220),' (a CSV round trip moved the comma out of the tag) gets the
  JP string's tag back.
The archive is then rebuilt as patch.py does and opened again to check it.

A cell is skipped when Japanese is left in it: kana other than っ/ッ (the
font draws Vietnamese letters on those codes), or kanji outside brackets.
A kanji in brackets is a gloss, 'tộc Hoa (嬅)', and draws as itself.

Glossary keys are the other exception to "as the cell has it". A script opens
an entry with `Mov GAMESTR_DictWords, <key>` and the game looks for the
glossary term (exefs/main, ruby taken off) equal to the key, character for
character. The key is never shown, so it is written as the term will be:
the title the exe tab gives it (--exe-list, default the --sheet's own exe
tab), prepared and encoded exactly as exetext.py import writes it with the
same map - or the JP key where that title is left Japanese. The report
names every key cell that differs. The 09/11 sheet had 71 of 131.

The font encoding is learnt from the mod: rows whose cell the mod already
carries line up letter for letter with its string. --map saves it as JSON,
--use-map reads one instead.

A row not written keeps the mod's string, so a build is never worse than the
mod. The report says why: jp_text that does not match the game, a cell that
is still the JP line, a cell with kana left in it other than っ/ッ (the font
gives those codes to Vietnamese letters, so they would show as the wrong
letter), a second row for a string already written with another
translation. Written rows note letters the font has no code for.

Some cells carry pieces of an older CSV export around the translation, and
only the translation is written (`cleanup`). The report names each such row
so the cell can be cleaned in the sheet. In the 07/11 sheet:
- 113 whole rows in EV04_0008_02: 'JP,Speaker,VI' on a NameMess line and
  'JP,VI,,,,,' on narration. JP is the row's jp_text with 、。 as ,. and its
  line breaks as spaces.
- 75 cells there that end in the empty columns ',,,,,'.
- 207 dialogue cells in 9 other tabs that open with the speaker's name,
  'Fey,「Dừng lại……!」'.
- 5 cells that open with a comma.

Needs openpyxl.
"""
import argparse
import collections
import csv
import difflib
import json
import os
import re
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import exetext   # noqa: E402
import kuv       # noqa: E402
import memfs     # noqa: E402
import overflow  # noqa: E402
import patch     # noqa: E402
import tags      # noqa: E402
from sheetfix import read_sheet   # noqa: E402

DROP = dict.fromkeys(map(ord, '「」『』“”​'), None)
SUBST = (('"', "'"), ('　', ' '))
# っ/ッ stay in VI on purpose (a gasp, 「っ――!!」): the 02/10 patch keeps them in
# 228 strings and the font draws them. Any other kana sits on a code the font
# gives to a Vietnamese letter, so it would show as the wrong letter.
SOUNDS = set('っッ')
SHARE = 0.8       # a letter's code must cover this much of its sightings
# jp_text only confirms the row's script + const_index. A find-and-replace on
# the whole sheet once took ―― out of jp_text, and once turned 《》 into ".
DASHES = dict.fromkeys(map(ord, '―—'), None)
BOOKS = dict.fromkeys(map(ord, '《》"'), None)
LOOSE = dict(DASHES)
LOOSE.update(BOOKS)


def loose_kinds(game, cell):
    """How jp_text differs from the game string, ignoring line breaks.

    None when a character other than a dash or a 《》/" swap differs: the row
    is then another line and must not be written. [] when they are the same."""
    g = re.sub(r'[\r\n]', '', game).strip()
    c = re.sub(r'[\r\n]', '', cell).strip()
    if g.translate(LOOSE) != c.translate(LOOSE):
        return None
    if g == c:
        return []
    chars = set()
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, g, c, autojunk=False).get_opcodes():
        if tag != 'equal':
            chars.update(g[i1:i2])
            chars.update(c[j1:j2])
    kinds = []
    if chars & set('―—'):
        kinds.append('dashes')
    if chars & set('《》"'):
        kinds.append('brackets')
    return kinds or None


def normalize(cell):
    """A sheet cell as game text, before wrapping and the font encoding."""
    t = unicodedata.normalize('NFC', cell).translate(DROP)
    for a, b in SUBST:
        t = t.replace(a, b)
    return re.sub(r'\n{2,}', '\n', t.replace('\r\n', '\n').replace('\r', '\n'))


def prepare(cell):
    """A sheet cell as game text, wrapped at 62 characters, before the font encoding."""
    return tags.builder_wrap(normalize(cell))


# A pasted CSV row: its JP part next to the jp_text the way the old export
# wrote it, so a typo in the JP (余エに for 余計に) still matches.
CSV_JP_MATCH = 0.85
LETTER = re.compile('[A-Za-zÀ-ɏḀ-ỿ]')
EMPTY_COLUMNS = re.compile(r',{2,}\s*$')
TAG_START = re.compile(r'#[A-Z]+\d*(?:\([^)]*\)?)?|\$\{\w+\}')   # a tag, cut or whole, or a name


def speaker_field(rest):
    """'Speaker,VI' -> (speaker, VI), or (None, rest) when the first field
    does not read as a name: dialogue VI opens with 「 or （, and a name is
    short and has no sentence in it."""
    k = rest.find(',')
    if k < 0:
        return None, rest
    name, vi = rest[:k], rest[k + 1:]
    if vi.lstrip().startswith(('「', '（', '『', '#T')) or (len(name) <= 24 and not re.search(r'[.!?…]', name)):
        return name, vi
    return None, rest


def csv_jp(jp):
    """jp_text as the old CSV export wrote it: no ruby, 、。 as ,. and each
    line break (with the indent after it) as one space."""
    t = re.sub(r'#R\([^)]*\)', '', jp)
    t = re.sub(r'(?:\r?\n)+　?', ' ', t)
    return t.replace('、', ',').replace('。', '.')


def csv_row(cell, jp, cmd):
    """The VI part of a cell that holds a pasted CSV row, or None.

    -> (VI, speaker field or None, 'row') for 'JP,Speaker,VI' (NameMess) and
    'JP,VI' (anything else), or (VI, None, 'columns') for a cell that only ends
    in empty columns. Trailing empty columns are dropped in both."""
    want = csv_jp(jp)
    best = (0, None)
    for m in re.finditer(',', cell):
        head = cell[:m.start()]
        if LETTER.search(TAG_START.sub('', head)):
            break                      # Vietnamese started: no JP part before this comma
        if len(head) < len(want) / 2:
            continue
        r = difflib.SequenceMatcher(None, head, want, autojunk=False).ratio()
        if r > best[0]:
            best = (r, m.end())
    if best[0] >= CSV_JP_MATCH:
        rest = cell[best[1]:]
        speaker = None
        if cmd == 'NameMess':
            speaker, rest = speaker_field(rest)
        rest = EMPTY_COLUMNS.sub('', rest)
        # a letter after the JP part, else the JP line itself has the comma;
        # VI may be all punctuation (「—...」) behind a speaker name
        if LETTER.search(rest) or (speaker and LETTER.search(speaker)):
            return rest, speaker, 'row'
    if EMPTY_COLUMNS.search(cell):
        return EMPTY_COLUMNS.sub('', cell), None, 'columns'
    return None


TAGS_FIRST = r'(?:#[A-Z]+\d*(?:\([^)]*\))?)*'
OPENS_QUOTE = re.compile(TAGS_FIRST + '[「（『]')
# 'Fey,「…」': a name of up to 40 characters ('Thị nữ Tuyết Nguyệt Hoa Vương
# triều 1' is 37), then the quote the JP line opens with
NAME_FIRST = re.compile('^(' + TAGS_FIRST + r')([^「」『』,\n#(（]{1,40}),[ \t]*(?=[「（『])')
LEAD_COMMA = re.compile(r'^\s*,+\s*')


def cleanup(cell, jp, cmd):
    """A cell with leftovers of a CSV export around its translation.

    -> (text to write, speaker or None, kind) or None. kind is 'row' (a whole
    pasted row, see csv_row), or one or more of 'columns' (empty columns at
    the end), 'comma' (a comma in front) and 'name' (the speaker's name in
    front of a NameMess line whose JP opens with a quote), joined by '+'."""
    fix = csv_row(cell, jp, cmd)
    if fix and fix[2] == 'row':
        return fix
    t, speaker, kinds = cell, None, []
    if fix:
        t = fix[0]; kinds.append('columns')
    m = LEAD_COMMA.match(t)
    if m and not jp.lstrip().startswith(('、', ',')):
        t = t[m.end():]; kinds.append('comma')
    if cmd == 'NameMess' and OPENS_QUOTE.match(jp.lstrip()):
        m = NAME_FIRST.match(t)
        if m:
            speaker = m.group(2).strip()
            t = m.group(1) + t[m.end():]; kinds.append('name')
    return (t, speaker, '+'.join(kinds)) if kinds else None


BROKEN_P = re.compile(r'#P\((\d+)\),?')      # '#P(1110220),': x and y run together, the comma after


def fix_tags(cell, jp):
    """-> (cell, kinds) for the two #P faults a cell can carry that always
    break the line in game:
      'broken'     #P(1110220), - a CSV round trip moved the comma out of
                   the tag; the JP string's tag whose x and y read so is put back
      'offscreen'  every #P of the cell puts it off the screen. JP does that
                   on purpose where the art already shows the words (poems,
                   #P(520,1200)); the translation would show only in the
                   backlog, so its tags go (as patch.py and the 07/11 build did)"""
    kinds = []
    jp_tags = dict((m.group(1) + m.group(2), m.group(0)) for m in tags.P.finditer(jp))
    t = BROKEN_P.sub(lambda m: jp_tags.get(m.group(1), m.group(0)), cell)
    if t != cell:
        kinds.append('broken')
    if tags.all_offscreen([(int(x), int(y)) for x, y in tags.P.findall(t)]):
        t = tags.P.sub('', t)
        kinds.append('offscreen')
    return t, kinds


def script_strings(arc):
    """{script name: strings} for the chunk the game loads for each entry."""
    out = {}
    for p in arc.entries:
        raw = arc.raw(p)
        nm = kuv.name(raw)
        if nm:
            out[nm] = kuv.parse(raw)[1]
    return out


DICT_VAR = 'GAMESTR_DictWords'
RUBY = re.compile(r'#R\([^)]*\)')


def dict_keys(arc):
    """{(script, string index)} of the glossary keys: the value each
    `Mov GAMESTR_DictWords, <key>` sets."""
    out = set()
    for p in arc.entries:
        raw = arc.raw(p)
        nm = kuv.name(raw)
        if not nm:
            continue
        strs = kuv.parse(raw)[1]
        for fn, args, _ in kuv.calls(raw):
            if fn == 'Mov' and len(args) == 2 and strs[args[0]] == DICT_VAR:
                out.add((nm, args[1]))
    return out


def glossary_keys(exe_path, list_path, fmap):
    """{JP key: (key as the program will hold it, VI title or None)}.

    The game finds a glossary entry by comparing its term, ruby taken off,
    with the key exactly. The term is what exetext.py import writes from the
    list (the sheet's exe tab) with the same font map, so the key is taken
    from that very text; a term the list leaves Japanese keeps the JP key."""
    with open(exe_path, 'rb') as f:
        exe = exetext.Exe(f.read())
    rows = exetext.read_rows(list_path)
    writes, _ = exetext.plan(rows, exe, fmap)
    vi = dict((r['address'], r['vi']) for r in reversed(rows))     # the row plan() used: the first
    out = {}
    for _, term, _ in exetext.glossary(exe):
        jp = exe.strings[term]
        key = RUBY.sub('', jp)
        if term in writes:
            out[key] = (RUBY.sub('', writes[term]), RUBY.sub('', exetext.prepare(vi[term], jp)))
        else:
            out[key] = (key, None)
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


def plan(rows, jp_strs, fmap, seen, keys=None, faces=None, chars=0, max_lines=overflow.LOG_LINES):
    """Which game string each row writes. -> ({script: {index: text}}, report).

    keys: {(script, index): (text, VI title or None)} for the glossary keys
    (dict_keys + glossary_keys): those strings get the title's text whatever
    the cell says, so the game finds the entry; never shown on screen.
    faces: the mod's settings fonts (overflow.story_faces). The text is then
    wrapped after encoding with overflow.fit_wrap instead of at 62 characters:
    each line filled up to the room of its boxes in the widest font (chars:
    a cap on visible characters as well, 0 none), and a string over
    max_lines lines (the backlog's 3; 0 never) gets the paragraphs of a
    block refilled as one."""
    keys = keys or {}
    flat = lambda t: ''.join(tags.HIDDEN.sub('', t).split())
    writes =collections.defaultdict(dict); report = []; first = {}; written = {}
    for r in rows:
        js = jp_strs.get(r['script'])
        ci = r['ci']
        if js is None:
            report.append(dict(r=r, action='skip', why='no-script')); continue
        kinds = loose_kinds(js[ci], r['jp']) if ci < len(js) else None
        if kinds is None:
            report.append(dict(r=r, action='skip', why='jp-mismatch')); continue
        fixed = list(kinds)                # a find-and-replace on the sheet reached jp_text
        cell, csv_fix = r['vi'], None
        if cell and cell.strip():
            csv_fix = cleanup(cell, r['jp'], r.get('cmd'))
            if csv_fix:
                cell = csv_fix[0]
            cell, more = fix_tags(cell, js[ci])
            fixed = fixed + more
        add = lambda **x: report.append(dict(x, r=r, csv=csv_fix, fixed=fixed))
        k = (r['script'], ci)
        if k in keys:
            if k in first:
                continue
            enc, title = keys[k]
            had = prepare(cell).strip() if cell and cell.strip() else ''
            first[k], written[k] = r, enc
            writes[r['script']][ci] = enc
            add(action='write', unknown=[], key=None if had == (title or js[ci]) else (had, title))
            continue
        if not cell or not cell.strip():
            add(action='skip', why='empty'); continue
        text = prepare(cell)
        if not js[ci].endswith('\n'):
            text = text.rstrip('\n')          # a trailing break only where JP has one
        if k in first:
            if written[k] != text:
                add(action='skip', why='duplicate', other=first[k])
            elif csv_fix:
                add(action='skip', why='same', other=first[k])    # still a cell to clean in the sheet
            continue
        # a gasp (「っ！」) reads the same in both, a kanji in brackets is a gloss
        left = exetext.japanese_left(tags.HIDDEN.sub('', text))
        if left and flat(text) == flat(js[ci].translate(DROP)):
            add(action='skip', why='untranslated'); continue
        if left:
            add(action='skip', why='japanese', chars=''.join(left)); continue
        enc, unknown = encode(text, fmap, seen)
        fit = refit = merged = 0
        if faces:
            # encoding is one code per character and keeps spaces and tags, so wrapping the
            # encoded text breaks where builder_wrap would, and the font's advances measure it
            fitted, fit, merged = overflow.fit_wrap(encode(normalize(cell), fmap, seen)[0], faces,
                                                    chars=chars, max_rows=max_lines)
            if not js[ci].endswith('\n'):
                fitted = fitted.rstrip('\n')
            refit, enc = fitted != enc, fitted
        first[k], written[k] = r, text
        writes[r['script']][ci] = enc
        many = overflow.rows(enc) if faces and max_lines and overflow.rows(enc) > max_lines else 0
        add(action='write', unknown=unknown, fit=fit, refit=refit, merged=merged, rows=many)
    return writes, report


def build(jp, mod, writes):
    """-> (membody, memfs, patch.build report) with the rows written in.

    Strings go in as planned (plan's fix_tags already took the off-screen
    tags off): no #P put back."""
    def edit(nm, strs):
        if nm not in writes:
            return strs
        strs = list(strs)
        for i, t in writes[nm].items():
            strs[i] = t
        return strs
    return patch.build(jp, mod, restore=False, untag_offscreen=False, edit=edit)


WHY = {'no-script': 'Không có script này trong game',
       'jp-mismatch': 'jp_text không khớp chuỗi JP trong game (sheet của bản khác?) - giữ chuỗi của bản mod',
       'empty': 'vi_text trống - giữ chuỗi của bản mod',
       'untranslated': 'vi_text vẫn là câu JP (chưa dịch) - giữ chuỗi của bản mod',
       'japanese': 'vi_text còn sót chữ Nhật (%s): font dùng các ô đó cho chữ Việt nên sẽ hiện sai - giữ chuỗi của bản mod',
       'duplicate': 'Cùng một câu game với tab %s dòng %s nhưng dịch khác - chỉ dùng được dòng kia',
       'same': 'Cùng một câu game và cùng bản dịch với tab %s dòng %s - đã ghi ở dòng kia'}
CLEANED = {'row': 'Ô là cả một dòng CSV dán vào (JP,%sVI): chỉ lấy phần VI - nên sửa ô trong sheet',
           'columns': 'Ô thừa các cột trống ",,,,," ở cuối: đã bỏ - nên sửa ô trong sheet',
           'comma': 'Ô bắt đầu bằng dấu phẩy: đã bỏ - nên sửa ô trong sheet',
           'name': 'Ô bắt đầu bằng tên người nói "%s,": đã bỏ tên - nên sửa ô trong sheet'}
TAG_FIXED = {'dashes': 'jp_text thiếu/thừa dấu ―― so với game (thay thế trên cả sheet?): đã khớp theo vị trí - '
                       'nên trả lại jp_text trong sheet',
             'brackets': 'jp_text đổi 《》 thành " (thay thế trên cả sheet?): đã khớp theo vị trí - '
                         'nên trả lại jp_text trong sheet',
             'broken': 'Tag #P hỏng (dấu phẩy bị dời ra ngoài, kiểu "#P(1110220),"): đã trả lại tag của câu JP - '
                       'nên sửa ô trong sheet',
             'offscreen': 'Tag #P đặt câu ra ngoài màn hình (JP làm vậy vì chữ đã vẽ sẵn trên ảnh): đã bỏ tag để câu '
                          'dịch hiện ra, không thì chỉ đọc được trong backlog - nên bỏ tag trong sheet'}
KEY_NOTE = ('Khoá từ điển (không hiện ra màn hình): sheet ghi "%s", đã ghi theo tiêu đề "%s" ở tab exe '
            'để game tìm được mục - nên sửa ô trong sheet cho giống')
KEY_JP = ('Khoá từ điển (không hiện ra màn hình): sheet ghi "%s" nhưng tiêu đề ở tab exe chưa dịch, '
          'exe giữ tiếng Nhật - đã giữ khoá tiếng Nhật để game tìm được mục')
FIT_NOTE = ('Nhiều hơn %d dòng so với ngắt ở 62 ký tự: có dòng rộng quá khung (khung thoại, mép màn hình '
            'tính từ #P, hoặc backlog) ở font rộng nhất trong mod')
FIT_P = '; câu có #P: xem câu nằm ngay dưới có bị đè không'
MERGE_NOTE = ('Đã nối các dòng xuống hàng trong ô thành một đoạn để câu còn tối đa 3 dòng (backlog chỉ chứa 3) '
              '- nên sửa ô trong sheet')
ROWS_NOTE = 'Câu vẫn có %d dòng, backlog chỉ chứa 3: nên rút gọn câu hoặc bớt xuống dòng trong ô'
CLEANED_SHORT = {'row': 'dong CSV', 'columns': 'cot trong cuoi o', 'comma': 'dau phay dau o', 'name': 'ten nguoi noi dau o'}


def write_report(path, report):
    with open(path, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f)
        w.writerow(['tab', 'dòng', 'record_id', 'script', 'const_index', 'kết quả', 'ghi chú'])
        for x in report:
            r = x['r']; notes = []
            for k in x.get('fixed', ()):
                notes.append(TAG_FIXED[k])
            if x.get('csv'):
                vi, speaker, kind = x['csv']
                for k in kind.split('+'):
                    notes.append(CLEANED[k] % (('%s,' % speaker if speaker is not None else '') if k == 'row' else
                                               (speaker,) if k == 'name' else ()))
            if x['action'] == 'skip':
                other = lambda: (x['other']['tab'], x['other']['row'])
                args = {'duplicate': other, 'same': other, 'japanese': lambda: (x['chars'],)}
                notes.append(WHY[x['why']] % args.get(x['why'], tuple)())
            else:
                if x.get('key'):
                    had, title = x['key']
                    notes.append(KEY_NOTE % (had, title) if title else KEY_JP % had)
                for ch, how in x['unknown']:
                    notes.append('Font chưa có chữ %s (%s)' % (ch, 'dùng chữ thường' if how == 'lower' else 'để nguyên'))
                if x.get('fit', 0) > 0:
                    notes.append(FIT_NOTE % x['fit'] + (FIT_P if tags.P.search(r['vi'] or '') else ''))
                if x.get('merged'):
                    notes.append(MERGE_NOTE)
                if x.get('rows'):
                    notes.append(ROWS_NOTE % x['rows'])
            if x['action'] == 'write' and not notes:
                continue
            w.writerow([r['tab'], r['row'], r['rid'], r['script'], r['ci'],
                        'ghi' if x['action'] == 'write' else 'bỏ qua', '; '.join(notes)])


def sync_keys(jp, jp_strs, exe, list_path, fmap):
    """{(script, index): (text, VI title)} for every glossary key, or {} with
    a word on why the keys are written as the sheet has them."""
    found = dict_keys(jp)
    if not found:
        return {}
    skip = 'khoa tu dien: %s - ghi khoa dung nhu sheet, game co the khong tim thay muc'
    if not exe:
        print(skip % 'khong co exefs/main'); return {}
    try:
        titles = glossary_keys(exe, list_path, fmap)
    except SystemExit as e:
        print(skip % ('khong doc duoc tieu de (%s)' % e)); return {}
    if not titles:
        print(skip % ('exe khong co bang tu dien o 0x%x' % exetext.GLOSSARY)); return {}
    keys, lost = {}, []
    for s, i in sorted(found):
        jk = jp_strs[s][i]
        if jk in titles:
            keys[(s, i)] = titles[jk]
        else:
            lost.append('%s #%d %s' % (s, i, jk))
    if lost:
        print('khoa tu dien khong co muc nao trung ten (ghi nhu sheet): %s' % ', '.join(lost))
    return keys


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--sheet', required=True, help='translation sheet (.xlsx)')
    ap.add_argument('--jp', required=True, help='folder with the JP script.memfs/membody')
    ap.add_argument('--mod', required=True, help='VI mod folder (font, exe, names)')
    ap.add_argument('--out', required=True, help='output folder')
    ap.add_argument('--exe', help='patched exefs/main (default: <mod>/exefs/main if present)')
    ap.add_argument('--map', help='save the learnt font encoding to this JSON file')
    ap.add_argument('--use-map', help='read the font encoding from this JSON file')
    ap.add_argument('--exe-list', help='glossary titles: the exetext list (address, jp_text, vi_text), '
                                       'default the --sheet\'s own exe tab')
    ap.add_argument('--fonts', help='font folder the lines are wrapped for (default <mod>/romfs/spec_win/font)')
    ap.add_argument('--chars', type=int, default=0,
                    help='also cap a line at this many visible characters (62 = the old count); default none: '
                         'each line is filled up to its box')
    ap.add_argument('--max-lines', type=int, default=overflow.LOG_LINES,
                    help='a string with more lines gets the line breaks of its cell joined where that saves lines '
                         '(the backlog holds %d); 0 keeps every break' % overflow.LOG_LINES)
    ap.add_argument('--chars-only', action='store_true',
                    help='wrap at 62 characters only, as the old builder did, without measuring the fonts')
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

    faces = None
    if not a.chars_only:
        folder = a.fonts or os.path.join(a.mod, 'romfs', 'spec_win', 'font')
        try:
            faces = overflow.story_faces(folder)
            print('ngat dong: lap day toi mep khung o font rong nhat%s, toi da %s dong (%s)' % (
                ', toi da %d ky tu' % a.chars if a.chars else '', a.max_lines or 'khong gioi han', folder))
        except SystemExit as e:
            if a.fonts:
                raise
            print('ngat dong: chi theo 62 ky tu (%s)' % e)
    keys = sync_keys(jp, jp_strs, exe, a.exe_list or a.sheet, fmap)
    writes, report = plan(rows, jp_strs, fmap, seen, keys, faces, a.chars, a.max_lines)
    if keys:
        changed = [x for x in report if x.get('key')]
        print('khoa tu dien: %d khoa ghi theo tieu de; %d dong sheet khac tieu de (xem --report)' % (
            len(keys), len(changed)))
    why = collections.Counter(x['why'] for x in report if x['action'] == 'skip')
    print('ghi %d chuoi vao %d script; bo qua: jp khong khop %d, chua dich %d, con sot chu Nhat %d, '
          'trung cau dich khac %d, trong %d' % (
              sum(len(w) for w in writes.values()), len(writes), why['jp-mismatch'], why['untranslated'],
              why['japanese'], why['duplicate'], why['empty']))
    refit = [x for x in report if x.get('refit')]
    if refit:
        grown = [x for x in refit if x['fit'] > 0]
        print('ngat dong khac 62 ky tu: %d chuoi; it dong hon %d, nhieu dong hon %d (%d co #P: xem cau ngay duoi), '
              'noi dong trong o de con %d dong %d - xem --report' % (
                  len(refit), sum(1 for x in refit if x['fit'] < 0), len(grown),
                  sum(1 for x in grown if tags.P.search(x['r']['vi'] or '')), a.max_lines or overflow.LOG_LINES,
                  sum(1 for x in refit if x['merged'])))
    if faces and a.max_lines:
        print('con qua %d dong (backlog chi chua %d): %d chuoi - nen sua ban dich, xem --report' % (
            a.max_lines, a.max_lines, sum(1 for x in report if x.get('rows'))))
    unknown = collections.Counter(ch for x in report if x['action'] == 'write' for ch, _ in x['unknown'])
    if unknown:
        print('font chua co: %s' % ', '.join('U+%04X x%d' % (ord(ch), n) for ch, n in unknown.most_common()))
    pasted = collections.Counter(k for x in report if x.get('csv') for k in x['csv'][2].split('+'))
    if pasted:
        tabs = sorted(set(x['r']['tab'] for x in report if x.get('csv')))
        print('o con sot cua file CSV cu, chi ghi phan cau dich: %s (%d tab: %s) - nen sua trong sheet, xem --report' % (
            ', '.join('%s %d' % (CLEANED_SHORT[k], pasted[k]) for k in CLEANED_SHORT if pasted[k]),
            len(tabs), ', '.join(tabs)))
    fixed = collections.Counter(k for x in report if x['action'] == 'write' for k in x.get('fixed', ()))
    if fixed['dashes']:
        print('jp_text khac game chi o dau ――: %d dong, da khop theo vi tri (xem --report)' % fixed['dashes'])
    if fixed['brackets']:
        print('jp_text doi 《》 thanh ": %d dong, da khop theo vi tri (xem --report)' % fixed['brackets'])
    print('tag: ghi nhu sheet, tru %d #P dua cau ra ngoai man hinh (da bo) va %d #P hong (da tra tag JP) - '
          'xem --report; kiem tag bang audit.py (Kiem tra ban patch)' % (fixed['offscreen'], fixed['broken']))

    body, mem, rep = build(jp, mod, writes)
    print('noi rong u16 -> u32: %s' % (', '.join(rep['widened']) or 'khong'))
    print('membody %d -> %d byte, memfs %d -> %d byte' % (len(mod.body), len(body), len(mod.memfs), len(mem)))

    problems = patch.verify(body, mem, jp, redirects, check_tags=False)
    if problems:
        print('KIEM TRA LOI:'); [print('  ' + x) for x in problems]
        return 1
    print('kiem tra: OK (code giong JP, so chuoi khop, moi kich ban mo duoc)')
    if a.report:
        write_report(a.report, report)
        print('bao cao -> %s' % a.report)
    if not a.apply:
        patch.say_replaced(a.out, ('script.membody', 'script.memfs'))
        print('chay thu - them --apply de ghi vao %s' % a.out)
        return 0
    patch.write_files(a.out, (('script.membody', body), ('script.memfs', mem)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
