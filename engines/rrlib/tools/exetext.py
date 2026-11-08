# -*- coding: utf-8 -*-
"""exetext.py - translate the text built into the game's program (exefs/main).

    python exetext.py export <mod>/exefs/main chu_exe.csv
    # ... fill the vi_text column of chu_exe.csv ...
    python exetext.py import <mod>/exefs/main chu_exe.csv --map font.json --out <mod>/exefs           # dry run
    python exetext.py import <mod>/exefs/main chu_exe.csv --map font.json --out <mod>/exefs --apply   # write
    python exetext.py check  <mod>/exefs/main

Dialog prompts (前回と同じ名前を使用します｡ + \\nよろしいですか？), quick save
and load messages, the settings screen's questions, button help ({B} 戻る),
glossary entries and chapter titles are not in script.membody: about 780
strings sit in main as UTF-32LE, NUL-terminated (found only once the NSO's
LZ4 segments are unpacked). The 02/10 patch never translated them, and its
font puts Vietnamese letters on kana codes, so they show as garbled
Japanese (と -> Ề, を -> ặ, よ -> Ở).

export   lists every Japanese string the program points at: columns address,
         refs, jp_text, vi_text, note (.csv; .xlsx too when openpyxl is
         installed). Run on a main this tool already wrote, it lists the same
         Japanese strings, and with --map fills vi_text with what is in it.
import   writes the vi_text column in. Vietnamese is longer than Japanese,
         so no string is rewritten in place: each translation goes to a new
         area after the program's data, and what pointed at the Japanese
         string points at it instead:
           - pointers (R_AARCH64_RELATIVE relocations): their addend
           - code (ADRP + ADD, or ADR): the ADD (or ADR) becomes an ADRP to
             the translation, which therefore starts on a 4 KiB page
         The Japanese bytes stay where they are, so strings sharing a tail
         (the linker merges those) and anything not found keep working.
         The new area is the old .bss, turned into zero-filled .data (the
         loader zeroes .bss anyway), then the translations. At its start a
         table keeps every value changed, so import first undoes an earlier
         run of itself: always give it your mod's main, translated or not.
         Text is encoded for the mod's font with the map that
         applysheet.py --map saves; rows are checked as applysheet checks
         sheet cells, plus %d/%ls must match JP (printf would crash).
check    lists what is found, then moves every string to the new area
         unchanged, checks that each pointer reads the same string there and
         that undoing it gives the program back byte for byte.

A pointer the code builds some other way is not found: that place keeps
showing Japanese. Try each screen in the game.

The NSO is written with its segments uncompressed (the loader takes both)
and their hashes recomputed. The read redirects of the 02/10 patch's main
(exehook.py) are kept as they are.
"""
import argparse
import csv
import hashlib
import json
import os
import re
import struct
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from exehook import lz4_block, redirects          # noqa: E402
from patch import say_replaced, write_files        # noqa: E402

PAGE = 0x1000
HEAD = 0x100                  # NSO header; the module name follows it
MAGIC = b'RRLBTEXT'
VERSION = 1
R_AARCH64_RELATIVE = 1027
WINDOW = 32                   # instructions an ADRP's ADD is looked for in
COLUMNS = ('address', 'refs', 'jp_text', 'vi_text', 'note')

# Kept as applysheet.py does it for sheet cells: the VI builder dropped these
# and the font is not known to have them.
DROP = dict.fromkeys(map(ord, '「」『』“”​'), None)
SUBST = (('"', "'"), ('　', ' '))
JAPANESE = re.compile('[぀-ヿ㐀-䶿一-鿿]')
SOUNDS = set('っッ')
PRINTF = re.compile(r'%[-+ #0]*(?:\d+|\*)?(?:\.(?:\d+|\*))?(?:hh|h|ll|l|z|j|t|L)?[diouxXeEfgGcspn%]')
BUTTON = re.compile(r'\{[A-Za-z+\-]{1,3}\}')


def u32(b, o):
    return struct.unpack_from('<I', b, o)[0]


def align(n, a=PAGE):
    return (n + a - 1) & ~(a - 1)


def _imm21(w):
    v = ((w >> 29) & 3) | (((w >> 5) & 0x7ffff) << 2)
    return v - (1 << 21) if v & (1 << 20) else v


def adrp(pc, target, rd):
    """ADRP X<rd>, page of target - placed at pc."""
    imm = (target >> 12) - (pc >> 12)
    if not -(1 << 20) <= imm < (1 << 20):
        raise ValueError('ADRP out of range at 0x%x' % pc)
    imm &= (1 << 21) - 1
    return 0x90000000 | ((imm & 3) << 29) | ((imm >> 2) << 5) | rd


def adrp_target(w, pc):
    """The page an ADRP at pc loads, or None if w is no ADRP."""
    if w & 0x9f000000 != 0x90000000:
        return None
    return (pc & ~0xfff) + (_imm21(w) << 12)


# ---------------------------------------------------------------- NSO

class Nso(object):
    """An NSO's three segments, unpacked."""

    def __init__(self, raw):
        if raw[:4] != b'NSO0':
            raise ValueError('khong phai file chuong trinh NSO (exefs/main)')
        self.header = bytes(raw[:HEAD])
        flags = u32(raw, 0x0C)
        self.segs = []
        for k in range(3):
            foff, moff, size = struct.unpack_from('<3I', raw, 0x10 + 0x10 * k)
            packed = u32(raw, 0x60 + 4 * k)
            data = raw[foff:foff + packed]
            if flags & (1 << k):
                data = lz4_block(data, size)
            if len(data) != size:
                raise ValueError('segment %d: %d byte, header says %d' % (k, len(data), size))
            self.segs.append((moff, bytes(data)))
        self.bss = u32(raw, 0x3C)
        name_off, name_size = u32(raw, 0x1C), u32(raw, 0x2C)
        self.name = bytes(raw[name_off:name_off + name_size]) if name_off >= HEAD else b''

    def image(self):
        moff, data = self.segs[2]
        img = bytearray(moff + len(data) + self.bss)
        for moff, data in self.segs:
            img[moff:moff + len(data)] = data
        return img

    def write(self, img, data_size, bss):
        """A new NSO from a memory image: text and rodata as they are laid out
        now, data grown or shrunk to data_size. Segments uncompressed, hashes
        recomputed; the hash-check flags are kept."""
        segs = []
        for k, (moff, data) in enumerate(self.segs):
            size = data_size if k == 2 else len(data)
            segs.append((moff, bytes(img[moff:moff + size])))
        h = bytearray(self.header)
        struct.pack_into('<I', h, 0x0C, u32(h, 0x0C) & ~7)
        struct.pack_into('<I', h, 0x1C, HEAD)
        struct.pack_into('<I', h, 0x2C, len(self.name))
        pos = HEAD + len(self.name)
        for k, (moff, data) in enumerate(segs):
            struct.pack_into('<3I', h, 0x10 + 0x10 * k, pos, moff, len(data))
            struct.pack_into('<I', h, 0x60 + 4 * k, len(data))
            h[0xA0 + 0x20 * k:0xC0 + 0x20 * k] = hashlib.sha256(data).digest()
            pos += len(data)
        struct.pack_into('<I', h, 0x3C, bss)
        return bytes(h) + self.name + b''.join(d for _, d in segs)


# ---------------------------------------------------------------- references

def _ends(x, rd):
    """May instruction x leave X<rd> holding something else, or leave this path?"""
    if x & 0xfc000000 == 0x14000000 or x & 0xfffffc1f in (0xd61f0000, 0xd65f0000):
        return True                                   # B, BR, RET
    if x & 0xfc000000 == 0x94000000 or x & 0xfffffc1f == 0xd63f0000:
        return rd <= 18                               # BL, BLR: x0-x18 are the callee's
    if x & 31 != rd:
        return False
    if x & 0x3b000000 in (0x38000000, 0x39000000):     # LDR/STR: a store only reads it
        return (x >> 22) & 3 != 0
    if x & 0x3a000000 == 0x28000000:                  # LDP/STP
        return (x >> 22) & 1 == 1
    if x & 0x7e000000 in (0x34000000, 0x36000000):    # CBZ/CBNZ, TBZ/TBNZ read it
        return False
    if x & 0xff000010 == 0x54000000:                  # B.cond: those bits are the condition
        return False
    return True


def code_refs(img, text_size, lo, hi):
    """{target: [(kind, pc)]} for addresses in [lo, hi) the code builds with
    ADRP + ADD (kind 'add', pc of the ADD) or ADR ('adr')."""
    n = text_size // 4
    w = struct.unpack_from('<%dI' % n, img, 0)
    out = {}
    for i in range(n):
        v = w[i]
        page = adrp_target(v, 4 * i)
        if page is not None and v & 31 != 31:
            rd = v & 31
            for j in range(i + 1, min(n, i + WINDOW)):
                x = w[j]
                if x & 0xffc00000 == 0x91000000 and (x >> 5) & 31 == rd:    # ADD Xd, X<rd>, #imm12
                    t = page + ((x >> 10) & 0xfff)
                    if lo <= t < hi and x & 31 != 31:                       # not ADD SP, ...
                        out.setdefault(t, []).append(('add', 4 * j))
                    if x & 31 == rd:
                        break
                    continue
                if _ends(x, rd):
                    break
        elif v & 0x9f000000 == 0x10000000 and v & 31 != 31:
            t = 4 * i + _imm21(v)
            if lo <= t < hi:
                out.setdefault(t, []).append(('adr', 4 * i))
    return out


def dynamic(img):
    """{tag: value} of the module's .dynamic, found through MOD0."""
    mod0 = u32(img, 4)
    if img[mod0:mod0 + 4] != b'MOD0':
        return {}
    p = mod0 + struct.unpack_from('<i', img, mod0 + 4)[0]
    tags = {}
    while p + 16 <= len(img):
        tag, val = struct.unpack_from('<qQ', img, p)
        p += 16
        if tag == 0:
            break
        tags.setdefault(tag, val)
    return tags


def rela_refs(img, lo, hi):
    """{target: [('rela', address of the Elf64_Rela)]} for RELATIVE relocations into [lo, hi)."""
    tags = dynamic(img)
    out = {}
    if 7 not in tags:
        return out
    rela, size, ent = tags[7], tags.get(8, 0), tags.get(9, 24) or 24
    for q in range(rela, rela + size, ent):
        _off, info, add = struct.unpack_from('<QQq', img, q)
        if info & 0xffffffff == R_AARCH64_RELATIVE and lo <= add < hi:
            out.setdefault(add, []).append(('rela', q))
    return out


def text_char(c):
    return c in (9, 10, 13) or 0x20 <= c <= 0x7e or 0xa0 <= c <= 0xd7ff or 0xe000 <= c <= 0xfffd


def is_japanese(s):
    return any(0x3000 <= ord(c) <= 0x30ff or 0x3400 <= ord(c) <= 0x9fff or 0xff00 <= ord(c) <= 0xffef for c in s)


def read_text(img, a, hi=None):
    """The UTF-32LE string at a, or None if it is no text up to a NUL."""
    hi = len(img) if hi is None else hi
    out = []
    while a + 4 <= hi:
        c = u32(img, a)
        if c == 0:
            return ''.join(out)
        if not text_char(c):
            return None
        out.append(chr(c))
        a += 4
    return None


def resolve(img, kind, at):
    """Where a reference points now."""
    if kind == 'rela':
        return struct.unpack_from('<q', img, at + 16)[0]
    w = u32(img, at)
    page = adrp_target(w, at)
    if page is not None:
        return page
    if kind == 'adr':
        return at + _imm21(w)
    raise ValueError('0x%x: not an ADRP any more' % at)


# ---------------------------------------------------------------- the program

class Exe(object):
    """exefs/main with its Japanese strings and what points at them. A main
    this tool wrote is undone first: img is always the program before any
    translation, and current says where each translated string went."""

    def __init__(self, raw):
        self.nso = Nso(raw)
        img = self.nso.image()
        (self.text_moff, text), (self.ro_moff, ro), (self.data_moff, data) = self.nso.segs
        self.text_size, self.ro_size, self.data_size, self.bss = len(text), len(ro), len(data), self.nso.bss
        self.current = {}
        self.written = None
        end = self.data_moff + self.data_size
        if end >= 16 and img[end - 16:end - 8] == MAGIC:
            self._undo(img, u32(img, end - 8))
        self.img = img
        lo, hi = self.ro_moff, self.data_moff + self.data_size
        refs = code_refs(img, self.text_size, lo, hi)
        # a site attributed to two targets is not trusted for either
        sites = {}
        for t, rs in refs.items():
            for r in rs:
                sites.setdefault(r, set()).add(t)
        self.ambiguous = sorted(r for r, ts in sites.items() if len(ts) > 1)
        bad = set(self.ambiguous)
        for t, rs in rela_refs(img, lo, hi).items():
            refs.setdefault(t, []).extend(rs)
        self.refs, self.strings = {}, {}
        # String literals live in .rodata. Text-looking bytes in .data are a
        # struct: the glossary table (0x5557d0) starts with the u32 'あ', a 0,
        # then pointers - moving it as a string crashes the game on wcslen(NULL).
        ro_end = self.ro_moff + self.ro_size
        for t in sorted(refs):
            rs = [r for r in refs[t] if r not in bad]
            s = read_text(img, t, ro_end) if t % 4 == 0 and t < ro_end else None
            if rs and s and is_japanese(s):
                self.refs[t], self.strings[t] = rs, s

    def _undo(self, img, head):
        if img[head:head + 8] != MAGIC or u32(img, head + 8) != VERSION:
            raise ValueError('bang hoan tac cua exetext hong o 0x%x' % head)
        npatch, data_size, bss, nstr = struct.unpack_from('<4I', img, head + 12)
        p = head + 32
        for _ in range(npatch):
            kind, _r, off, old = struct.unpack_from('<IIQQ', img, p)
            p += 24
            if kind == 1:
                struct.pack_into('<I', img, off, old)
            elif kind in (2, 3):
                struct.pack_into('<Q', img, off, old)
            else:
                raise ValueError('bang hoan tac: loai %d la' % kind)
        for _ in range(nstr):
            old, new = struct.unpack_from('<QQ', img, p)
            p += 16
            self.current[old] = new
        self.written = bytes(img[self.data_moff + data_size:])       # the area, for export --map
        self.written_base = self.data_moff + data_size
        del img[self.data_moff + data_size:]
        img.extend(bytes(bss))
        self.data_size, self.bss = data_size, bss

    def current_text(self, a):
        """The translation now in the program for the string at a, or None."""
        if a not in self.current or self.written is None:
            return None
        return read_text(self.written, self.current[a] - self.written_base)

    def unreferenced(self):
        """Japanese UTF-32 strings in rodata that nothing found points at."""
        lo, hi = self.ro_moff, self.ro_moff + self.ro_size
        vals = struct.unpack_from('<%dI' % ((hi - lo) // 4), self.img, lo)
        out, i = [], 0
        while i < len(vals):
            if vals[i] and text_char(vals[i]) and (i == 0 or vals[i - 1] == 0):
                j = i
                while j < len(vals) and vals[j] and text_char(vals[j]):
                    j += 1
                if j < len(vals) and vals[j] == 0:
                    s = ''.join(map(chr, vals[i:j]))
                    a = lo + 4 * i
                    inside = any(a <= t < lo + 4 * j for t in range(a, lo + 4 * j, 4) if t in self.strings)
                    if is_japanese(s) and not inside:
                        out.append((a, s))
                i = j
            i += 1
        return out


def build(exe, writes):
    """writes: {address of a Japanese string: text, already in the font's
    codes} -> (new main, {address: where its translation went})."""
    img = bytearray(exe.img)
    start = align(exe.data_moff + exe.data_size + exe.bss)
    code = sorted(a for a in writes if any(k != 'rela' for k, _ in exe.refs[a]))
    plain = sorted(a for a in writes if a not in code)
    npatch = sum(2 * len(exe.refs[a]) for a in writes)        # room for a qword beside each addend
    head = 32 + 24 * npatch + 16 * len(writes)
    size = lambda a: 4 * (len(writes[a]) + 1)
    where, gaps = {}, []
    page = align(start + head)
    gaps.append([align(start + head, 8), page])
    for a in code:                       # an ADRP reaches only the start of a page
        where[a] = page
        end = page + size(a)
        page = align(end)
        gaps.append([align(end, 8), page])
    tail = page
    for a in plain:
        for g in gaps:
            if g[1] - g[0] >= size(a):
                where[a] = g[0]
                g[0] = align(g[0] + size(a), 8)
                break
        else:
            where[a] = tail
            tail = align(tail + size(a), 8)
    end = align(max(tail, page) + 16)
    img.extend(bytes(end - len(img)))
    for a, t in writes.items():
        enc = ''.join(t).encode('utf-32le') + b'\0\0\0\0'
        img[where[a]:where[a] + len(enc)] = enc
    patches, done = [], {}
    for a in sorted(writes):
        new = where[a]
        for kind, at in exe.refs[a]:
            if (kind, at) in done:
                raise ValueError('0x%x duoc tro boi ca 0x%x lan 0x%x' % (at, done[(kind, at)], a))
            done[(kind, at)] = a
            if kind == 'rela':
                old = struct.unpack_from('<Q', img, at + 16)[0]
                patches.append((2, at + 16, old))
                struct.pack_into('<q', img, at + 16, new)
                off = struct.unpack_from('<Q', img, at)[0]
                if off + 8 <= exe.data_moff + exe.data_size and struct.unpack_from('<Q', img, off)[0] == a:
                    patches.append((3, off, a))
                    struct.pack_into('<Q', img, off, new)
            else:
                old = u32(img, at)
                patches.append((1, at, old))
                struct.pack_into('<I', img, at, adrp(at, new, old & 31))
    struct.pack_into('<8s5I', img, start, MAGIC, VERSION, len(patches), exe.data_size, exe.bss, len(writes))
    p = start + 32
    for kind, off, old in patches:
        struct.pack_into('<IIQQ', img, p, kind, 0, off, old)
        p += 24
    for a in sorted(writes):
        struct.pack_into('<QQ', img, p, a, where[a])
        p += 16
    struct.pack_into('<8sII', img, end - 16, MAGIC, start, 0)
    return exe.nso.write(img, end - exe.data_moff, 0), where


def verify(raw, exe, writes, where):
    """Open what build wrote and check it. -> list of problems."""
    out = []
    new = Exe(raw)
    if (new.text_size, new.ro_size, new.data_size, new.bss) != (exe.text_size, exe.ro_size, exe.data_size, exe.bss) \
            or new.img != exe.img:
        out.append('hoan tac khong ra dung chuong trinh goc')
    if new.current != where:
        out.append('bang hoan tac ghi sai cho cua %d chuoi' % len(set(new.current.items()) ^ set(where.items())))
    img = Nso(raw).image()
    for a, t in sorted(writes.items()):
        for kind, at in exe.refs[a]:
            try:
                got = resolve(img, kind, at)
            except ValueError as e:
                got = str(e)
            if got != where[a]:
                out.append('0x%x: %s 0x%x tro toi %s, phai la 0x%x' % (a, kind, at, got, where[a]))
        if read_text(img, where[a]) != t:
            out.append('0x%x: ban dich doc lai khong dung' % a)
    if redirects(img[:exe.text_size]) != redirects(exe.img[:exe.text_size]):
        out.append('doan chuyen huong cua ban patch bi thay doi')
    return out


# ---------------------------------------------------------------- sheet

def notes(s):
    """What a translator has to keep, in Vietnamese."""
    out = []
    p = PRINTF.findall(s)
    if p:
        out.append('giữ nguyên %s theo đúng thứ tự (thiếu hay thừa là game có thể lỗi)' % ' '.join(p))
    b = BUTTON.findall(s)
    if b:
        out.append('giữ %s: ký hiệu nút' % ' '.join(b))
    if '#R(' in s:
        out.append('#R(cách đọc,chữ) là chữ nhỏ trên đầu, bỏ được')
    if '￥ｎ' in s:
        out.append('￥ｎ là xuống dòng')
    if s.startswith('\n') or s.endswith('\n'):
        out.append('câu bắt đầu hoặc kết thúc bằng xuống dòng: công cụ tự giữ')
    return '; '.join(out)


def ref_text(refs):
    n = sum(1 for k, _ in refs if k == 'rela')
    c = len(refs) - n
    return ', '.join(x for x in ('con trỏ %d' % n if n else '', 'code %d' % c if c else '') if x)


def write_rows(path, header, rows):
    if path.lower().endswith('.xlsx'):
        try:
            import openpyxl
        except ImportError:
            raise SystemExit('can openpyxl de ghi .xlsx (pip install openpyxl) - hoac luu thanh .csv')
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = 'exe'
        ws.append(list(header))
        for r in rows:
            ws.append(list(r))
        ws.freeze_panes = 'A2'
        for col, width in zip('ABCDE', (12, 16, 50, 50, 50)):
            ws.column_dimensions[col].width = width
        wb.save(path)
        return
    with open(path, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def read_rows(path):
    """[{row, address, jp, vi}] from a .csv or .xlsx with the export's columns."""
    if path.lower().endswith('.xlsx'):
        try:
            import openpyxl
        except ImportError:
            raise SystemExit('can openpyxl de doc .xlsx (pip install openpyxl) - hoac tai bang ve dang .csv')
        ws = openpyxl.load_workbook(path, read_only=True, data_only=True).worksheets[0]
        table = [['' if v is None else str(v) for v in r] for r in ws.iter_rows(values_only=True)]
    else:
        with open(path, encoding='utf-8-sig', newline='') as f:
            table = list(csv.reader(f))
    if not table:
        raise SystemExit('%s: bang trong' % path)
    hdr = [h.strip().lower() for h in table[0]]
    for need in ('address', 'jp_text', 'vi_text'):
        if need not in hdr:
            raise SystemExit('%s: thieu cot %s (can cac cot cua lenh export)' % (path, need))
    ix = dict((h, i) for i, h in enumerate(hdr))
    out = []
    for n, r in enumerate(table[1:], start=2):
        g = lambda k: r[ix[k]] if ix[k] < len(r) else ''
        a = g('address').strip()
        if not a:
            continue
        try:
            addr = int(a[2:] if a.lower().startswith('0x') else a, 16)
        except ValueError:
            raise SystemExit('%s dong %d: dia chi "%s" khong doc duoc' % (path, n, a))
        out.append(dict(row=n, address=addr, jp=g('jp_text'), vi=g('vi_text')))
    return out


def load_map(path):
    with open(path, encoding='utf-8') as f:
        fmap = json.load(f)
    if not isinstance(fmap, dict) or not all(isinstance(k, str) and len(k) == 1 for k in fmap):
        raise SystemExit('%s: khong phai bang ma font cua applysheet.py --map' % path)
    return fmap


def vietnamese_letter(ch):
    """A letter the font has to carry on a borrowed code: Latin Extended-A/B
    and Extended Additional (ă đ ơ ư and every letter with two marks)."""
    return 0x100 <= ord(ch) <= 0x24f or 0x1e00 <= ord(ch) <= 0x1eff


# Letters past Latin-1 the mod's scripts write at their own code (ũ 4 242
# times, ĩ 1 719): the map only lists letters moved onto another code.
LITERAL = set('ĩũ')


def encode(text, fmap):
    """-> (text in the font's codes, letters the map has no code for).
    Latin-1 letters, ĩ and ũ keep their code, as in the patch; a capital the
    mod never used gets its small letter's code. Punctuation and symbols are
    kept: the font is the Japanese one with letters drawn over kana."""
    out, unknown = [], []
    for ch in text:
        low = ch.lower()
        if ch in fmap:
            out.append(fmap[ch])
        elif ch in LITERAL or not vietnamese_letter(ch):
            out.append(ch)
        elif low != ch and (low in fmap or low in LITERAL):
            out.append(fmap.get(low, low)); unknown.append(ch)
        else:
            out.append(ch); unknown.append(ch)
    return ''.join(out), unknown


def decode(text, fmap):
    back = {}
    for k, v in sorted(fmap.items(), key=lambda kv: kv[0] == kv[0].lower()):
        back[v] = k                       # the small letter wins where two share a code
    return ''.join(back.get(c, c) for c in text)


def prepare(vi, jp):
    """A cell as program text, before the font encoding."""
    t = unicodedata.normalize('NFC', vi).translate(DROP)
    for a, b in SUBST:
        t = t.replace(a, b)
    t = t.replace('\r\n', '\n').replace('\r', '\n')
    if '￥ｎ' in jp and '\n' not in jp:
        t = t.replace('\n', '￥ｎ')
    lead = len(jp) - len(jp.lstrip('\n'))
    trail = len(jp) - len(jp.rstrip('\n'))
    return '\n' * lead + t.strip('\n') + '\n' * trail


WHY = {'no-string': 'Exe không có chuỗi tiếng Nhật nào ở địa chỉ này',
       'jp-mismatch': 'jp_text khác chữ trong exe (bảng lấy từ một exe khác?)',
       'empty': 'Chưa dịch',
       'untranslated': 'vi_text vẫn là câu tiếng Nhật',
       'japanese': 'Còn sót chữ Nhật: font dùng các ô kana cho chữ Việt, sẽ hiện sai chữ',
       'format': 'Các mã %d, %ls... khác tiếng Nhật: game có thể lỗi',
       'duplicate': 'Địa chỉ này đã có một dòng khác',
       'buttons': 'Ký hiệu nút {..} khác tiếng Nhật',
       'font': 'Font chưa có chữ'}


def plan(rows, exe, fmap):
    """-> ({address: encoded text}, report rows)."""
    writes, report = {}, []
    for r in rows:
        a, jp = r['address'], exe.strings.get(r['address'])
        rep = dict(r=r, action='skip', why='', more='')
        report.append(rep)
        if jp is None:
            rep['why'] = 'no-string'; continue
        if r['jp'].replace('\r\n', '\n').strip() != jp.strip():     # sheets may trim a leading \n
            rep['why'] = 'jp-mismatch'; continue
        if not r['vi'].strip():
            rep['why'] = 'empty'; continue
        if a in writes:
            rep['why'] = 'duplicate'; continue
        text = prepare(r['vi'], jp)
        left = sorted(set(JAPANESE.findall(text)) - SOUNDS)
        if left and text == jp.translate(DROP):
            rep['why'] = 'untranslated'; continue
        if left:
            rep.update(why='japanese', more=''.join(left)); continue
        if PRINTF.findall(text) != PRINTF.findall(jp):
            rep.update(why='format', more=' '.join(PRINTF.findall(jp))); continue
        enc, unknown = encode(text, fmap)
        writes[a] = enc
        rep['action'] = 'write'
        warn = []
        if sorted(BUTTON.findall(text)) != sorted(BUTTON.findall(jp)):
            warn.append('buttons')
        if unknown:
            warn.append('font')
            rep['more'] = ''.join(sorted(set(unknown)))
        rep['why'] = ','.join(warn)
    return writes, report


def write_report(path, report):
    with open(path, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(['dong', 'address', 'viec', 'ly do', 'chu', 'jp_text', 'vi_text'])
        for x in report:
            why = '; '.join(WHY[k] for k in x['why'].split(',') if k)
            w.writerow([x['r']['row'], '0x%x' % x['r']['address'], 'ghi' if x['action'] == 'write' else 'bo qua',
                        why, x['more'], x['r']['jp'], x['r']['vi']])


# ---------------------------------------------------------------- commands

def open_exe(path):
    with open(path, 'rb') as f:
        return Exe(f.read())


def say_found(exe):
    kinds = {}
    for rs in exe.refs.values():
        for k, _ in rs:
            kinds[k] = kinds.get(k, 0) + 1
    print('exe: %d chuoi tieng Nhat co cho tro toi (%d con tro, %d lenh ADRP+ADD, %d ADR)%s' % (
        len(exe.strings), kinds.get('rela', 0), kinds.get('add', 0), kinds.get('adr', 0),
        '; da dich %d chuoi bang exetext' % len(exe.current) if exe.current else ''))
    hooks = redirects(exe.img[:exe.text_size])
    if hooks:
        print('doan chuyen huong doc kich ban cua ban patch: %d (giu nguyen)' % len(hooks))


def cmd_export(path, out, map_path):
    exe = open_exe(path)
    say_found(exe)
    fmap = load_map(map_path) if map_path else None
    rows, filled = [], 0
    for a, s in sorted(exe.strings.items()):
        vi = ''
        cur = exe.current_text(a)
        if cur is not None and fmap is not None:
            vi, filled = decode(cur, fmap), filled + 1
        rows.append(('0x%x' % a, ref_text(exe.refs[a]), s, vi, notes(s)))
    lost = exe.unreferenced()
    if lost:
        print('%d chuoi tieng Nhat khong tim thay cho tro toi - cong cu nay khong dich duoc (vd. %s)' % (
            len(lost), ', '.join('0x%x %s' % (a, s[:12].replace('\n', ' ')) for a, s in lost[:3])))
    if exe.current and fmap is None:
        print('exe nay da co ban dich: them --map de dien vao cot vi_text')
    if not out:
        for r in rows:
            print('%s  %-16s %s' % (r[0], r[1], r[2].replace('\n', '\\n')))
        return 0
    write_rows(out, COLUMNS, rows)
    print('%d dong -> %s%s' % (len(rows), out, ' (%d dong da dien ban dich dang co)' % filled if filled else ''))
    return 0


def cmd_import(path, sheet, map_path, out, report, apply):
    exe = open_exe(path)
    say_found(exe)
    fmap = load_map(map_path)
    rows = read_rows(sheet)
    writes, rep = plan(rows, exe, fmap)
    count = {}
    for x in rep:
        if x['action'] == 'skip':
            count[x['why']] = count.get(x['why'], 0) + 1
    print('bang: %d dong; ghi %d chuoi; bo qua: chua dich %d, jp khong khop %d, khong co trong exe %d, '
          'con sot chu Nhat %d, sai ma %%d %d, trung %d' % (
              len(rows), len(writes), count.get('empty', 0) + count.get('untranslated', 0), count.get('jp-mismatch', 0),
              count.get('no-string', 0), count.get('japanese', 0), count.get('format', 0), count.get('duplicate', 0)))
    unknown = sorted(set(ch for x in rep if x['action'] == 'write' for ch in x['more']))
    if unknown:
        print('font chua co: %s' % ' '.join('%s(U+%04X)' % (ch, ord(ch)) for ch in unknown))
    nbtn = sum(1 for x in rep if 'buttons' in x['why'])
    if nbtn:
        print('%d cau co ky hieu nut {..} khac tieng Nhat - xem bao cao' % nbtn)
    if exe.current and not writes:
        print('khong con cau nao duoc dich: exe ra se giong exe goc (bo ban dich cu)')
    raw, where = build(exe, writes)
    problems = verify(raw, exe, writes, where)
    if problems:
        print('KIEM TRA LOI:')
        for p in problems[:30]:
            print('  ' + p)
        return 1
    nsites = sum(len(exe.refs[a]) for a in writes)
    print('kiem tra: OK (%d cho tro da doi; hoan tac ra dung exe goc); main %d -> %d byte' % (
        nsites, os.path.getsize(path), len(raw)))
    if report:
        write_report(report, rep)
        print('bao cao -> %s' % report)
    if not apply:
        say_replaced(out, ('main',))
        print('chay thu - them --apply de ghi vao %s' % out)
        return 0
    write_files(out, (('main', raw),))
    return 0


def cmd_check(path):
    exe = open_exe(path)
    say_found(exe)
    problems = []
    for a in exe.current:
        if exe.current_text(a) is None:
            problems.append('ban dich dang co cua 0x%x doc khong duoc' % a)
    writes = dict(exe.strings)
    raw, where = build(exe, writes)
    problems += verify(raw, exe, writes, where)
    if exe.ambiguous:
        print('%d lenh ADD khong ro thuoc chuoi nao - bo qua' % len(exe.ambiguous))
    if problems:
        print('KIEM TRA LOI:')
        for p in problems[:30]:
            print('  ' + p)
        return 1
    print('kiem tra: OK - doi ca %d chuoi sang vung moi, moi cho tro doc dung chuoi, hoan tac ra dung exe' % len(writes))
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('cmd', choices=['export', 'import', 'check'])
    ap.add_argument('main', help='exefs/main (of the mod, or the Japanese one)')
    ap.add_argument('sheet', nargs='?', help='export: where to save the list (.csv, or .xlsx with openpyxl); '
                    'none: print it. import: the list with vi_text filled in')
    ap.add_argument('--map', help='font encoding (.json) from applysheet.py --map; needed by import')
    ap.add_argument('--out', help='import: folder the new main goes to (exefs inside the mod)')
    ap.add_argument('--report', help='import: CSV of every row and what was done with it')
    ap.add_argument('--apply', action='store_true', help='import: write the file')
    a = ap.parse_args()
    if a.cmd == 'export':
        return cmd_export(a.main, a.sheet, a.map)
    if a.cmd == 'import':
        if not a.sheet or not a.map or not a.out:
            ap.error('import: can bang dich, --map va --out')
        return cmd_import(a.main, a.sheet, a.map, a.out, a.report, a.apply)
    return cmd_check(a.main)


if __name__ == '__main__':
    sys.exit(main())
