# -*- coding: utf-8 -*-
"""sprite.py - UI art painted into textures: the archives under romfs/spec_win/ssdata.

    python sprite.py translate ttlm_nam.memfs anh/   # empty folder: take the images out
    # ... redraw the cells you translate inside anh/, saving over the same files ...
    python sprite.py translate ttlm_nam.memfs anh/ --out <mod>/romfs/spec_win/ssdata           # dry run
    python sprite.py translate ttlm_nam.memfs anh/ --out <mod>/romfs/spec_win/ssdata --apply   # write
    python sprite.py translate ttlm_nam.memfs        # no folder: only list the cells
    python sprite.py check  ttlm_nam.memfs

The app has the two halves as two tools: export (take out; no folder = only
list) and import (put back), and fills import's screen and folder in from
the export it just ran. `translate` does either, picked by the folder.

The membody is read from next to the memfs unless --body names it.

Menu labels, buttons and help lines of the title menu, options, backlog and
other screens are pixels, not strings: there is nothing to translate in a
sheet. Each screen is a memfs/membody pair holding .rtex textures, one
SpriteStudio .ssdata and an .rson. The .ssdata says which rectangle of which
texture every sprite part draws, so a texture splits into named cells:
mat_ttlm_com01_off is the 新しく始める label, mat_ttlm_com01_setu its help line.

export   lists every texture and its cells - file name, place, size, parts.
         Given a folder it also writes every texture as <texture>.png and
         every cell as <texture>/<part>.png (<part>_<x>_<y>.png when the part
         draws several cells, plus _<w>x<h> when they share that corner),
         plus cells_<screen>.csv with the same list. Into a folder that
         already holds any of them it writes nothing unless --overwrite: the
         run names the files that differ from the game (cells someone
         redrew), and with --overwrite each of those is copied to <name>.bak
         beside it first. (`list` = export, no folder.)
import   reads that folder back. A cell PNG that differs from the game's
         pixels is pasted at its rectangle; a <texture>.png that differs
         replaces the whole texture first, so an edited cell wins over it.
         A cell PNG of another size (a label grown to fit longer Vietnamese)
         goes to an empty place of the same texture, and every part state
         that drew the old rectangle is pointed at the new one. Parts are
         drawn centred on their position, so the label grows evenly round
         the same centre. Only cells whose states hold nothing but position,
         rotation, scale and alpha can change size (ROUND_CENTRE); the old
         rectangle keeps its pixels.
         Without --apply it only reports. The result is opened again and
         checked: untouched files byte for byte, changed textures pixel for
         pixel, a changed .ssdata only in states' x, y, w, h. A file already
         in --out is first copied beside it, to
         <name>.bak (or .bak2, .bak3 ... if that is taken); the dry run names
         each file and its copy (`se thay file da co`), and the app shows
         them when it asks.
check    rebuilds the archive unchanged (must match byte for byte) and
         round-trips every texture it can edit.

Only plain RGBA8 textures (format byte 0x02, not block-compressed) can be
written; every UI atlas of this game is one. BC-compressed backgrounds and
the 8/16/24-bit transition masks are listed and skipped.

Needs Pillow (pip install Pillow).
"""
import argparse
import csv
import io
import os
import re
import shutil
import struct
import sys
import tempfile
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rson  # noqa: E402
from patch import backup_name, say_replaced, write_files  # noqa: E402

RTEX_HEAD = 0x20
FMT_RGBA8 = 0x02
BLOCK_COMPRESSED = 0x80000
STATE_SIZE = 40
STATE_RECT = 6                          # u16 x, y, w, h inside a state
# State flags whose fields only turn, scale or fade a part round its position,
# read from their values: 0x40 a float in degrees, 0x80 / 0x100 floats near 1,
# 0x200 0..255. A part whose states carry nothing else is drawn centred on its
# position, so its cell can change size without the part moving. 0x10 / 0x20
# add an i16 each (maybe a pivot or a size in pixels) and are not in it.
ROUND_CENTRE = 0x40 | 0x80 | 0x100 | 0x200
CELL_GAP = 4                            # empty pixels kept round a cell moved to new space


def need_pil():
    try:
        from PIL import Image
    except ImportError:
        raise SystemExit('can Pillow: pip install Pillow')
    return Image


# --- .rtex -----------------------------------------------------------------

class Texture(object):
    """'RTEX' u32 0 | u16 w, h, padded w, padded h | u32 0x20 (header size),
    payload size, flags, row stride | payload: 'RZ' u32 BE size + zlib, or raw.
    Flags: low byte 0x02 RGBA8, 0x14 RGB8, 0x28 8-bit, 0x33 16-bit;
    0x80000 marks block compression (BC), the pixels are not rows then."""

    def __init__(self, data):
        if data[:4] != b'RTEX':
            raise ValueError('not RTEX (%r)' % data[:4])
        (_, self.w, self.h, self.pw, self.ph, hsize, self.psize, self.flags,
         self.stride) = struct.unpack_from('<I4H4I', data, 4)
        if hsize != RTEX_HEAD or self.psize != len(data) - RTEX_HEAD:
            raise ValueError('RTEX header: size %d, payload %d, file %d' % (hsize, self.psize, len(data)))
        self.data = data
        self.rz = data[RTEX_HEAD:RTEX_HEAD + 2] == b'RZ'

    @property
    def editable(self):
        return (self.flags & 0xff) == FMT_RGBA8 and not self.flags & BLOCK_COMPRESSED

    def why_not(self):
        if self.flags & BLOCK_COMPRESSED:
            return 'nen khoi (BC), flags %#x' % self.flags
        return 'dinh dang %#x, khong phai RGBA8' % (self.flags & 0xff)

    def raw(self):
        p = self.data[RTEX_HEAD:]
        if self.rz:
            size = int.from_bytes(p[2:6], 'big')
            raw = zlib.decompress(p[6:])
            if len(raw) != size:
                raise ValueError('RZ says %d bytes, got %d' % (size, len(raw)))
        else:
            raw = p
        if self.editable and len(raw) != self.stride * self.ph:
            raise ValueError('RGBA8 texture of %d bytes, expected %d' % (len(raw), self.stride * self.ph))
        return raw

    def image(self, raw=None):
        Image = need_pil()
        raw = self.raw() if raw is None else raw
        return Image.frombuffer('RGBA', (self.w, self.h), raw, 'raw', 'RGBA', self.stride, 1).copy()

    def rebuild(self, img):
        """The same texture with img's pixels; the padding past w x h is kept."""
        if img.size != (self.w, self.h):
            raise ValueError('image is %dx%d, texture %dx%d' % (img.size + (self.w, self.h)))
        raw = bytearray(self.raw())
        px = img.convert('RGBA').tobytes()
        row = self.w * 4
        for y in range(self.h):
            raw[y * self.stride:y * self.stride + row] = px[y * row:(y + 1) * row]
        raw = bytes(raw)
        payload = b'RZ' + len(raw).to_bytes(4, 'big') + zlib.compress(raw, 6) if self.rz else raw
        head = bytearray(self.data[:RTEX_HEAD])
        struct.pack_into('<I', head, 0x14, len(payload))
        return bytes(head) + payload


# --- .ssdata ---------------------------------------------------------------

def states(data):
    """Yield (state offset, texture name, part name) for every part state a
    frame of a SpriteStudio .ssdata draws (w and h not 0), once per pack.

    'SSAD1.03' | u32 header size H | u32 16 | u32 pack offsets, 0-terminated
    part states, 40 bytes each from H: u32 flags, u16 part, u16 x, y, w, h
        (source rectangle in the part's texture, pixels), i16 x, y position
        (from the screen centre, y down; the cell is drawn centred on it),
        then the fields the flags add (ROUND_CENTRE)
    pack: ff ff ff ff 'ABSS' u32 3, 0, parts, frames, textures | u16 parts,
        frames, fps
      textures: 0-terminated u32 pointers to names ('mat_ttlm.png')
      parts: 16 bytes - u32 name pointer, u16 index, parent, texture, is_null, u32
      frames: 12 bytes - u32 pointer to u16 state indices, u32 0, u32 count
    """
    if data[:8] != b'SSAD1.03':
        raise ValueError('not SSAD1.03 (%r)' % data[:8])

    def cstr(p):
        return data[p:data.index(b'\0', p)].decode('utf-8')

    hsize = struct.unpack_from('<I', data, 8)[0]
    for po in struct.unpack_from('<%dI' % ((hsize - 0x10) // 4), data, 0x10):
        if not po:
            break
        if data[po:po + 8] != b'\xff\xff\xff\xffABSS':
            raise ValueError('no ABSS pack at %#x' % po)
        _, _, parts_p, frames_p, tex_p, nparts, nframes, _ = struct.unpack_from('<5I3H', data, po + 8)
        texs = []
        while True:
            t = struct.unpack_from('<I', data, tex_p + 4 * len(texs))[0]
            if not t:
                break
            texs.append(cstr(t))
        parts = [struct.unpack_from('<I3H', data, parts_p + 16 * i) for i in range(nparts)]
        seen = set()
        for f in range(nframes):
            lp, _, cnt = struct.unpack_from('<3I', data, frames_p + 12 * f)
            for si in struct.unpack_from('<%dH' % cnt, data, lp):
                off = hsize + STATE_SIZE * si
                part, x, y, w, h = struct.unpack_from('<5H', data, off + 4)
                if si in seen or not (w and h):
                    continue
                seen.add(si)
                name_p, _, _, tex = parts[part]
                if tex >= len(texs):
                    raise ValueError('part %s uses texture %d of %d' % (cstr(name_p), tex, len(texs)))
                yield off, texs[tex], cstr(name_p)


def cells(data):
    """{(texture name, x, y, w, h): set of part names} drawn by a SpriteStudio
    .ssdata (layout in states())."""
    out = {}
    for off, tname, pname in states(data):
        rect = struct.unpack_from('<4H', data, off + STATE_RECT)
        out.setdefault((tname,) + rect, set()).add(pname)
    return out


def rects_only(old, new):
    """True when the .ssdata new differs from old only in the x, y, w, h of
    states a frame draws."""
    if len(old) != len(new):
        return False
    hsize = struct.unpack_from('<I', old, 8)[0]
    offs = set(off for off, _, _ in states(old))
    for i, (a, b) in enumerate(zip(old, new)):
        if a != b:
            off = hsize + (i - hsize) // STATE_SIZE * STATE_SIZE
            if i < hsize or off not in offs or not STATE_RECT <= i - off < STATE_RECT + 8:
                return False
    return True


# --- the archive -------------------------------------------------------------

def stem(path):
    return os.path.splitext(path.rsplit('/', 1)[-1])[0]


def safe(name):
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', name)


class Cell(object):
    def __init__(self, texture, x, y, w, h, parts, file):
        self.texture, self.x, self.y, self.w, self.h = texture, x, y, w, h
        self.parts, self.file = sorted(parts), file

    @property
    def box(self):
        return (self.x, self.y, self.x + self.w, self.y + self.h)

    def overlaps(self, o):
        return (self.texture == o.texture and self.box != o.box and self.x < o.x + o.w and o.x < self.x + self.w
                and self.y < o.y + o.h and o.y < self.y + self.h)


class Archive(object):
    """A memfs/membody pair whose files sit back to back in the body."""

    def __init__(self, memfs_path, body_path=None):
        body_path = body_path or os.path.splitext(memfs_path)[0] + '.membody'
        self.name = stem(memfs_path)
        with open(memfs_path, 'rb') as f:
            self.memfs = f.read()
        with open(body_path, 'rb') as f:
            self.body = f.read()
        self.root = rson.parse(self.memfs)
        self.entries = rson.entries(self.root)
        self.align = 1
        for k, v in self.root.items:
            if k.t == 'alignBytes':
                self.align = 1 if v.b == b'\x41' else (v.b[1] if v.b[:1] == b'\x48' else None)
        if not self.align:
            raise ValueError('alignBytes %r not understood' % v.b)
        self.files = dict((p, self.body[a.vals[0]:a.vals[0] + a.vals[1]]) for p, a in self.entries.items())
        self.textures = dict((p, Texture(d)) for p, d in self.files.items() if p.endswith('.rtex'))
        self.by_stem = dict((stem(p), p) for p in self.textures)
        self.cells, self.notes = self._cells()

    def _cells(self):
        found, notes = {}, []
        for p, d in sorted(self.files.items()):
            if p.endswith('.ssdata'):
                for k, parts in cells(d).items():
                    found.setdefault(k, set()).update(parts)
        out = []
        for (tname, x, y, w, h), parts in found.items():
            tp = self.by_stem.get(stem(tname))
            if not tp:
                notes.append('o %s(%d,%d %dx%d) dung %s, khong co trong goi' % (min(parts), x, y, w, h, tname))
                continue
            t = self.textures[tp]
            if x + w > t.w or y + h > t.h:
                notes.append('o %s(%d,%d %dx%d) vuot ra ngoai %s %dx%d' % (min(parts), x, y, w, h, tname, t.w, t.h))
                continue
            out.append(Cell(tp, x, y, w, h, parts, None))
        names = {}
        for c in out:
            names.setdefault((c.texture, c.parts[0]), []).append(c)
        for (tp, part), cs in names.items():
            at = {}
            for c in cs:
                at[c.x, c.y] = at.get((c.x, c.y), 0) + 1
            for c in cs:
                # One part may draw several cells from one corner (advwin's
                # mat_adwin_win: ten widths at 0,0); only those get the size.
                if len(cs) == 1:
                    base = part
                elif at[c.x, c.y] == 1:
                    base = '%s_%d_%d' % (part, c.x, c.y)
                else:
                    base = '%s_%d_%d_%dx%d' % (part, c.x, c.y, c.w, c.h)
                c.file = '%s/%s.png' % (safe(stem(tp)), safe(base))
        out.sort(key=lambda c: (c.texture, c.y, c.x, c.w, c.h))
        return out, notes

    def build(self, replaced):
        """(memfs, membody) with files of `replaced` ({path: bytes}) swapped in."""
        spans = sorted(set(tuple(a.vals) for a in self.entries.values()))
        pos, moved = 0, {}
        for off, size in spans:
            if off != pos:
                raise ValueError('%s: data at %d, expected %d - not laid back to back' % (self.name, off, pos))
            pos = off + size
            pos += -pos % self.align
        if pos < len(self.body) and self.body[pos:].strip(b'\0'):
            raise ValueError('%s: %d bytes after the last file' % (self.name, len(self.body) - pos))
        new = dict((tuple(a.vals), replaced.get(p, self.files[p])) for p, a in self.entries.items())
        body = bytearray()
        for span in spans:
            body += b'\0' * (-len(body) % self.align)
            moved[span] = (len(body), len(new[span]))
            body += new[span]
        body += self.body[pos:]
        root = rson.parse(self.memfs)            # a copy: this Archive stays as read
        for a in rson.entries(root).values():
            a.vals = list(moved[tuple(a.vals)])
            if a.etype == 0x30 and max(a.vals) > 0xFFFF:
                a.etype = 0x20                   # widened, as patch.py does for scripts
        return rson.write(root), bytes(body)


# --- commands ----------------------------------------------------------------

def same_png(path, img):
    """True when the PNG at path holds exactly img's pixels."""
    Image = need_pil()
    try:
        with Image.open(path) as old:
            return old.size == img.size and old.convert('RGBA').tobytes() == img.tobytes()
    except Exception:
        return False


def save_originals(arc, files, changed):
    """The game's own pixels of each changed image, under one temporary folder
    with the same relative paths, so the app can put each beside the user's
    file when it asks keep or replace. The folder is emptied on every run."""
    folder = os.path.join(tempfile.gettempdir(), 'otome-translator', 'sprite-goc', safe(arc.name))
    shutil.rmtree(folder, ignore_errors=True)
    for rel, data in files:
        if rel in changed and not isinstance(data, bytes):
            dst = os.path.join(folder, *rel.split('/'))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            data.save(dst)
    return folder


def cmd_export(arc, out=None, overwrite=False, keep=()):
    """List every texture and its cells; with out, also save them as PNG and
    cells_<screen>.csv (named per screen, so screens can share a folder).

    Files already in out may be cells someone redrew, so without overwrite
    nothing is written: the run lists them, names the ones that differ from
    the game, and says to add --overwrite (the app turns that into a question).
    With overwrite, each file that differs is first copied beside itself
    (backup_name: <name>.bak, .bak2 ...); identical ones are just rewritten.
    keep names files (as listed, e.g. mat_ttl/mat_ttl_btn.png) to leave as
    they are: the ones the user chose to keep, one by one, in the app."""
    rows, files = [], []          # files: (path in out, image or bytes)
    for p, t in sorted(arc.textures.items()):
        mine = [c for c in arc.cells if c.texture == p]
        if t.editable:
            print('%s.png  %dx%d, %d o' % (safe(stem(p)), t.w, t.h, len(mine)))
        else:
            print('%s  %dx%d, %d o - bo qua: %s' % (p.lstrip('/'), t.w, t.h, len(mine), t.why_not()))
        img = t.image() if out and t.editable else None
        if img is not None:
            files.append((safe(stem(p)) + '.png', img))
        for c in mine:
            name = c.file if t.editable else '(khong luu duoc)'
            print('    %-48s %5d %5d %5dx%-5d %s' % (name, c.x, c.y, c.w, c.h, ' '.join(c.parts)))
            if not t.editable:
                continue
            rows.append([c.file, stem(p), c.x, c.y, c.w, c.h, ' '.join(c.parts)])
            if img is not None:
                files.append((c.file, img.crop(c.box)))
    for n in arc.notes:
        print('chu y: ' + n)
    if not out:
        print('%d o sua duoc. Chua chon thu muc nen chi liet ke; chon thu muc de luu anh ra.' % len(rows))
        return 0
    table = io.StringIO()
    w = csv.writer(table, lineterminator='\r\n')
    w.writerow(['file', 'texture', 'x', 'y', 'w', 'h', 'parts'])
    w.writerows(rows)
    files.append(('cells_%s.csv' % safe(arc.name), table.getvalue().encode('utf-8-sig')))

    def path_of(rel):
        return os.path.join(out, *rel.split('/'))

    def same(rel, data):
        if isinstance(data, bytes):
            with open(path_of(rel), 'rb') as f:
                return f.read() == data
        return same_png(path_of(rel), data)
    have = [(rel, data) for rel, data in files if os.path.isfile(path_of(rel))]
    changed = [rel for rel, data in have if not same(rel, data)]
    if have and not overwrite:
        print('')
        print('%s da co %d file lay ra truoc do; %d file khac ban goc cua game (co the la o da ve lai).'
              % (out, len(have), len(changed)))
        if changed:
            pairs = ['%s -> %s' % (rel, os.path.basename(backup_name(path_of(rel)))) for rel in changed]
            print('se thay file da co, ban cu chep sang file .bak cung thu muc: %s' % ', '.join(pairs))
            print('anh goc de so sanh -> %s' % save_originals(arc, have, changed))
        print('chua ghi gi - them --overwrite de ghi de vao %s' % out)
        return 0
    keep = set(k.replace('\\', '/').strip() for k in keep)
    for rel, data in files:
        dst = path_of(rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if rel in changed and rel in keep:
            print('giu nguyen %s' % rel)
            continue
        if rel in changed:
            bak = backup_name(dst)
            shutil.copy2(dst, bak)
            print('ban cu -> %s' % bak)
        if isinstance(data, bytes):
            with open(dst, 'wb') as f:
                f.write(data)
        else:
            data.save(dst)
    print('da luu %d o -> %s (cells_%s.csv ghi vi tri tung o)' % (len(rows), out, safe(arc.name)))
    return 0


def load_png(path, size=None):
    Image = need_pil()
    img = Image.open(path)
    img.load()
    if size and img.size != size:
        raise ValueError('%s la %dx%d, phai dung %dx%d' % ((path,) + img.size + size))
    return img.convert('RGBA')


def free_spots(img, taken, sizes, gap=CELL_GAP):
    """Top-left corners for rectangles of sizes ([(w, h)]) in img, each at
    least gap pixels from the rectangles in taken, from one another and from
    every pixel that is not fully transparent; None for one that does not
    fit. Searched top to bottom, left to right on blocks of g pixels (a power
    of two that keeps the atlas within 512 blocks): a block holding any such
    pixel counts as used, so a 4096 atlas places a cell in well under a second."""
    W, H = img.size
    g = 1
    while max(W, H) > 512 * g:
        g *= 2
    m = -(-gap // g)                                   # blocks kept free round a cell
    used = img.getchannel('A').point(lambda v: 255 if v else 0)
    k = 1
    while k < g:
        used = used.reduce(2).point(lambda v: 255 if v else 0)
        k *= 2
    GW, GH = used.size
    px = used.tobytes()
    occ = [bytearray(1 if v else 0 for v in px[r * GW:(r + 1) * GW]) for r in range(GH)]

    def mark(x, y, w, h):
        for by in range(y // g, min(GH, (y + h - 1) // g + 1)):
            for bx in range(x // g, min(GW, (x + w - 1) // g + 1)):
                occ[by][bx] = 1

    def sums():
        s = [[0] * (GW + 1)]
        for row in occ:
            prev, acc, r = s[-1], 0, [0]
            for i, v in enumerate(row):
                acc += v
                r.append(prev[i + 1] + acc)
            s.append(r)
        return s

    for x, y, w, h in taken:
        mark(x, y, w, h)
    s, out = sums(), []
    for w, h in sizes:
        bw, bh, spot = -(-w // g), -(-h // g), None
        for by in range(GH - bh + 1):
            if by * g + h > H or spot:
                break
            y0, y1 = max(0, by - m), min(GH, by + bh + m)
            for bx in range(GW - bw + 1):
                if bx * g + w > W:
                    break
                x0, x1 = max(0, bx - m), min(GW, bx + bw + m)
                if s[y1][x1] - s[y0][x1] - s[y1][x0] + s[y0][x0] == 0:
                    spot = (bx * g, by * g)
                    break
        out.append(spot)
        if spot:
            mark(spot[0], spot[1], w, h)
            s = sums()
    return out


def drawn_by(arc):
    """{(texture path, x, y, w, h): {(ssdata path, state offset)}} for every
    state a frame draws, and {(ssdata path, offset): set of those keys}."""
    drawn, uses = {}, {}
    for sp, d in sorted(arc.files.items()):
        if not sp.endswith('.ssdata'):
            continue
        for off, tname, _ in states(d):
            key = (arc.by_stem.get(stem(tname)),) + struct.unpack_from('<4H', d, off + STATE_RECT)
            drawn.setdefault(key, set()).add((sp, off))
            uses.setdefault((sp, off), set()).add(key)
    return drawn, uses


def resize_cells(arc, p, img, resized, drawn, uses):
    """Put the cells of texture p whose PNG has another size (resized:
    [(cell, image)]) into empty space of img. Returns ({old key: new rect},
    report lines, problems); a cell with a problem is left out."""
    moves, report, problems = {}, [], []
    mine = [c for c in arc.cells if c.texture == p]
    ok = []
    for c, cell in resized:
        key = (p, c.x, c.y, c.w, c.h)
        where = drawn.get(key, set())
        odd = sorted(set(f for f in (struct.unpack_from('<I', arc.files[sp], off)[0] for sp, off in where)
                         if f & ~ROUND_CENTRE))
        shared = [k for sp_off in where for k in uses[sp_off] if k != key]
        if odd:
            problems.append('%s la %dx%d, o game %dx%d: chi doi co duoc o ma phan hinh chi dich, xoay, phong, '
                            'mo quanh tam; trang thai cua %s con co %s (chua biet la gi) - ve dung %dx%d'
                            % ((c.file,) + cell.size + (c.w, c.h, ' '.join(c.parts), ' '.join('%#x' % f for f in odd),
                                                       c.w, c.h)))
        elif shared:
            problems.append('%s: co trang thai ve ca o khac (%s %d,%d %dx%d), khong doi co duoc - ve dung %dx%d'
                            % ((c.file, stem(shared[0][0] or '?')) + shared[0][1:] + (c.w, c.h)))
        else:
            ok.append((c, cell))
    ok.sort(key=lambda ci: (-ci[1].size[1], -ci[1].size[0], ci[0].file))      # tall ones first pack better
    spots = free_spots(img, [(c.x, c.y, c.w, c.h) for c in mine], [cell.size for _, cell in ok])
    for (c, cell), spot in zip(ok, spots):
        w, h = cell.size
        if spot is None:
            problems.append('%s la %dx%d, o game %dx%d: %s khong con cho trong %dx%d (cach moi thu %d diem anh) '
                            '- ve nho lai hoac ve dung %dx%d' % (c.file, w, h, c.w, c.h, safe(stem(p)) + '.png',
                                                                 w, h, CELL_GAP, c.w, c.h))
            continue
        img.paste(cell, spot)
        moves[(p, c.x, c.y, c.w, c.h)] = spot + (w, h)
        report.append('%s: %dx%d thay cho %dx%d - dat vao cho trong (%d,%d), %d trang thai tro sang o moi, '
                      've quanh tam nhu cu' % ((c.file, w, h, c.w, c.h) + spot + (len(drawn.get((p, c.x, c.y, c.w, c.h), ())),)))
        hit = [o.file for o in mine if c.overlaps(o)]
        if hit:
            report.append('  chu y: o cu cua %s giu nguyen diem anh, %s van ve tu do' % (c.file, ', '.join(hit)))
    return moves, report, problems


def plan_import(arc, folder):
    """({texture path: new image, .ssdata path: new bytes}, report lines, problems)."""
    report, problems, new = [], [], {}
    moves, drawn = {}, None
    known = set()
    for p, t in sorted(arc.textures.items()):
        whole = safe(stem(p)) + '.png'
        known.add(whole)
        mine = [c for c in arc.cells if c.texture == p]
        known.update(c.file for c in mine)
        if not t.editable:
            continue
        orig = t.image()
        img = None
        path = os.path.join(folder, whole)
        if os.path.exists(path):
            try:
                full = load_png(path, (t.w, t.h))
            except ValueError as e:
                problems.append(str(e)); continue
            if full.tobytes() != orig.tobytes():
                img = full
                report.append('%s: thay ca anh' % whole)
        changed, resized = [], []
        for c in mine:
            path = os.path.join(folder, *c.file.split('/'))
            if not os.path.exists(path):
                continue
            cell = load_png(path)
            if cell.size != (c.w, c.h):
                resized.append((c, cell))
                continue
            if cell.tobytes() == orig.crop(c.box).tobytes():
                continue
            if img is None:
                img = orig.copy()
            img.paste(cell, (c.x, c.y))
            changed.append(c)
            report.append('%s: dan vao (%d,%d) %dx%d' % (c.file, c.x, c.y, c.w, c.h))
        for c in changed:
            hit = [o.file for o in mine if c.overlaps(o)]
            if hit:
                report.append('  chu y: %s de len o khac: %s' % (c.file, ', '.join(hit)))
        if resized:
            if drawn is None:
                drawn = drawn_by(arc)
            work = orig.copy() if img is None else img
            m, r, bad = resize_cells(arc, p, work, resized, *drawn)
            moves.update(m); report += r; problems += bad
            if m:
                img = work
        if img is not None:
            new[p] = img
    # Point every state that drew a moved cell at its new rectangle.
    ss = {}
    for key, rect in sorted(moves.items()):
        for sp, off in sorted(drawn[0][key]):
            struct.pack_into('<4H', ss.setdefault(sp, bytearray(arc.files[sp])), off + STATE_RECT, *rect)
    new.update((sp, bytes(d)) for sp, d in ss.items())
    # A stray PNG inside one of this screen's texture folders is most likely a
    # renamed cell; files of other screens sharing the folder are not ours.
    mine = tuple(safe(stem(p)) + '/' for p in arc.textures)
    for dirpath, _, names in os.walk(folder):
        for n in names:
            if n.lower().endswith('.png'):
                rel = os.path.relpath(os.path.join(dirpath, n), folder).replace(os.sep, '/')
                if rel not in known and rel.startswith(mine):
                    report.append('khong dung %s: khong co o nao ten nhu vay (doi ten file?)' % rel)
    return new, report, problems


def verify(arc, mem, body, new):
    """Problems found when the rebuilt pair is opened again."""
    out = []
    root = rson.parse(mem)
    if rson.write(root) != mem:
        out.append('memfs moi doc/ghi lai khong khop')
    ents = rson.entries(root)
    if set(ents) != set(arc.entries):
        out.append('memfs moi co danh sach file khac')
    for p, a in ents.items():
        d = body[a.vals[0]:a.vals[0] + a.vals[1]]
        if isinstance(new.get(p), bytes):                # a .ssdata pointed at moved cells
            if d != new[p]:
                out.append('%s: khac ban da sua' % p)
            elif not rects_only(arc.files[p], d):
                out.append('%s: doi ca ngoai o x/y/w/h cua trang thai' % p)
            for tname, x, y, w, h in cells(d):
                t = arc.textures.get(arc.by_stem.get(stem(tname)))
                if t and (x + w > t.w or y + h > t.h):
                    out.append('%s: o %d,%d %dx%d vuot ra ngoai %s' % (p, x, y, w, h, tname))
        elif p in new:
            t = Texture(d)
            if t.image().tobytes() != new[p].tobytes():
                out.append('%s: diem anh khac anh da dan' % p)
            if t.raw()[t.stride * t.h:] != arc.textures[p].raw()[t.stride * t.h:]:
                out.append('%s: phan dem cuoi anh bi doi' % p)
        elif d != arc.files[p]:
            out.append('%s: bi doi du khong sua' % p)
    return out


def cmd_import(arc, folder, out, apply):
    if folder_state(arc, folder) != 'taken':
        print('LOI: %s chua co anh lay ra tu %s.' % (folder, arc.name))
        print('Chay buoc lay anh ra (export) voi mot thu muc trong truoc, ve lai cac o ngay trong thu muc do,')
        print('roi chon chinh thu muc do o day.')
        return 1
    new, report, problems = plan_import(arc, folder)
    for line in report:
        print(line)
    if problems:
        print('LOI:'); [print('  ' + x) for x in problems]
        return 1
    if not new:
        print('chua co o nao duoc ve lai trong %s (moi anh van giong ban game) - khong co gi de ghi' % folder)
        return 0
    if not out:
        print('LOI: chua chon noi ghi (--out): thu muc romfs/spec_win/ssdata trong mod.')
        return 1
    replaced = dict((p, v if isinstance(v, bytes) else arc.textures[p].rebuild(v)) for p, v in new.items())
    mem, body = arc.build(replaced)
    bad = verify(arc, mem, body, new)
    if bad:
        print('KIEM TRA LOI:'); [print('  ' + x) for x in bad]
        return 1
    images = sum(1 for v in new.values() if not isinstance(v, bytes))
    print('%d anh doi; membody %d -> %d byte, memfs %d -> %d byte' % (
        images, len(arc.body), len(body), len(arc.memfs), len(mem)))
    print('kiem tra: OK (file khong sua giong tung byte, anh da sua dung tung diem anh%s)'
          % ('' if images == len(new) else ', .ssdata chi doi o x/y/w/h cua trang thai'))
    if not apply:
        say_replaced(out, (arc.name + '.memfs', arc.name + '.membody'))
        print('chay thu - them --apply de ghi vao %s' % out)
        return 0
    write_files(out, ((arc.name + '.memfs', mem), (arc.name + '.membody', body)))
    return 0


def folder_state(arc, folder):
    """'empty', 'taken' (holds images export took out of this screen) or 'other'."""
    if not os.path.isdir(folder):
        return 'empty'
    names = [n for n in os.listdir(folder) if not n.startswith('.')]
    if not names:
        return 'empty'
    # Only the texture names tell screens apart (an older export wrote cells.csv for any).
    ours = set(safe(stem(p)) for p in arc.textures)
    ours |= set(n + '.png' for n in ours)
    return 'taken' if any(n in ours for n in names) else 'other'


def cmd_translate(arc, folder, out, apply):
    """Both halves in one command, chosen by the folder: an empty one gets the
    images taken out, one holding them has the redrawn ones put back."""
    if not folder:
        return cmd_export(arc, None)
    state = folder_state(arc, folder)
    if state == 'other':
        print('LOI: %s co file nhung khong phai anh lay ra tu %s.' % (folder, arc.name))
        print('Chon mot thu muc trong de lay anh ra, hoac thu muc da lay anh %s ra truoc do.' % arc.name)
        return 1
    if state == 'empty':
        rc = cmd_export(arc, folder)
        print('')
        print('Buoc tiep theo: ve lai cac o can dich ngay trong %s, luu de len dung file do' % folder)
        print('(giu ten va dinh dang PNG; chu dai hon o thi ve anh to hon, cong cu tim cho trong cho no),')
        print('roi chay lai voi cung thu muc de dua anh vao game.')
        return rc
    return cmd_import(arc, folder, out, apply)


def cmd_check(arc):
    bad = []
    mem, body = arc.build({})
    if mem != arc.memfs or body != arc.body:
        bad.append('dung lai goi khong sua ma khong giong tung byte')
    n = 0
    for p, t in sorted(arc.textures.items()):
        if not t.editable:
            continue
        img = t.image()
        back = Texture(t.rebuild(img))
        if back.raw() != t.raw():
            bad.append('%s: nen lai roi giai nen khong ra dung du lieu' % p)
        n += 1
    print('%s: %d file, %d anh sua duoc / %d, %d o' % (arc.name, len(arc.files), n, len(arc.textures), len(arc.cells)))
    for x in arc.notes:
        print('chu y: ' + x)
    for x in bad:
        print('LOI: ' + x)
    if not bad:
        print('kiem tra: OK')
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('cmd', choices=['translate', 'list', 'export', 'import', 'check'])
    ap.add_argument('memfs', help='e.g. romfs/spec_win/ssdata/ttlm_nam.memfs')
    ap.add_argument('folder', nargs='?', help='translate: empty to take out, or the folder taken out to; '
                    'export: where to save (none: only list); import: the edited folder')
    ap.add_argument('--body', help='the .membody, if not next to the memfs')
    ap.add_argument('--out', help='translate, import: where the new memfs/membody go')
    ap.add_argument('--apply', action='store_true', help='translate, import: write the files')
    ap.add_argument('--overwrite', action='store_true',
                    help='export: replace images already in the folder (those that differ are copied to .bak first)')
    ap.add_argument('--keep', action='append', default=[],
                    help='export --overwrite: a file already there to leave as it is, e.g. mat_ttl/mat_ttl_btn.png (repeat)')
    a = ap.parse_args()
    if a.cmd == 'import' and not a.folder:
        ap.error('import: can thu muc anh')
    if a.cmd == 'import' and not a.out:
        ap.error('import: can --out')
    arc = Archive(a.memfs, a.body)
    if a.cmd == 'translate':
        return cmd_translate(arc, a.folder, a.out, a.apply)
    if a.cmd in ('list', 'export'):
        return cmd_export(arc, a.folder if a.cmd == 'export' else None, a.overwrite, a.keep)
    if a.cmd == 'import':
        return cmd_import(arc, a.folder, a.out, a.apply)
    return cmd_check(arc)


if __name__ == '__main__':
    sys.exit(main())
