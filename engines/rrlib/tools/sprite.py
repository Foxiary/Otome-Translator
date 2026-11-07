# -*- coding: utf-8 -*-
"""sprite.py - UI art painted into textures: the archives under romfs/spec_win/ssdata.

    python sprite.py export ttlm_nam.memfs           # list the cells only
    python sprite.py export ttlm_nam.memfs anh/      # list them and save them as PNG
    python sprite.py import ttlm_nam.memfs anh/ --out <mod>/romfs/spec_win/ssdata
    python sprite.py import ttlm_nam.memfs anh/ --out <mod>/romfs/spec_win/ssdata --apply
    python sprite.py check  ttlm_nam.memfs

The membody is read from next to the memfs unless --body names it.

Menu labels, buttons and help lines of the title menu, options, backlog and
other screens are pixels, not strings: there is nothing to translate in a
sheet. Each screen is a memfs/membody pair holding .rtex textures, one
SpriteStudio .ssdata and an .rson. The .ssdata says which rectangle of which
texture every sprite part draws, so a texture splits into named cells:
mat_ttlm_com01_off is the 新しく始める label, mat_ttlm_com01_setu its help line.

export   lists every texture and its cells - file name, place, size, parts.
         Given a folder it also writes every texture as <texture>.png and
         every cell as <texture>/<part>.png, plus cells.csv with the same
         list. (`list` is export without a folder, kept for old scripts.)
import   reads that folder back. A cell PNG that differs from the game's
         pixels is pasted at its rectangle; a <texture>.png that differs
         replaces the whole texture first, so an edited cell wins over it.
         A PNG must keep its size: nothing outside the rectangle is drawn.
         Without --apply it only reports. The result is opened again and
         checked: untouched files byte for byte, changed textures pixel for
         pixel. A file already in --out is kept as .bak.
check    rebuilds the archive unchanged (must match byte for byte) and
         round-trips every texture it can edit.

Only plain RGBA8 textures (format byte 0x02, not block-compressed) can be
written; every UI atlas of this game is one. BC-compressed backgrounds and
the 8/16/24-bit transition masks are listed and skipped.

Needs Pillow (pip install Pillow).
"""
import argparse
import csv
import os
import re
import struct
import sys
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rson  # noqa: E402
from patch import write_files  # noqa: E402

RTEX_HEAD = 0x20
FMT_RGBA8 = 0x02
BLOCK_COMPRESSED = 0x80000
STATE_SIZE = 40


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

def cells(data):
    """{(texture name, x, y, w, h): set of part names} drawn by a SpriteStudio .ssdata.

    'SSAD1.03' | u32 header size H | u32 16 | u32 pack offsets, 0-terminated
    part states, 40 bytes each from H: u32 ?, u16 part, u16 x, y, w, h (source
        rectangle in the part's texture, pixels), then position and the rest
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
    out = {}
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
        for f in range(nframes):
            lp, _, cnt = struct.unpack_from('<3I', data, frames_p + 12 * f)
            for si in struct.unpack_from('<%dH' % cnt, data, lp):
                part, x, y, w, h = struct.unpack_from('<5H', data, hsize + STATE_SIZE * si + 4)
                if not (w and h):
                    continue
                name_p, _, _, tex = parts[part]
                if tex >= len(texs):
                    raise ValueError('part %s uses texture %d of %d' % (cstr(name_p), tex, len(texs)))
                out.setdefault((texs[tex], x, y, w, h), set()).add(cstr(name_p))
    return out


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
            for c in cs:
                base = part if len(cs) == 1 else '%s_%d_%d' % (part, c.x, c.y)
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

def cmd_export(arc, out=None):
    """List every texture and its cells; with out, also save them as PNG and cells.csv."""
    if out:
        os.makedirs(out, exist_ok=True)
    rows = []
    for p, t in sorted(arc.textures.items()):
        mine = [c for c in arc.cells if c.texture == p]
        if t.editable:
            print('%s.png  %dx%d, %d o' % (safe(stem(p)), t.w, t.h, len(mine)))
        else:
            print('%s  %dx%d, %d o - bo qua: %s' % (p.lstrip('/'), t.w, t.h, len(mine), t.why_not()))
        img = t.image() if out and t.editable else None
        if img is not None:
            img.save(os.path.join(out, safe(stem(p)) + '.png'))
        for c in mine:
            name = c.file if t.editable else '(khong luu duoc)'
            print('    %-48s %5d %5d %5dx%-5d %s' % (name, c.x, c.y, c.w, c.h, ' '.join(c.parts)))
            if not t.editable:
                continue
            rows.append([c.file, stem(p), c.x, c.y, c.w, c.h, ' '.join(c.parts)])
            if img is not None:
                dst = os.path.join(out, *c.file.split('/'))
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                img.crop(c.box).save(dst)
    for n in arc.notes:
        print('chu y: ' + n)
    if not out:
        print('%d o sua duoc. Chua chon thu muc nen chi liet ke; chon thu muc de luu anh ra.' % len(rows))
        return 0
    with open(os.path.join(out, 'cells.csv'), 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f)
        w.writerow(['file', 'texture', 'x', 'y', 'w', 'h', 'parts'])
        w.writerows(rows)
    print('da luu %d o -> %s (cells.csv ghi vi tri tung o)' % (len(rows), out))
    return 0


def load_png(path, size):
    Image = need_pil()
    img = Image.open(path)
    img.load()
    if img.size != size:
        raise ValueError('%s la %dx%d, phai dung %dx%d' % ((path,) + img.size + size))
    return img.convert('RGBA')


def plan_import(arc, folder):
    """({texture path: new image}, report lines, problems)."""
    report, problems, new = [], [], {}
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
        changed = []
        for c in mine:
            path = os.path.join(folder, *c.file.split('/'))
            if not os.path.exists(path):
                continue
            try:
                cell = load_png(path, (c.w, c.h))
            except ValueError as e:
                problems.append(str(e)); continue
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
        if img is not None:
            new[p] = img
    for dirpath, _, names in os.walk(folder):
        for n in names:
            if n.lower().endswith('.png'):
                rel = os.path.relpath(os.path.join(dirpath, n), folder).replace(os.sep, '/')
                if rel not in known:
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
        if p in new:
            t = Texture(d)
            if t.image().tobytes() != new[p].tobytes():
                out.append('%s: diem anh khac anh da dan' % p)
            if t.raw()[t.stride * t.h:] != arc.textures[p].raw()[t.stride * t.h:]:
                out.append('%s: phan dem cuoi anh bi doi' % p)
        elif d != arc.files[p]:
            out.append('%s: bi doi du khong sua' % p)
    return out


def cmd_import(arc, folder, out, apply):
    new, report, problems = plan_import(arc, folder)
    for line in report:
        print(line)
    if problems:
        print('LOI:'); [print('  ' + x) for x in problems]
        return 1
    if not new:
        print('khong co anh nao khac ban game - khong co gi de ghi')
        return 0
    replaced = dict((p, arc.textures[p].rebuild(img)) for p, img in new.items())
    mem, body = arc.build(replaced)
    bad = verify(arc, mem, body, new)
    if bad:
        print('KIEM TRA LOI:'); [print('  ' + x) for x in bad]
        return 1
    print('%d anh doi; membody %d -> %d byte, memfs %d -> %d byte' % (
        len(new), len(arc.body), len(body), len(arc.memfs), len(mem)))
    print('kiem tra: OK (file khong sua giong tung byte, anh da sua dung tung diem anh)')
    if not apply:
        print('chay thu - them --apply de ghi vao %s' % out)
        return 0
    write_files(out, ((arc.name + '.memfs', mem), (arc.name + '.membody', body)))
    return 0


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
    ap.add_argument('cmd', choices=['list', 'export', 'import', 'check'])
    ap.add_argument('memfs', help='e.g. romfs/spec_win/ssdata/ttlm_nam.memfs')
    ap.add_argument('folder', nargs='?', help='export: where to save (none: only list); import: the edited folder')
    ap.add_argument('--body', help='the .membody, if not next to the memfs')
    ap.add_argument('--out', help='import: where the new memfs/membody go')
    ap.add_argument('--apply', action='store_true', help='import: write the files')
    a = ap.parse_args()
    if a.cmd == 'import' and not a.folder:
        ap.error('import: can thu muc anh')
    if a.cmd == 'import' and not a.out:
        ap.error('import: can --out')
    arc = Archive(a.memfs, a.body)
    if a.cmd in ('list', 'export'):
        return cmd_export(arc, a.folder if a.cmd == 'export' else None)
    if a.cmd == 'import':
        return cmd_import(arc, a.folder, a.out, a.apply)
    return cmd_check(arc)


if __name__ == '__main__':
    sys.exit(main())
