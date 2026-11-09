# -*- coding: utf-8 -*-
"""overflow.py - find the lines that run out of their box in game.

    python overflow.py --mod <mod folder> [--map font_map.json] [--csv tran_khung.csv]
    python overflow.py --mod <mod folder> --font standard --name "Nguyệt Ánh" --margin 10

The engine never wraps a line and never clips one to its box: a line breaks
only where the string has a line break, and a line that is too wide runs on
over the art or off the screen. The Vietnamese scripts are wrapped at 62
characters (tags.WRAP), which the old patch font fitted; a wider font pushes
the long lines out.

The tool lays every line out the way the game does - advance after advance,
in the mod's own fonts, no kerning - and compares it with the room it has
where it is shown:

  screen    a story line after #P(x,y): from x to the screen's edge
  window    a story line without #P: the message window          (estimate)
  backlog   every story line and choice again, in the backlog
  glossary  a glossary description from exefs/main (exetext.py)
  choice    a choice (SltAdd), centred on its button             (estimate)

Story text is drawn in the font chosen on the settings screen (一 二 三 四 =
standard, extra, extra2, extra3), so each line is measured in each of them
(--font picks some) and reported with the widest. The glossary always uses
extra2. #T1/#T2 variants are measured one at a time, ${FirstName} as --name.

The numbers are measured on screenshots of the game (CLAUDE.md "Line
widths"): story text and the glossary are drawn at 1.05 of the font's
pixels, the backlog at 0.9; the backlog's narration box holds text from
x 240 to the name strip at x 1258, the glossary popup from 576 to the
paper's edge at 1362. The message window and the choice buttons were read
off their art, never seen with a long line: treat those findings as likely.

Output: per box, how many strings run out; per font, the lines over, how
many characters a line holds and how much narrower the font must get for
99% of the lines to fit (many lines over at once is a font size question,
not a translation one); the worst lines of each box. --csv lists
each such string with its script and index (the sheet's const_index; for
the glossary its address in the exetext list), the boxes and how many px it
runs over, and a re-wrap that fits every box it shows in (strings with one
position and no #T). --map decodes the text for reading. Nothing is changed.
"""
import argparse
import csv
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kuv       # noqa: E402
import memfs     # noqa: E402
import tags      # noqa: E402


class Box(object):
    """Where a line is drawn: from x (None: the #P x of the line) to right, at
    scale times the font's pixels. All in 1920x1080 screen pixels."""

    def __init__(self, key, label, x, right, scale, estimate=False):
        self.key, self.label, self.x, self.right, self.scale, self.estimate = key, label, x, right, scale, estimate

    def over(self, width, x=None, margin=0):
        """Screen px a line `width` font px wide runs past the box (<= 0: fits)."""
        return (self.x if x is None else x) + width * self.scale - (self.right - margin)

    def room(self, x=None, margin=0):
        """Font px a line may take (at least 1)."""
        return max(1.0, (self.right - margin - (self.x if x is None else x)) / self.scale)


STORY_SCALE = 1.05     # 42 px text from the 40 px fonts: 1.047-1.048 fitted on two lines
LOG_SCALE = 0.90       # the backlog draws the same font at 36 px
BOXES = [
    Box('screen', 'màn hình (#P)', None, tags.SCREEN_W, STORY_SCALE),
    # text_atari of advwin (48x48 at 167..215) to the page arrow mat_adwin_okuri (x 1374..1474)
    Box('window', 'khung thoại', 170, 1374, STORY_SCALE, estimate=True),
    # mat_log_event_texbase spans x 160..1374; text from 240, the cyan name strip from 1258
    Box('backlog', 'backlog', 240, 1258, LOG_SCALE),
    # mat_advjisyo_base spans 454..1466 with the roller; text from 576, the paper ends at 1362
    Box('glossary', 'từ điển', 576, 1362, STORY_SCALE),
    # mat_advsen_texbase is 840 wide; text centred, 40 px kept clear each side
    Box('choice', 'lựa chọn', 0, 760, STORY_SCALE, estimate=True),
]
BOX = dict((b.key, b) for b in BOXES)
SETTINGS = ('standard', 'extra', 'extra2', 'extra3')    # the settings screen's フォント 一 二 三 四
GLOSSARY_FONT = 'extra2'
GLOSSARY_TABLE = 0x5557d0   # JP 1.0.0 .data: 32-byte entries {u32 heading kana, 0, term*, description*, ...}
MISSING = 40                # a character the font lacks is counted as a full cell

HIDDEN = re.compile(r'#C\([^)]*\)|#R\([^)]*\)|#KW')
T_TAG = re.compile(r'(#T[012])')
NEWLINE = re.compile(r'\r?\n')
CHOICE_CODE = re.compile(r'^【[^】]*】')          # 【N2】 before a choice: a route code, not drawn


class Face(object):
    """The advances of one font."""

    def __init__(self, name, adv):
        self.name, self.adv = name, adv

    @classmethod
    def load(cls, path, name=None):
        import font
        f = font.Font.load(path)
        return cls(name or f.name, dict((ch, f.glyphs[i].adv) for ch, i in f.char_index.items()))

    def width(self, text):
        return sum(self.adv.get(c, MISSING) for c in text)

    def missing(self, text):
        return set(c for c in text if c not in self.adv and not c.isspace())


def visible(line, name):
    """What the game draws of one line: tags as nothing, the heroine's name filled in."""
    return HIDDEN.sub('', line).replace('${FirstName}', name)


def variants(s):
    """[(label, text)] per name variant: #T1 parts show with the default name,
    #T2 parts with one the player typed, the rest (#T0) with both."""
    if not T_TAG.search(s):
        return [('', s)]
    out = []
    for v in '12':
        keep, mode = [], '0'
        for part in T_TAG.split(s):
            if T_TAG.match(part):
                mode = part[2]
            elif mode in ('0', v):
                keep.append(part)
        out.append(('#T' + v, ''.join(keep)))
    return out


def blocks(text):
    """[(x, y, lines)] of one variant: text before any #P goes to the message
    window (x None)."""
    parts = tags.P.split(text)
    out = []
    if parts[0].strip():
        out.append((None, None, NEWLINE.split(parts[0])))
    for k in range(1, len(parts), 3):
        out.append((int(parts[k]), int(parts[k + 1]), NEWLINE.split(parts[k + 2])))
    return out


class Finding(object):
    """One string that runs out of at least one box."""

    def __init__(self, where, index, call, text):
        self.where, self.index, self.call, self.text = where, index, call, text
        self.worst = {}          # box key -> (over px, font, line)
        self.lines = {}          # box key -> lines over
        self.fonts = set()       # fonts it runs out in
        self.measured = set()    # fonts it was measured in
        self.suggestion = ''
        self.note = ''

    @property
    def everywhere(self):
        """Runs out in every font it shows in: the line's fault, not a font's."""
        return self.fonts == self.measured

    def fonts_text(self):
        return 'mọi font' if self.everywhere else 'chỉ ' + ', '.join(sorted(self.fonts))

    def add(self, box, over, face, line):
        self.lines[box] = self.lines.get(box, 0) + 1
        if box not in self.worst or over > self.worst[box][0]:
            self.worst[box] = (over, face, line)

    @property
    def over(self):
        return max(w[0] for w in self.worst.values())

    def top(self):
        return max(self.worst.items(), key=lambda kv: kv[1][0])


class Tally(object):
    """Per font: lines over per box, the px a character of a long line takes,
    and how full each line is (width / room of its tightest box)."""

    LONG = 40            # visible characters: a line the wrap filled
    SHARE = 0.99         # lines a font should fit, for shrink()

    def __init__(self):
        self.over = {}   # (font, box key) -> lines
        self.px = {}     # font -> [width, characters] of long lines
        self.fill = {}   # font -> [width / room per line]

    def line(self, font, vis, width, fill):
        if len(vis) >= self.LONG:
            p = self.px.setdefault(font, [0, 0])
            p[0] += width
            p[1] += len(vis)
        if fill is not None:
            self.fill.setdefault(font, []).append(fill)

    def hit(self, font, box):
        self.over[font, box] = self.over.get((font, box), 0) + 1

    def per_char(self, font):
        w, n = self.px.get(font, (0, 0))
        return float(w) / n if n else 0.0

    def shrink(self, font):
        """Percent narrower the font must get for SHARE of the lines to fit (0: they do)."""
        f = sorted(self.fill.get(font, ()))
        if not f:
            return 0
        r = f[int(self.SHARE * (len(f) - 1))]
        return 0 if r <= 1 else -(-100 * (r - 1) // r)


def boxes_for(kind, x, y):
    """[(box, x)] a line of a block at (x, y) is drawn in."""
    if kind == 'choice':
        return [(BOX['choice'], None), (BOX['backlog'], None)]
    if x is None:
        out = [(BOX['window'], None)]
    elif tags.offscreen(x, y):
        out = []                         # hidden on purpose (text painted on the art); logged only
    else:
        out = [(BOX['screen'], x)]
    return out + [(BOX['backlog'], None)]


def measure(finding, kind, s, faces, name, margin, missing, tally):
    """Lay out every line of story string s in every face; fill finding and
    tally. -> True if any line runs over."""
    hit = False
    finding.measured.update(f.name for f in faces)
    for _, text in variants(s):
        for x, y, lines in blocks(text):
            seen = set()
            for line in lines:
                vis = visible(line, name)
                if not vis.strip() or vis in seen:
                    continue
                seen.add(vis)
                widths = []
                shown = boxes_for(kind, x, y)
                for f in faces:
                    w = f.width(vis)
                    widths.append((w, f))
                    missing.update(f.missing(vis))
                    tally.line(f.name, vis, w, max(w / box.room(bx, margin) for box, bx in shown) if shown else None)
                for box, bx in shown:
                    overs = [(box.over(w, bx, margin), f) for w, f in widths]
                    for o, f in overs:
                        if o > 0:
                            tally.hit(f.name, box.key)
                            finding.fonts.add(f.name)
                    o, f = max(overs, key=lambda of: of[0])
                    if o > 0:
                        finding.add(box.key, o, f.name, line)
                        hit = True
    return hit


def wrap_words(lines, room, width):
    """Lines refilled greedily so each is at most room wide (a word wider
    than room stays alone on its line)."""
    out, cur = [], ''
    for w in ' '.join(l.strip() for l in lines if l.strip()).split(' '):
        if not w:
            continue
        if cur and width(cur + ' ' + w) > room:
            out.append(cur)
            cur = w
        else:
            cur = (cur + ' ' + w) if cur else w
    if cur:
        out.append(cur)
    return out


def rewrap(s, kind, faces, name, margin):
    """(string re-wrapped to fit every box it shows in with the widest face,
    note), or ('', '') when it has #T variants or several positions."""
    if len(variants(s)) != 1:
        return '', ''
    bl = blocks(s)
    if len(bl) != 1:
        return '', ''
    x, y, lines = bl[0]
    room = min(box.room(bx, margin) for box, bx in boxes_for(kind, x, y))
    out = wrap_words(lines, room, lambda t: max(f.width(visible(t, name)) for f in faces))
    head = '' if x is None else '#P(%d,%d)' % (x, y)
    old = len([l for l in lines if l.strip()])
    note = ''
    if len(out) > old:
        note = 'thêm %d dòng' % (len(out) - old)
        if x is not None:
            note += ': xem câu nằm ngay dưới có bị đè không'
    return head + '\n'.join(out), note


# ------------------------------------------------------------------ the game

def story(archive):
    """[(script name, index, call, kind, text)] of every message and choice string."""
    out = []
    for p in sorted(archive.entries):
        raw = archive.raw(p)
        if not kuv.is_kuv(raw):
            continue
        strs = kuv.parse(raw)[1]
        done = set()
        for f, args, _ in kuv.calls(raw):
            if not args or args[-1] in done:
                continue
            if f in tags.MESSAGE_CALLS:
                kind, text = 'story', strs[args[-1]]
            elif f == 'SltAdd':
                kind, text = 'choice', CHOICE_CODE.sub('', strs[args[-1]])
            else:
                continue
            done.add(args[-1])
            out.append((memfs.script_name(p)[:-4], args[-1], f, kind, text))
    return out


def relocations(img):
    """{place: target} of the RELATIVE relocations of an unpacked NSO."""
    import exetext
    dyn = exetext.dynamic(img)
    out = {}
    if 7 not in dyn:
        return out
    rela, size, ent = dyn[7], dyn.get(8, 0), dyn.get(9, 24) or 24
    for q in range(rela, rela + size, ent):
        off, info, add = struct.unpack_from('<QQq', img, q)
        if info & 0xffffffff == exetext.R_AARCH64_RELATIVE:
            out[off] = add
    return out


def glossary(exe, table=GLOSSARY_TABLE):
    """[(entry, term address, description address)] of the glossary table,
    addresses of the Japanese strings (exe.img is the program before exetext)."""
    img, rel = exe.img, relocations(exe.img)
    out, a = [], table
    while a + 32 <= len(img):
        kana, zero = struct.unpack_from('<2I', img, a)
        term, desc = rel.get(a + 8), rel.get(a + 16)
        if not 0x3041 <= kana <= 0x30ff or zero or term not in exe.strings or desc not in exe.strings:
            break
        out.append((a, term, desc))
        a += 32
    return out


def check_glossary(exe, face, decode, margin, missing, table=GLOSSARY_TABLE):
    """-> (findings, entries, translated). A description keeps its own line
    breaks; the suggestion only splits the lines that are too wide."""
    box = BOX['glossary']
    entries = glossary(exe, table)
    found, translated = [], 0
    for _, term, desc in entries:
        vi = exe.current_text(desc)
        if vi is None:
            continue                     # still Japanese: JP fits by design
        translated += 1
        t = exe.current_text(term) or exe.strings[term]
        fd = Finding('exefs/main', '0x%x' % desc, 'từ điển: ' + decode(visible(t, '')), vi)
        fd.measured.add(face.name)
        out = []
        for line in NEWLINE.split(vi):
            vis = visible(line, '')
            missing.update(face.missing(vis))
            over = box.over(face.width(vis), None, margin)
            if over > 0:
                fd.add(box.key, over, face.name, line)
                fd.fonts.add(face.name)
                out += wrap_words([line], box.room(None, margin), lambda s: face.width(visible(s, '')))
            else:
                out.append(line)
        if fd.worst:
            fd.suggestion = '\n'.join(out)
            found.append(fd)
    return found, len(entries), translated


# ------------------------------------------------------------------ files

def find_fonts(folder, wanted):
    """{name: path} of the wanted fonts in folder; SystemExit naming what is missing."""
    have = dict((n, os.path.join(folder, n + '.font.memfs')) for n in wanted)
    lost = [n for n, p in have.items() if not os.path.isfile(p)]
    if lost:
        raise SystemExit('LOI: %s khong co %s' % (folder, ', '.join(n + '.font.memfs' for n in lost)))
    return have


def where_text(fd):
    return '; '.join('%s +%d px (%d dòng)%s' % (BOX[k].label, round(v[0]), fd.lines[k],
                                                ', khung ước lượng' if BOX[k].estimate else '')
                     for k, v in sorted(fd.worst.items(), key=lambda kv: -kv[1][0]))


def write_csv(path, findings, decode):
    with open(path, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(['script', 'index', 'call', 'box', 'over_px', 'font', 'fonts', 'line', 'text', 'suggestion', 'note'])
        for fd in findings:
            _, (over, face, line) = fd.top()
            w.writerow([fd.where, fd.index, fd.call, where_text(fd), round(over), face, fd.fonts_text(), decode(line),
                        decode(fd.text), decode(fd.suggestion), fd.note])


def say_kinds(findings, names):
    """One translation serves every font, so a string should run out in all
    of them (fix the line) or in none. Strings that run out in only some
    mean the fonts are not equally wide yet (fix the fonts)."""
    story = [fd for fd in findings if len(fd.measured) > 1]
    if len(names) < 2 or not story:
        return
    some = [fd for fd in story if not fd.everywhere]
    print('\nkieu tran (%d font, mot ban dich):' % len(names))
    print('  tran o moi font        %5d cau  - loi cua cau: sua ban dich' % (len(story) - len(some)))
    print('  chi tran o mot so font %5d cau  - font chua deu nhau: chinh co / be ngang font%s' % (
        len(some), (' (%s)' % ', '.join('%s %d' % (n, sum(1 for fd in some if n in fd.fonts)) for n in names)) if some else ''))


def say_fonts(tally, names, margin):
    """Per font: lines over per box and how many characters a line holds."""
    room = BOX['backlog'].room(None, margin)
    win = BOX['window'].room(None, margin)
    print('\ntheo font (dong tran: man hinh / khung thoai / backlog / lua chon):')
    for n in names:
        pc = tally.per_char(n)
        fit = ''
        if pc:
            fit = ('%.1f px/chu, mot dong vua ~%d chu o backlog, ~%d o khung thoai (kich ban ngat %d)'
                   % (pc, room / pc, win / pc, tags.WRAP))
            cut = tally.shrink(n)
            if cut:
                fit += ' - hep lai ~%d%% thi %d%% so dong vua' % (cut, 100 * Tally.SHARE)
        print('  %-9s %5d / %5d / %5d / %3d   %s' % (n, tally.over.get((n, 'screen'), 0), tally.over.get((n, 'window'), 0),
                                                  tally.over.get((n, 'backlog'), 0), tally.over.get((n, 'choice'), 0), fit))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--mod', required=True, help='VI mod folder (romfs/common/script.*, romfs/spec_win/font, exefs/main)')
    ap.add_argument('--fonts', help='font folder; default <mod>/romfs/spec_win/font')
    ap.add_argument('--font', action='append', choices=SETTINGS,
                    help='settings font(s) to measure story text with; default all four')
    ap.add_argument('--exe', help='exefs/main; default the mod\'s (read redirects, glossary)')
    ap.add_argument('--map', help='font encoding (.json, applysheet --map): show the text decoded')
    ap.add_argument('--name', default='Naya', help='heroine name for ${FirstName} (default Naya)')
    ap.add_argument('--margin', type=float, default=0, help='also report lines closer than this many px to the edge')
    ap.add_argument('--window-right', type=float, help='right edge of message window text (estimate: %d)' % BOX['window'].right)
    ap.add_argument('--csv', help='every string that runs out, with a re-wrap')
    ap.add_argument('--top', type=int, default=5, help='worst lines to print per box (default 5)')
    a = ap.parse_args(argv)

    from patch import find_exe, find_pair
    if a.window_right:
        BOX['window'].right = a.window_right
    fonts_dir = a.fonts or os.path.join(a.mod, 'romfs', 'spec_win', 'font')
    exe_path = a.exe or find_exe(a.mod)
    if a.map:
        import exetext
        fmap = exetext.load_map(a.map)
        decode = lambda t: exetext.decode(t, fmap)
        name = exetext.encode(a.name, fmap)[0]
    else:
        decode = lambda t: t
        name = a.name

    names = a.font or list(SETTINGS)
    paths = find_fonts(fonts_dir, sorted(set(names) | {GLOSSARY_FONT}) if exe_path else names)
    faces = dict((n, Face.load(p, n)) for n, p in paths.items())
    story_faces = [faces[n] for n in names]
    print('font: %s (%s)' % (', '.join(names), fonts_dir))

    archive = memfs.Archive(*find_pair(a.mod), redirects=memfs.load_redirects(exe_path))
    strings = story(archive)
    missing, tally, findings = set(), Tally(), []
    for script, idx, call, kind, s in strings:
        fd = Finding(script, idx, call, s)
        if measure(fd, kind, s, story_faces, name, a.margin, missing, tally):
            fd.suggestion, fd.note = rewrap(s, kind, story_faces, name, a.margin)
            findings.append(fd)
    print('kich ban: %d file, %d cau thoai va lua chon' % (len(set(s[0] for s in strings)), len(strings)))

    if exe_path:
        import exetext
        exe = exetext.open_exe(exe_path)
        if not exe.current:
            print('tu dien: exe chua co ban dich cua exetext.py - bo qua')
        else:
            got, n, done = check_glossary(exe, faces[GLOSSARY_FONT], decode, a.margin, missing)
            if not n:
                print('tu dien: khong thay bang tu dien o 0x%x - bo qua' % GLOSSARY_TABLE)
            else:
                print('tu dien: %d muc, %d muc da dich (font %s)' % (n, done, GLOSSARY_FONT))
                findings += got
    else:
        print('tu dien: khong co exefs/main - bo qua')

    findings.sort(key=lambda fd: -fd.over)
    print('\ncau tran khung (cau / dong), font rong nhat:')
    for b in BOXES:
        n = sum(1 for fd in findings if b.key in fd.worst)
        lines = sum(fd.lines.get(b.key, 0) for fd in findings)
        print('  %-16s %5d / %5d%s' % (b.label, n, lines, '   (khung uoc luong)' if b.estimate else ''))
    say_kinds(findings, names)
    say_fonts(tally, names, a.margin)
    if missing:
        print('font khong co: %s (tinh rong %d px moi chu)' % (''.join(sorted(decode(c) for c in missing)), MISSING))
    for b in BOXES if a.top else ():
        worst = sorted((fd for fd in findings if b.key in fd.worst), key=lambda fd: -fd.worst[b.key][0])[:a.top]
        if worst:
            print('\n%s - lo nhieu nhat:' % b.label)
        for fd in worst:
            over, face, line = fd.worst[b.key]
            print('  %-13s %-8s +%4d px  %-8s %s' % (fd.where, fd.index, round(over), face, decode(visible(line, name))))
    if a.csv:
        write_csv(a.csv, findings, decode)
        print('-> %s (%d cau)' % (a.csv, len(findings)))
    if not findings:
        print('khong cau nao tran khung')
    return 0


if __name__ == '__main__':
    sys.exit(main())
