# -*- coding: utf-8 -*-
"""font.py - the game's fonts: romfs/spec_win/font/*.font.memfs.

    python font.py info    standard.font.memfs
    python font.py check   standard.font.memfs            # read, write back: must be byte-identical
    python font.py export  standard.font.memfs out/       # textures as PNG + glyphs.tsv
    python font.py preview standard.font.memfs "Xin chào" out.png [--outline standard_outline.font.memfs]
    python font.py preview <font folder> "Xin chào" out.png [--map map.json]   # 一 二 三 四, each outlined
    python font.py gen --template <JP font folder> --out <mod>/romfs/spec_win/font \\
        --font Foo-Regular.ttf [--font Bar.ttf ...] [--font-extra2 Brush.ttf] [--width 90] \\
        [--map map.json] [--map-out map.json] [--preview new.png [--preview-text "Xin chào"]] [--apply]

`gen` redraws Latin glyphs from OTF/TTF fonts - the same idea as the Otomate
ffugen.py, for this engine's format. Give it the JP font folder (or one
.font.memfs) and it writes every *.font.memfs it finds into --out, the
*_outline ones included, which it builds from the glyphs it just drew. The
five faces differ (standard rounded gothic, extra bold gothic, extra2 brush,
extra3 serif, ui): --font-standard / --font-extra / --font-extra2 /
--font-extra3 / --font-ui give one of them its own source font, tried before
the --font ones. Without --apply it is a dry run; with it, a file
already in --out is first copied to .bak beside it.

What it draws (each from the first --font that has the character):
  - printable ASCII except the space, and the Vietnamese alphabet;
  - --map map.json (`applysheet.py --map` writes it): the VI letters the mod's
    scripts encode on kana codes (ệ -> る). Each letter is drawn into the cell
    of its code, so the scripts built today show the new typeface unchanged;
  - every other letter the font lacks is ADDED under its own code point - the
    capitals the old patch never mapped (Ể, Ổ), or, without --map, the whole
    alphabet. --map-out writes the map plus those letters, for
    `applysheet.py --use-map`, so the next script build writes them.
  - --no-latin keeps the template's ASCII/Latin-1 glyphs and draws only the
    Vietnamese letters.
Kana and kanji are kept. Without --map the kana are left as the JP font has
them, so Japanese still left in the exe reads as Japanese again - but then
EVERY Vietnamese string must carry real Unicode, the speaker names and choices
the sheet does not cover included; with today's mod scripts use --map.

The size is fitted so 'H' is as tall as the template's and the letters sit on
the template's baseline. --px sets one size for every font, --px-standard /
--px-extra / ... one font's (its _outline follows); the dry run prints the
fitted size and how much wider the letters come out than the template's.
--width 90 (or --width-standard / ...) draws every letter 90% as wide at the
same height, and its advance with it: the way to fit a line in fewer px
without making the letters shorter. The game has no kerning, so a font whose
letters run into each other (a joining script, a brush face) gets a few px
more on every advance and the space - see
tracking(); the dry run says how many. An *_outline font is the border
drawn under the text: its glyphs are the text glyphs widened by a radius that
gen measures on the template pair (4.0-4.8 px depending on the font).

FORMAT (worked out on JP v1.0.0; see also CLAUDE.md "Fonts")

  The file is an rrlib/memfs with the body inside ('hasSeparateBody' false):
  'bin' holds /fontdata.00.rtex ... /fontdata.NN.rtex and /fontdata.rson,
  'path' names them. It uses more of RSON than script.memfs does, so it has
  its own reader/writer here (rson.py is left as it is):

    tag = kind (top 3 bits) | size code (low 5 bits)
    size code 0-7: the value itself; 8-15: 1 more byte, 16-23: 2 more, 24: 4
    more, the code's low 3 bits being the top bits - all BIG-endian.
    0x20/0x21 false/true; 0x40 int (codes 0-7 = 0,1,-1,2,-2,3,-3,4, longer
    ones two's complement in 11/19/32 bits); 0x80 UTF-16LE string (byte
    length) + 2 NULs; 0xa0 binary blob, 4-aligned; 0xc0 array: count, element
    byte - 0x40/0x30/0x20 = u8/u16/u32 LE values, 0..3 = offsets of 1..4
    bytes to child nodes (2-byte ones LE, 3-byte ones BE, as found);
    0xe0 map: count, h, value offsets (u16 LE, or u32 LE when h=1), key
    offsets (u16 LE), key hashes (u16 LE) = CRC-16/CCITT-FALSE of the
    UTF-16LE key, entries sorted by hash. Offsets count back from the
    parent's tag. Children are written before parents; maps and node arrays
    pad so their payload is 4-aligned, typed arrays to their element size.

  /fontdata.rson (rrlib/rfnt2): baseInfo (charWidth/charHeight 40,
  renderMarginX/Y 20/22, offsetX/Y -8/-19, texture size and count),
  gryphInfo [one u8/u16/u32 array per glyph: texture, x, y, w, h, advance,
  dx, dy] and charToIndex {character: glyph}. Cells are 60x62 on a 62x64
  grid; the pen origin is 8 px in (-offsetX) and the baseline 53 px down.
  dx/dy move a glyph whose ink would leave the cell: the JP 'p' is drawn 3 px
  higher in its cell with dy 10 instead of 7, 'î' 3 px to the right with
  dx -3; gen follows the same rule (ink kept right of x 7 and above y 59)
  and also keeps the outline's width clear on every side (place()), so the
  border under a g's tail is not cut flat on the cell's last row as JP's is.

  .rtex: 'RTEX' header (see sprite.py), 2048x2048, flags 0x84002 = BC3/DXT5,
  linear block order (no swizzle), payload 'RZ' + BE size + zlib. Alpha is
  the glyph; RGB is a white mask 1 px wider (an _outline font: the widened
  shape). gen re-encodes only the 4x4 blocks of the cells it draws, so every
  other glyph keeps its exact bytes.

Needs Pillow (pip install Pillow); fontTools is used if present.
"""
import argparse
import binascii
import bisect
import json
import math
import os
import struct
import sys
import zlib

# ------------------------------------------------------------------ RSON

ALIGN = 4
INT_ET = {0x40: 1, 0x30: 2, 0x20: 4}       # typed array element byte -> width
ET_OF = {1: 0x40, 2: 0x30, 4: 0x20}


def key_hash(key):
    return binascii.crc_hqx(key.encode('utf-16le'), 0xffff)


class Map(object):
    """An RSON map: [key, value] pairs kept in hash order."""

    def __init__(self, items=None):
        self.items = items or []

    def __getitem__(self, key):
        for k, v in self.items:
            if k == key:
                return v
        raise KeyError(key)

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def __setitem__(self, key, value):
        for it in self.items:
            if it[0] == key:
                it[1] = value
                return
        self.insert(key, value)

    def insert(self, key, value):
        """Add a new key after every key with the same or a lower hash."""
        hs = [key_hash(k) for k, _ in self.items]
        self.items.insert(bisect.bisect_right(hs, key_hash(key)), [key, value])

    def keys(self):
        return [k for k, _ in self.items]


class IntArr(object):
    """A typed array of integers (u8/u16/u32, little-endian)."""

    def __init__(self, vals):
        self.vals = list(vals)


def _size(m, p):
    """-> (value from the tag's size code, header length)."""
    t = m[p] & 0x1f
    if t < 8:
        return t, 1
    if t < 16:
        return ((t & 7) << 8) | m[p + 1], 2
    if t < 24:
        return ((t & 7) << 16) | (m[p + 1] << 8) | m[p + 2], 3
    if t == 24:
        return int.from_bytes(m[p + 1:p + 5], 'big'), 5
    raise ValueError('size code %#x at %#x' % (m[p], p))


def _size_head(kind, n):
    if n < 0x800:
        return bytes([kind | 0x08 | n >> 8, n & 0xff])
    if n < 0x80000:
        return bytes([kind | 0x10 | n >> 16]) + (n & 0xffff).to_bytes(2, 'big')
    return bytes([kind | 0x18]) + n.to_bytes(4, 'big')


def _int_bytes(v):
    if -3 <= v <= 4:
        return bytes([0x40 | (2 * v - 1 if v > 0 else -2 * v)])
    if -0x400 <= v < 0x400:
        u = v & 0x7ff
        return bytes([0x48 | u >> 8, u & 0xff])
    if -0x40000 <= v < 0x40000:
        u = v & 0x7ffff
        return bytes([0x50 | u >> 16]) + (u & 0xffff).to_bytes(2, 'big')
    return bytes([0x58]) + (v & 0xffffffff).to_bytes(4, 'big')


def _off_read(m, q, w):
    return int.from_bytes(m[q:q + w], 'big' if w == 3 else 'little')


def _off_bytes(v, w):
    return v.to_bytes(w, 'big' if w == 3 else 'little')


def parse(m):
    """RSON bytes -> tree of Map / list / IntArr / str / bytes / int / bool."""
    if m[:4] != b'RSON':
        raise ValueError('not RSON (%r)' % bytes(m[:4]))
    size, root, one = struct.unpack_from('<3I', m, 4)
    if size != len(m) or one != 1:
        raise ValueError('RSON header says size %d, data is %d' % (size, len(m)))

    def node(p):
        kind = m[p] & 0xe0
        if kind == 0x20:
            if m[p] not in (0x20, 0x21):
                raise ValueError('bool tag %#x at %#x' % (m[p], p))
            return m[p] == 0x21
        if kind == 0x40:
            t = m[p] & 0x1f
            if t < 8:
                return (t + 1) // 2 if t & 1 else -(t // 2)
            v, n = _size(m, p)
            bits = {2: 11, 3: 19, 5: 32}[n]
            return v - (1 << bits) if v >= 1 << (bits - 1) else v
        n, hl = _size(m, p)
        q = p + hl
        if kind == 0x80:
            return bytes(m[q:q + n]).decode('utf-16le')
        if kind == 0xa0:
            return bytes(m[q:q + n])
        if kind == 0xc0:
            et = m[q]
            q += 1
            if et in INT_ET:
                w = INT_ET[et]
                return IntArr(int.from_bytes(m[q + w * i:q + w * i + w], 'little') for i in range(n))
            if et > 3:
                raise ValueError('array element byte %#x at %#x' % (et, p))
            w = et + 1
            return [node(p - _off_read(m, q + w * i, w)) for i in range(n)]
        if kind == 0xe0:
            h = m[q]
            q += 1
            if h not in (0, 1):
                raise ValueError('map offset width %d at %#x' % (h, p))
            vw = 4 if h else 2
            vo = [_off_read(m, q + vw * i, vw) for i in range(n)]
            q += vw * n
            ko = struct.unpack_from('<%dH' % n, m, q)
            hs = struct.unpack_from('<%dH' % n, m, q + 2 * n)
            items = []
            for k, v, hh in zip(ko, vo, hs):
                key = node(p - k)
                if key_hash(key) != hh:
                    raise ValueError('key %r: hash %#x, expected %#x' % (key, hh, key_hash(key)))
                items.append([key, node(p - v)])
            return Map(items)
        raise ValueError('RSON tag %#x at %#x' % (m[p], p))

    return node(root)


def write(root):
    out = bytearray(b'RSON' + b'\0' * 12)

    def pad(head, n):
        while (len(out) + head) % n:
            out.append(0)

    def emit(v):
        if isinstance(v, bool):
            p = len(out)
            out.append(0x21 if v else 0x20)
            return p
        if isinstance(v, int):
            p = len(out)
            out.extend(_int_bytes(v))
            return p
        if isinstance(v, str):
            b = v.encode('utf-16le')
            head = _size_head(0x80, len(b))
            pad(len(head), 2)
            p = len(out)
            out.extend(head + b + b'\0\0')
            return p
        if isinstance(v, (bytes, bytearray)):
            head = _size_head(0xa0, len(v))
            pad(len(head), ALIGN)
            p = len(out)
            out.extend(head + v)
            return p
        if isinstance(v, IntArr):
            vals = [x & 0xffffffff for x in v.vals]      # negatives go out as u32
            hi = max(vals) if vals else 0
            w = 1 if hi < 0x100 else 2 if hi < 0x10000 else 4
            head = _size_head(0xc0, len(vals)) + bytes([ET_OF[w]])
            pad(len(head), w)
            p = len(out)
            out.extend(head)
            for x in vals:
                out.extend(x.to_bytes(w, 'little'))
            return p
        if isinstance(v, list):
            ps = [emit(x) for x in v]
            head = _size_head(0xc0, len(v)) + b'\0'
            pad(len(head), 4)
            p = len(out)
            offs = [p - x for x in ps]
            w = next(w for w in (1, 2, 3, 4) if max(offs or [0]) < 1 << (8 * w))
            head = head[:-1] + bytes([w - 1])
            out.extend(head)
            for o in offs:
                out.extend(_off_bytes(o, w))
            return p
        if isinstance(v, Map):
            vp = [emit(val) for _, val in v.items]
            kp = [emit(k) for k, _ in v.items]
            head = _size_head(0xe0, len(v.items))
            pad(len(head) + 1, 4)
            p = len(out)
            vo = [p - x for x in vp]
            ko = [p - x for x in kp]
            h = 1 if max(vo or [0]) > 0xffff else 0
            if max(ko or [0]) > 0xffff:
                raise OverflowError('map key offset past u16')
            out.extend(head + bytes([h]))
            out.extend(b''.join(_off_bytes(o, 4 if h else 2) for o in vo))
            out.extend(struct.pack('<%dH' % len(ko), *ko))
            out.extend(struct.pack('<%dH' % len(ko), *[key_hash(k) for k, _ in v.items]))
            return p
        raise TypeError(type(v))

    root_pos = emit(root)
    struct.pack_into('<3I', out, 4, len(out), root_pos, 1)
    return bytes(out)


# ------------------------------------------------------------------ BC3 textures

RTEX_HEAD = 0x20
BC3_FLAGS = 0x84002
EMPTY_BLOCK = bytes([0, 5]) + bytes(14)        # what the JP fonts use for nothing


def _g565(g):
    return ((g * 31 + 127) // 255) << 11 | ((g * 63 + 127) // 255) << 5 | ((g * 31 + 127) // 255)


def _g8(c):
    return ((c >> 11) * 255 + 15) // 31            # red channel, as gray


_dec_cache = {}


def decode_block(b):
    """16-byte BC3 block -> (16 alpha values, 16 gray values from red)."""
    r = _dec_cache.get(b)
    if r is not None:
        return r
    a0, a1 = b[0], b[1]
    if a0 > a1:
        pal = [a0, a1] + [((7 - i) * a0 + i * a1 + 3) // 7 for i in range(1, 7)]
    else:
        pal = [a0, a1] + [((5 - i) * a0 + i * a1 + 2) // 5 for i in range(1, 5)] + [0, 255]
    ab = int.from_bytes(b[2:8], 'little')
    alpha = [pal[(ab >> (3 * i)) & 7] for i in range(16)]
    c0, c1 = struct.unpack_from('<2H', b, 8)
    g0, g1 = _g8(c0), _g8(c1)
    if c0 > c1:
        cp = [g0, g1, (2 * g0 + g1 + 1) // 3, (g0 + 2 * g1 + 1) // 3]
    else:
        cp = [g0, g1, (g0 + g1) // 2, 0]
    ci = int.from_bytes(b[12:16], 'little')
    gray = [cp[(ci >> (2 * i)) & 3] for i in range(16)]
    r = (alpha, gray)
    if len(_dec_cache) < 200000:
        _dec_cache[b] = r
    return r


def _fit(vals, pal):
    idx, err = [], 0
    for v in vals:
        best = min(range(len(pal)), key=lambda i: abs(pal[i] - v))
        idx.append(best)
        err += (pal[best] - v) ** 2
    return idx, err


def encode_block(alpha, gray):
    """16 alpha + 16 gray values -> 16-byte BC3 block."""
    if not any(alpha) and not any(gray):
        return EMPTY_BLOCK
    lo, hi = min(alpha), max(alpha)
    if lo == hi:
        ablock = bytes([lo, lo]) + bytes(6)
    else:
        pal8 = [hi, lo] + [((7 - i) * hi + i * lo + 3) // 7 for i in range(1, 7)]
        i8, e8 = _fit(alpha, pal8)
        mid = [v for v in alpha if 0 < v < 255] or [lo, hi]
        l6, h6 = min(mid), max(mid)
        pal6 = [l6, h6] + [((5 - i) * l6 + i * h6 + 2) // 5 for i in range(1, 5)] + [0, 255]
        i6, e6 = _fit(alpha, pal6)
        a0, a1, idx = (hi, lo, i8) if e8 <= e6 else (l6, h6, i6)
        bits = 0
        for i, x in enumerate(idx):
            bits |= x << (3 * i)
        ablock = bytes([a0, a1]) + bits.to_bytes(6, 'little')
    glo, ghi = min(gray), max(gray)
    c0, c1 = _g565(ghi), _g565(glo)
    if c0 == c1:
        cblock = struct.pack('<2HI', c0, c1, 0)
    else:
        g0, g1 = _g8(c0), _g8(c1)
        idx, _ = _fit(gray, [g0, g1, (2 * g0 + g1 + 1) // 3, (g0 + 2 * g1 + 1) // 3])
        bits = 0
        for i, x in enumerate(idx):
            bits |= x << (2 * i)
        cblock = struct.pack('<2HI', c0, c1, bits)
    return ablock + cblock


class Texture(object):
    """One fontdata.NN.rtex, BC3 blocks kept as bytes and edited in place."""

    def __init__(self, blob):
        if blob[:4] != b'RTEX':
            raise ValueError('not an RTEX texture')
        self.blob = blob
        self.w, self.h, self.pw, self.ph = struct.unpack_from('<4H', blob, 8)
        hs, ps, self.flags, self.stride = struct.unpack_from('<4I', blob, 16)
        if self.flags != BC3_FLAGS or hs != RTEX_HEAD:
            raise ValueError('texture flags %#x: only BC3 (0x84002) fonts are known' % self.flags)
        pay = blob[RTEX_HEAD:RTEX_HEAD + ps]
        if pay[:2] != b'RZ':
            raise ValueError('texture payload is not RZ-wrapped')
        self.raw = bytearray(zlib.decompress(pay[6:]))
        if len(self.raw) != int.from_bytes(pay[2:6], 'big') or len(self.raw) != self.pw * self.ph:
            raise ValueError('texture payload size does not match %dx%d BC3' % (self.pw, self.ph))
        self.bw = self.pw // 4
        self.dirty = False

    def to_blob(self):
        if not self.dirty:
            return self.blob
        pay = b'RZ' + len(self.raw).to_bytes(4, 'big') + zlib.compress(bytes(self.raw), 9)
        head = bytearray(self.blob[:RTEX_HEAD])
        struct.pack_into('<I', head, 20, len(pay))
        return bytes(head) + pay

    def _block(self, bx, by):
        o = (by * self.bw + bx) * 16
        return bytes(self.raw[o:o + 16])

    def read(self, x0, y0, w, h):
        """-> (alpha, gray) PIL 'L' images of a rectangle."""
        from PIL import Image
        a = bytearray(w * h)
        g = bytearray(w * h)
        for by in range(y0 // 4, (y0 + h - 1) // 4 + 1):
            for bx in range(x0 // 4, (x0 + w - 1) // 4 + 1):
                al, gr = decode_block(self._block(bx, by))
                for i in range(16):
                    x, y = bx * 4 + (i & 3) - x0, by * 4 + (i >> 2) - y0
                    if 0 <= x < w and 0 <= y < h:
                        a[y * w + x], g[y * w + x] = al[i], gr[i]
        return Image.frombytes('L', (w, h), bytes(a)), Image.frombytes('L', (w, h), bytes(g))

    def write(self, x0, y0, alpha, gray):
        """Paste (alpha, gray) 'L' images at (x0, y0), re-encoding only those blocks."""
        w, h = alpha.size
        ad, gd = alpha.tobytes(), gray.tobytes()
        for by in range(y0 // 4, (y0 + h - 1) // 4 + 1):
            for bx in range(x0 // 4, (x0 + w - 1) // 4 + 1):
                old = self._block(bx, by)
                al, gr = decode_block(old)
                al, gr = list(al), list(gr)
                for i in range(16):
                    x, y = bx * 4 + (i & 3) - x0, by * 4 + (i >> 2) - y0
                    if 0 <= x < w and 0 <= y < h:
                        al[i], gr[i] = ad[y * w + x], gd[y * w + x]
                new = encode_block(al, gr)
                if new != old:
                    o = (by * self.bw + bx) * 16
                    self.raw[o:o + 16] = new
                    self.dirty = True

    def image(self):
        """The whole texture as an RGBA PIL image (gray from red, alpha)."""
        from PIL import Image
        a = bytearray(self.pw * self.ph)
        g = bytearray(self.pw * self.ph)
        for by in range(self.ph // 4):
            for bx in range(self.bw):
                al, gr = decode_block(self._block(bx, by))
                if not any(al) and not any(gr):
                    continue
                for i in range(16):
                    o = (by * 4 + (i >> 2)) * self.pw + bx * 4 + (i & 3)
                    a[o], g[o] = al[i], gr[i]
        gi = Image.frombytes('L', (self.pw, self.ph), bytes(g))
        return Image.merge('RGBA', (gi, gi, gi, Image.frombytes('L', (self.pw, self.ph), bytes(a))))


# ------------------------------------------------------------------ font file

def _s32(v):
    return v - (1 << 32) if v >= 1 << 31 else v


class Glyph(object):
    __slots__ = ('index', 'tex', 'x', 'y', 'w', 'h', 'adv', 'dx', 'dy')

    def __init__(self, index, vals):
        self.index = index
        self.tex, self.x, self.y, self.w, self.h, self.adv, dx, dy = vals
        self.dx, self.dy = _s32(dx), _s32(dy)

    def vals(self):
        return [self.tex, self.x, self.y, self.w, self.h, self.adv, self.dx, self.dy]


class Font(object):
    def __init__(self, data, name=''):
        self.name = name
        self.root = parse(data)
        if self.root.get('@fileType') != 'rrlib/memfs' or self.root.get('hasSeparateBody') is not False:
            raise ValueError('%s: not a self-contained rrlib/memfs' % name)
        self.bins = self.root['bin']
        self.paths = self.root['path']
        self.info = parse(self.bins[self.paths['/fontdata.rson']])
        if self.info.get('@fileType') != 'rrlib/rfnt2':
            raise ValueError('%s: fontdata.rson is %r, not rrlib/rfnt2' % (name, self.info.get('@fileType')))
        self.base = self.info['baseInfo']
        self.glyphs = [Glyph(i, a.vals) for i, a in enumerate(self.info['gryphInfo'])]
        self.char_index = dict((k, v) for k, v in self.info['charToIndex'].items)
        self._tex = {}
        self.added = []                       # characters given a new glyph

    @classmethod
    def load(cls, path):
        with open(path, 'rb') as f:
            return cls(f.read(), os.path.basename(path))

    def glyph(self, ch):
        i = self.char_index.get(ch)
        return None if i is None else self.glyphs[i]

    def texture(self, i):
        if i not in self._tex:
            self._tex[i] = Texture(self.bins[self.paths['/fontdata.%02d.rtex' % i]])
        return self._tex[i]

    @property
    def texture_count(self):
        return self.base['textureCount']

    def cell(self, g):
        """-> (alpha, gray) images of a glyph's cell."""
        return self.texture(g.tex).read(g.x, g.y, g.w, g.h)

    def put(self, g, alpha, gray):
        self.texture(g.tex).write(g.x, g.y, alpha, gray)

    def free_slot(self):
        """Next free cell on the grid the JP fonts pack on (column by column)."""
        w, h = self.glyphs[0].w, self.glyphs[0].h
        px = w + 2 * self.base['packMarginX']
        py = h + 2 * self.base['packMarginY']
        tw, th = self.base['textureWidth'], self.base['textureHeight']
        t = self.texture_count - 1
        used = set((g.x, g.y) for g in self.glyphs if g.tex == t)
        for x in range(0, tw - w + 1, px):
            for y in range(0, th - h + 1, py):
                if (x, y) not in used:
                    return t, x, y
        raise SystemExit('%s: no free cell left in texture %d' % (self.name, t))

    def add(self, ch, adv, dx, dy):
        """A new glyph for `ch` in a free cell; returns it."""
        t, x, y = self.free_slot()
        tmpl = self.glyphs[0]
        g = Glyph(len(self.glyphs), [t, x, y, tmpl.w, tmpl.h, adv, dx & 0xffffffff, dy & 0xffffffff])
        self.glyphs.append(g)
        self.char_index[ch] = g.index
        self.info['charToIndex'].insert(ch, g.index)
        self.added.append(ch)
        return g

    def to_bytes(self):
        self.info['gryphInfo'] = [IntArr(g.vals()) for g in self.glyphs]
        self.base['charaCount'] = len(self.glyphs)
        bins = list(self.bins)
        bins[self.paths['/fontdata.rson']] = write(self.info)
        for i, t in self._tex.items():
            bins[self.paths['/fontdata.%02d.rtex' % i]] = t.to_blob()
        self.root['bin'] = bins
        return write(self.root)


# ------------------------------------------------------------------ source fonts

_VN = ('AÀÁẢÃẠĂẰẮẲẴẶÂẦẤẨẪẬ'
       'EÈÉẺẼẸÊỀẾỂỄỆ'
       'IÌÍỈĨỊ'
       'OÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢ'
       'UÙÚỦŨỤƯỪỨỬỮỰ'
       'YỲÝỶỸỴĐ')
VN_CHARS = [c for ch in _VN for c in (ch, ch.lower())]
ASCII = [chr(c) for c in range(0x21, 0x7f)]


class Source(object):
    def __init__(self, spec, px, width=1.0):
        from PIL import ImageFont
        path, _, idx = spec.partition('#')
        self.path, self.index, self.px = path, int(idx or 0), px
        self.width = width                # horizontal scale of every glyph and advance (--width)
        if not os.path.isfile(path):
            raise SystemExit('font not found: %s' % path)
        self.font = ImageFont.truetype(path, px, index=self.index)
        self.cmap = None
        self.name = os.path.basename(path)
        try:
            from fontTools.ttLib import TTFont, TTCollection
            tt = TTCollection(path).fonts[self.index] if path.lower().endswith('.ttc') else TTFont(path, lazy=True)
            self.cmap = set(tt.getBestCmap().keys())
            self.name = tt['name'].getDebugName(4) or self.name
            tt.close()
        except Exception:
            self._tofu = self._mask('\U0010fffd')

    def _mask(self, ch):
        m = self.font.getmask(ch, mode='L')
        return (m.size, bytes(m))

    def length(self, text):
        """Advance of `text` in px, at this source's width."""
        return self.font.getlength(text) * self.width

    def has(self, ch):
        if self.cmap is not None:
            return ord(ch) in self.cmap
        if ch.isspace():
            return True
        m = self._mask(ch)
        return m != self._tofu and any(m[1])

    def __repr__(self):
        return '%s @%dpx' % (self.name, self.px)


class Chain(object):
    def __init__(self, specs, px, width=1.0):
        self.sources = [Source(s, px, width) for s in specs]

    def pick(self, ch):
        for s in self.sources:
            if s.has(ch):
                return s
        return None


def fit_px(spec, cap):
    """Pixel size at which 'H' is `cap` px tall in the first font."""
    from PIL import ImageFont
    path, _, idx = spec.partition('#')
    best, best_err, lo, hi = 8, 10 ** 9, 4, 200
    while lo <= hi:
        mid = (lo + hi) // 2
        bb = ImageFont.truetype(path, mid, index=int(idx or 0)).getbbox('H', anchor='ls')
        h = bb[3] - bb[1]
        if abs(h - cap) < best_err:
            best, best_err = mid, abs(h - cap)
        if h < cap:
            lo = mid + 1
        elif h > cap:
            hi = mid - 1
        else:
            return mid
    return best


# ------------------------------------------------------------------ metrics and drawing

LEFT_MIN = 7         # the JP glyphs keep ink right of this column ...
BOTTOM_MAX = 59      # ... and above this row; past it the glyph moves (dx/dy)


def outline_room(radius):
    """Px the _outline glyph reaches past the text's ink: widen() spreads
    `radius` px plus a soft rim that fades out 1 px further (4.7 -> 5)."""
    return int(math.ceil(radius + 1)) - 1 if radius else 0


def place(box, w, h, room=0):
    """-> (sx, sy, fits) for ink with box (left, top, right, bottom) in a w x h
    cell: move it sx px right and sy px up so it keeps LEFT_MIN / BOTTOM_MAX
    and leaves `room` px on every side for the outline drawn from it.

    The JP fonts only keep the text in: their g/p/y end on row 59 and the
    outline under them is cut flat on the cell's last row. A Vietnamese g has a
    round tail, and the cut showed (user, 2026-11-08). Moving the ink is free -
    dx/dy put it back on the line - so it moves as little as it can and only
    when it must; a glyph too tall for its room keeps the text whole and shares
    the cut between top and bottom. fits: nothing is cut."""
    l, t, r, b = box
    lo_x, hi_x = max(LEFT_MIN, room) - l, (w - room) - r
    sx = max(lo_x, min(0, hi_x))                     # the left limit wins, as before
    lo_y, hi_y = b - min(BOTTOM_MAX, h - room), t - room
    sy = max(lo_y, min(0, hi_y)) if lo_y <= hi_y else (lo_y + hi_y + 1) // 2
    sy = max(b - h, min(t, sy))                      # never cut the text itself
    fits = lo_x <= hi_x and lo_y <= hi_y
    return sx, sy, fits


class Metrics(object):
    """Where a template draws its letters, measured on its own glyphs."""

    def __init__(self, font):
        ref = font.glyph('H')
        if ref is None:
            raise SystemExit('%s: no H to measure' % font.name)
        a, _ = font.cell(ref)
        bb = a.getbbox()
        self.cap = bb[3] - bb[1]
        self.baseline = bb[3] + (ref.dy - self.dy0(font))
        self.origin = -font.base['offsetX']
        self.w, self.h = ref.w, ref.h

    @staticmethod
    def dy0(font):
        ys = [g.dy for g in font.glyphs[:256]]
        return max(set(ys), key=ys.count)


PAD = 32             # room around a cell while drawing, for ink that leaves it


def _draw(source, text, m):
    """`text` drawn with its pen at (PAD + origin, PAD + baseline) of a cell
    with PAD px around it -> (image, ink bbox or None)."""
    from PIL import Image, ImageDraw
    im = Image.new('L', (m.w + 2 * PAD, m.h + 2 * PAD), 0)
    ImageDraw.Draw(im).text((PAD + m.origin, PAD + m.baseline), text, font=source.font,
                            fill=255, anchor='ls')
    k = getattr(source, 'width', 1.0)
    if k != 1:
        # narrower (or wider) round the pen: the letter keeps its height and
        # baseline, and still starts where the pen is
        pen = PAD + m.origin
        # BOX (area average) when narrowing: LANCZOS rings, and the faint halo
        # it leaves would count as ink when tracking() measures the gaps
        sq = im.resize((max(1, int(round(im.width * k))), im.height), Image.BOX if k < 1 else Image.BILINEAR)
        im = Image.new('L', im.size, 0)
        im.paste(sq, (int(round(pen - pen * k)), 0))
    return im, im.getbbox()


TRACK_GAP = 1        # px: letters whose ink sits closer than this get spaced out
WIDTH_MIN, WIDTH_MAX = 50, 150     # --width, in %


def tracking(chain, m, text=None):
    """Px to add to every advance so neighbouring letters stop running into
    each other: 0 for a font whose letters already clear each other.

    A joining script (VL Ricca Script) or a brush face (VL Kathya) has each
    letter's strokes reach past its advance into the next one - the font's
    contextual forms and kerning make them meet, but the game has neither,
    and the outline under each letter turns the overlaps into one blob. The
    median clear space between neighbouring letters' ink in `text` (SAMPLE),
    as gen draws them, is brought up to TRACK_GAP: standard sources measure
    +2 and get nothing, those two -3 and get 4."""
    gaps = []
    for word in (text or SAMPLE).split():
        prev = None                       # (advance, ink right) of the letter before
        for ch in word:
            src = chain.pick(ch)
            bb = _draw(src, ch, m)[1] if src else None
            if prev and bb:
                gaps.append(prev[0] + (bb[0] - PAD - m.origin) - prev[1])
            prev = (max(1, int(round(src.length(ch)))), bb[2] - PAD - m.origin) if bb else None
    if not gaps:
        return 0
    return max(0, TRACK_GAP - sorted(gaps)[len(gaps) // 2])


def draw_glyph(source, text, m, dy0, track=0, room=0):
    """-> (alpha image of the cell, advance, dx, dy, clipped?, fits?) for
    `text`; track (from tracking()) is added to the advance, room (from
    outline_room()) kept clear around the ink for the outline - the same for a
    font and its _outline so both place every glyph alike. clipped: the text
    itself is cut; fits: neither text nor outline is."""
    pad = PAD
    im, bb = _draw(source, text, m)
    adv = max(1, int(round(source.length(text)))) + track
    sx = sy = 0
    fits = True
    if bb:
        sx, sy, fits = place([v - pad for v in bb], m.w, m.h, room)
    cell = im.crop((pad - sx, pad + sy, pad - sx + m.w, pad + sy + m.h))
    clipped = bool(bb) and cell.getbbox() != (bb[0] - pad + sx, bb[1] - pad - sy,
                                              bb[2] - pad + sx, bb[3] - pad - sy)
    return cell, adv, -sx, dy0 + sy, clipped, fits and not clipped


def widen(alpha, radius, hard):
    """The outline: the glyph's hardened shape spread by `radius` px, soft rim."""
    from PIL import Image, ImageChops
    src = alpha.point(lambda v: min(255, int(v * hard)))
    acc = Image.new('L', alpha.size, 0)
    r = int(math.ceil(radius)) + 1
    for oy in range(-r, r + 1):
        for ox in range(-r, r + 1):
            w = min(1.0, max(0.0, radius + 1.0 - math.hypot(ox, oy)))
            if w <= 0:
                continue
            sh = Image.new('L', alpha.size, 0)
            sh.paste(src, (ox, oy))
            if w < 1:
                sh = sh.point(lambda v, w=w: int(v * w + 0.5))
            acc = ImageChops.lighter(acc, sh)
    return acc


def mask(alpha, grow=1):
    """The white RGB under a glyph: where it has ink, `grow` px wider."""
    from PIL import ImageFilter
    m = alpha.point(lambda v: 255 if v else 0)
    return m.filter(ImageFilter.MaxFilter(2 * grow + 1)) if grow else m


def fit_outline(main, outline, chars='AHIox口一'):
    """(radius, hardness) that turn `main` glyphs into `outline`'s best."""
    from PIL import ImageChops
    pairs = []
    for ch in chars:
        g, o = main.glyph(ch), outline.glyph(ch)
        if g is not None and o is not None:
            pairs.append((main.cell(g)[0], outline.cell(o)[0]))
    if not pairs:
        return 4.6, 1.0

    def err(radius, hard):
        e = 0
        for a, t in pairs:
            hist = ImageChops.difference(widen(a, radius, hard), t).histogram()
            e += sum(v * v * c for v, c in enumerate(hist))
        return e

    best = min((err(r, h), r, h) for r in (2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0)
               for h in (1.0, 2.0))
    r0 = best[1]
    best = min([best] + [(err(r, h), r, h) for r in (r0 - 0.4, r0 - 0.2, r0 + 0.2, r0 + 0.4)
                         for h in (1.0, 1.5, 2.0) if r > 0])
    return round(best[1], 1), best[2]


# ------------------------------------------------------------------ gen

def clean_map(fmap):
    """Drop a letter that shares its code with another one.

    The map applysheet learns has Ể and ể both on ろ (Ổ/ổ on ゼ): the old patch
    wrote those capitals with the small letter. The cell keeps the small letter
    and the capital gets a code of its own. -> (map, dropped letters)"""
    by_code = {}
    for k, v in sorted(fmap.items()):
        by_code.setdefault(v, []).append(k)
    out, dropped = {}, []
    for v, ks in by_code.items():
        keep = [k for k in ks if k == k.lower()] if len(ks) > 1 else ks
        keep = keep[:1] or ks[:1]
        out[keep[0]] = v
        dropped += [k for k in ks if k != keep[0]]
    return out, dropped


def plan_chars(font, fmap, latin):
    """-> [(code the game uses, text to draw)] in a stable order."""
    want = []
    if latin:
        want += [(c, c) for c in ASCII]
    taken = set(fmap.values())
    for letter in VN_CHARS:
        if letter in fmap:
            want.append((fmap[letter], letter))
        elif not latin and letter.isascii():
            continue
        elif letter in taken and letter not in fmap:
            raise SystemExit('the map puts another letter on %r, which is itself a letter to draw' % letter)
        else:
            want.append((letter, letter))
    seen, out = set(), []
    for code, text in want:
        if code not in seen:
            seen.add(code)
            out.append((code, text))
    return out


def generate(tpl, chain, chars, m, outline=None, track=0, room=0):
    """Draw `chars` [(code, text)] into `tpl` (a Font, edited in place).

    m: the Metrics to draw on - the main font's, for an _outline font too.
    outline: (radius, hardness) when tpl is an _outline font. track: px
    added to every advance drawn, and to the space's (see tracking()). room:
    px kept clear around each glyph for the family's outline, the same for
    the font and its _outline (see place()). Returns a report."""
    dy0 = Metrics.dy0(tpl)
    rep = {'drawn': 0, 'added': [], 'missing': [], 'clipped': [], 'tight': []}
    space = tpl.glyph(' ')
    if track and space is not None:
        space.adv += track
    for code, text in chars:
        src = chain.pick(text)
        if src is None:
            rep['missing'].append(text)
            continue
        alpha, adv, dx, dy, clipped, fits = draw_glyph(src, text, m, dy0, track, room)
        if clipped:
            rep['clipped'].append(text)
        elif not fits:
            rep['tight'].append(text)
        if outline:
            alpha = widen(alpha, *outline)
        g = tpl.glyph(code)
        if g is None:
            g = tpl.add(code, adv, dx, dy)
            rep['added'].append((code, text))
        else:
            g.adv, g.dx, g.dy = adv, dx, dy
        tpl.put(g, alpha, mask(alpha, 0 if outline else 1))
        rep['drawn'] += 1
    return rep


def font_files(path):
    if os.path.isdir(path):
        names = sorted(n for n in os.listdir(path) if n.endswith('.font.memfs'))
        if not names:
            raise SystemExit('no *.font.memfs in %s' % path)
        return [os.path.join(path, n) for n in names]
    return [path]


def main_of(path):
    """standard_outline.font.memfs -> standard.font.memfs, or None."""
    d, n = os.path.split(path)
    if not n.endswith('_outline.font.memfs'):
        return None
    return os.path.join(d, n.replace('_outline.font.memfs', '.font.memfs'))


def family(path):
    """standard_outline.font.memfs -> 'standard'."""
    n = os.path.basename(path)[:-len('.font.memfs')]
    return n[:-len('_outline')] if n.endswith('_outline') else n


FAMILIES = ('standard', 'extra', 'extra2', 'extra3', 'ui')


def font_chains(fonts, own, files):
    """{family: [font specs]}: its own --font-<family> first, then every --font."""
    names = sorted(set(family(p) for p in files))
    return dict((n, ([own[n]] if own.get(n) else []) + list(fonts)) for n in names)


SAMPLE = 'Xin chào, tôi là người Việt Nam. Hôm nay trời rất đẹp, chúng ta cùng đi dạo nhé!'
# What one character takes on the line the VI scripts are wrapped for (62 to a
# line, measured in game on the dialogue font). A template whose own Latin is
# narrower - extra3's 12 px - was never what lines were sized by.
LINE_CHAR_PX = 18.4


def mean_advance(src, track=0):
    """Mean advance in px of SAMPLE: from a template Font, or a Chain spaced
    out by `track` px (what gen writes)."""
    import unicodedata
    total = 0
    for ch in SAMPLE:
        if isinstance(src, Font):
            g = src.glyph(ch) or src.glyph(unicodedata.normalize('NFD', ch)[0])
            total += g.adv if g else 0
        else:
            s = src.pick(ch)
            total += int(round(s.length(ch))) + track if s else 0
    return total / float(len(SAMPLE))


def cmd_gen(a):
    fmap = {}
    if a.map:
        with open(a.map, encoding='utf-8') as f:
            fmap = json.load(f)
        bad = [k for k, v in fmap.items() if len(k) != 1 or len(v) != 1]
        if bad:
            raise SystemExit('%s: entries must map one letter to one character (%s)' % (a.map, ', '.join(bad[:5])))
        fmap, dropped = clean_map(fmap)
        if dropped:
            print('bang ma: %s dung chung o voi chu thuong -> cho o rieng' % ''.join(dropped))
    else:
        print('CANH BAO: khong co --map. Chu Viet duoc them voi ma Unicode that va cac o kana giu chu Nhat,'
              ' nen kich ban hien tai (viet chu Viet bang ma kana) se hien kana (ộ -> ば).'
              ' Chi bo --map khi moi chuoi tieng Viet da dung Unicode.')
    if a.preview_text and not a.preview:
        raise SystemExit('--preview-text needs --preview: the image (.png) to draw it into')
    if a.preview and os.path.isdir(a.preview):
        raise SystemExit('--preview is the image file to save (.png), not a folder')
    files = font_files(a.template)
    if os.path.isfile(a.out):
        raise SystemExit('--out is a folder (e.g. <mod>/romfs/spec_win/font), not a file')
    for p in files:
        if os.path.abspath(os.path.join(a.out, os.path.basename(p))) == os.path.abspath(p):
            raise SystemExit('--out would overwrite the template %s' % p)
    chains = font_chains(a.font, dict((n, getattr(a, 'font_' + n)) for n in FAMILIES), files)

    extra = [(c, c) for c in (a.chars or '') if not c.isspace()]
    newmap = dict(fmap)
    results, built = [], {}
    borders = {}

    def border_of(p):
        """(radius, hardness) of the outline the family of `p` gets, or None
        when its _outline font is not being built. Measured once on the
        templates, so the font and its outline leave the same room."""
        fam = family(p)
        if fam not in borders:
            d = os.path.dirname(p)
            mp = os.path.join(d, fam + '.font.memfs')
            op = os.path.join(d, fam + '_outline.font.memfs')
            if op not in files or not os.path.isfile(mp):
                borders[fam] = None
            elif a.outline_radius:
                borders[fam] = (a.outline_radius, 1.0)
            else:
                borders[fam] = fit_outline(Font.load(mp), Font.load(op))
        return borders[fam]

    for p in files:
        tpl = Font.load(p)
        main_path = main_of(p)
        if main_path:
            if not os.path.isfile(main_path):
                raise SystemExit('%s is an outline font; its main font %s must sit beside it'
                                 % (os.path.basename(p), os.path.basename(main_path)))
            ref = Font.load(main_path)
            if [g.vals() for g in ref.glyphs] != [g.vals() for g in tpl.glyphs]:
                print('  ! %s: glyph table differs from %s' % (tpl.name, ref.name))
        else:
            ref = tpl
        border = border_of(p)
        outline = border if main_path else None
        room = outline_room(border[0]) if border else 0
        m = Metrics(ref)
        specs = chains[family(p)]
        fit = fit_px(specs[0], m.cap)
        px = getattr(a, 'px_' + family(p), None) or a.px or fit
        width = getattr(a, 'width_' + family(p), None) or a.width or 100
        if not WIDTH_MIN <= width <= WIDTH_MAX:
            raise SystemExit('--width %g: be ngang phai tu %d den %d (%%)' % (width, WIDTH_MIN, WIDTH_MAX))
        chain = Chain(specs, px, width / 100.0)
        chars = plan_chars(tpl, fmap, not a.no_latin) + extra
        # measured on the main font's metrics, so the outline gets the same advances
        track = tracking(chain, m)
        print('%s: %d glyph, chu H cao %d px, baseline %d -> %s %d px%s%s%s'
              % (tpl.name, len(tpl.glyphs), m.cap, m.baseline, chain.sources[0].name, px,
                 ' (dat tay; vua chu H la %d px)' % fit if px != fit else ' (vua chu H)',
                 ', be ngang %g%%' % width if width != 100 else '',
                 ', vien %.1f px' % outline[0] if outline else ''))
        if not main_path:
            if track:
                print('  chu cua font nay de len nhau (net noi / but long): gian them %d px moi chu va dau cach'
                      % track)
            old, new = mean_advance(ref), mean_advance(chain, track)
            print('  rong TB 1 chu: font goc %.1f px -> moi %.1f px (%+d%%)%s' % (
                old, new, round(100 * (new / old - 1)),
                ' - cau dai co the tran khung, thu --px nho hon' if new > max(old, LINE_CHAR_PX) * 1.08 else ''))
        # an outline font is drawn on its main font's metrics: it must hug those letters
        rep = generate(tpl, chain, chars, m, outline, track, room)
        data = tpl.to_bytes()
        check = Font(data, tpl.name)
        if len(check.glyphs) != len(tpl.glyphs):
            raise SystemExit('%s: rebuilt file does not read back' % tpl.name)
        for code, text in rep['added']:
            if code == text and not code.isascii():
                newmap[code] = code       # a letter under its own code: applysheet must pass it through
        print('  ve %d chu, them %d o moi%s%s%s' % (
            rep['drawn'], len(rep['added']),
            ('; font khong co: ' + ''.join(rep['missing'])) if rep['missing'] else '',
            ('; bi cat mep: ' + ''.join(rep['clipped'])) if rep['clipped'] else '',
            ('; vien bi cat (chu cao/rong qua o %dx%d, thu --px nho hon): %s'
             % (m.w, m.h, ''.join(rep['tight']))) if rep['tight'] and not main_path else ''))
        results.append((os.path.basename(p), data))
        built[os.path.basename(p)] = check

    if a.preview:
        # the new fonts as they would be written, the text encoded as applysheet
        # would with the saved map - drawn on the dry run too, before any write
        have = set(family(n) for n in built)
        fonts = pick_fonts(have, built.get)
        text = ''.join(newmap.get(c, c) for c in (a.preview_text or PREVIEW_SAMPLE))
        draw_preview(fonts, text, a.preview, decode=dict((v, k) for k, v in newmap.items()))

    from patch import say_replaced, write_files
    if not a.apply:
        say_replaced(a.out, [n for n, _ in results])
        print('%d font san sang.' % len(results))
        print('chay thu - them --apply de ghi vao %s' % a.out)
    else:
        write_files(a.out, results)
    if a.map_out:
        with open(a.map_out, 'w', encoding='utf-8') as f:
            json.dump(newmap, f, ensure_ascii=False, indent=0, sort_keys=True)
        print('bang ma -> %s (%d chu; dung voi applysheet.py --use-map)' % (a.map_out, len(newmap)))
    return 0


# ------------------------------------------------------------------ preview / export / info

def render_text(font, text, outline=None, scale=1):
    """The game's way of laying out one line, roughly: pen + advance, dx/dy."""
    from PIL import Image
    m = Metrics(font)
    dy0 = Metrics.dy0(font)
    gs = [font.glyph(ch) for ch in text]
    width = sum(g.adv for g in gs if g) + 2 * m.w
    canvas = Image.new('RGBA', (width, m.h + 16), (40, 40, 60, 255))
    pen = m.origin + 4
    layers = ([(outline, (0, 0, 0))] if outline else []) + [(font, (255, 255, 255))]
    for f, colour in layers:
        x = pen
        for ch, g in zip(text, gs):
            if g is None:
                x += m.w // 2
                continue
            fg = f.glyph(ch) or g
            a, _ = f.cell(fg)
            solid = Image.new('RGBA', a.size, colour + (255,))
            canvas.paste(solid, (x - m.origin + fg.dx, 8 + fg.dy - dy0), a)
            x += g.adv
    if scale != 1:
        canvas = canvas.resize((canvas.width * scale, canvas.height * scale), Image.NEAREST)
    return canvas


SETTINGS = ('standard', 'extra', 'extra2', 'extra3')   # the settings screen's フォント 一 二 三 四
SETTINGS_MARKS = '一二三四'
PREVIEW_GAP = 16


def stack(images, gap=0, rule=False):
    """Images one under another on the preview background; rule draws a thin
    line in the middle of each gap."""
    from PIL import Image, ImageDraw
    im = Image.new('RGBA', (max(i.width for i in images),
                            sum(i.height for i in images) + gap * (len(images) - 1)), (40, 40, 60, 255))
    y = 0
    for n, i in enumerate(images):
        if n and rule:
            ImageDraw.Draw(im).line((0, y - gap // 2, im.width, y - gap // 2), fill=(80, 80, 110, 255))
        im.paste(i, (0, y))
        y += i.height + gap
    return im


# The text gen --preview draws when no --preview-text is given: a sentence,
# then every small and the capital letters that sit on kana codes or are new.
PREVIEW_SAMPLE = ('Ngày xưa ở làng ven biển, có cô gái tên Hằng: "Đừng sợ, tôi ở đây!"\\n'
                  'ả ã ạ ằ ẳ ẵ ặ ầ ẩ ẫ ậ ề ể ễ ệ ỉ ĩ ị ồ ổ ỗ ộ ờ ở ỡ ợ ừ ử ữ ự ỳ ỷ ỹ ỵ đ\\n'
                  'Ả Ạ Ằ Ặ Ẫ Ậ Đ Ể Ễ Ệ Ỉ Ị Ổ Ộ Ờ Ợ Ừ Ữ Ự Ỳ Ỹ 0123456789')


def pick_fonts(have, load):
    """[(name, font, outline font)] to draw from the families in `have`: the
    four settings fonts in their order, or every font when none of them is
    there. load(file name) gives a Font or None."""
    names = [n for n in SETTINGS if n in have] or sorted(have)
    if any(n in have for n in SETTINGS):
        for n in SETTINGS:
            if n not in have:
                print('khong thay %s.font.memfs - bo qua' % n)
    return [(n, load(n + '.font.memfs'), load(n + '_outline.font.memfs')) for n in names]


def preview_fonts(path, outline=None):
    """What `preview` draws: one file, or a font folder's settings fonts,
    each with the _outline beside it."""
    if not os.path.isdir(path):
        return [(os.path.basename(path), Font.load(path), Font.load(outline) if outline else None)]
    if outline:
        print('--outline bo qua: moi font dung file _outline cua no trong thu muc')

    def load(name):
        p = os.path.join(path, name)
        return Font.load(p) if os.path.isfile(p) else None
    have = set(n[:-len('.font.memfs')] for n in os.listdir(path)
               if n.endswith('.font.memfs') and not n.endswith('_outline.font.memfs'))
    return pick_fonts(have, load)


def draw_preview(fonts, text, out, encoded=True, decode=None):
    """Draw text (\\n splits lines) with each (name, font, outline) into one
    PNG, one block per font, and say what each font lacks (shown through
    decode, {code: letter}, when the text is encoded)."""
    blocks, lacking = [], False
    for name, font, outline in fonts:
        missing = sorted(set(c for c in text.replace('\\n', '') if font.glyph(c) is None))
        if missing:
            lacking = True
            print('%s khong co: %s' % (name, ''.join((decode or {}).get(c, c) for c in missing)))
        blocks.append(stack([render_text(font, line, outline) for line in text.split('\\n')]))
    if lacking and not encoded:
        print('Font dung bang ma (gen --map) thi chon them --map de ma hoa chu nhu kich ban.')
    stack(blocks, PREVIEW_GAP, rule=True).save(out)
    order = ''
    if len(fonts) > 1:
        order = '  (tu tren xuong: %s)' % ', '.join(
            '%s %s' % (n, SETTINGS_MARKS[SETTINGS.index(n)]) if n in SETTINGS else n for n, _, _ in fonts)
    print('anh xem truoc -> %s%s' % (out, order))


def cmd_preview(a):
    text = a.text
    if a.map:
        with open(a.map, encoding='utf-8') as f:
            fmap = json.load(f)
        text = ''.join(fmap.get(c, c) for c in text)
    fonts = preview_fonts(a.font, a.outline)
    if not fonts:
        print('LOI: %s khong co file *.font.memfs nao' % a.font)
        return 1
    draw_preview(fonts, text, a.out, bool(a.map))
    return 0


def cmd_export(a):
    font = Font.load(a.font)
    os.makedirs(a.out, exist_ok=True)
    for i in range(font.texture_count):
        p = os.path.join(a.out, 'fontdata.%02d.png' % i)
        font.texture(i).image().save(p)
        print('-> %s' % p)
    inv = dict((v, k) for k, v in font.char_index.items())
    p = os.path.join(a.out, 'glyphs.tsv')
    with open(p, 'w', encoding='utf-8') as f:
        f.write('index\tchar\tcode\ttexture\tx\ty\tw\th\tadvance\tdx\tdy\n')
        for g in font.glyphs:
            ch = inv.get(g.index, '')
            f.write('%d\t%s\t%s\t%s\n' % (g.index, ch, 'U+%04X' % ord(ch) if len(ch) == 1 else '',
                                          '\t'.join(str(v) for v in g.vals()[:6] + [g.dx, g.dy])))
    print('-> %s' % p)
    return 0


def cmd_info(a):
    font = Font.load(a.font)
    b = dict((k, v) for k, v in font.base.items)
    print('%s: %d glyph, %d texture %dx%d, o %dx%d, em %dx%d, offset %d,%d' % (
        font.name, len(font.glyphs), b['textureCount'], b['textureWidth'], b['textureHeight'],
        font.glyphs[0].w, font.glyphs[0].h, b['charWidth'], b['charHeight'], b['offsetX'], b['offsetY']))
    m = Metrics(font)
    print('chu H cao %d px, baseline hang %d, goc but cot %d' % (m.cap, m.baseline, m.origin))
    vn = [c for c in VN_CHARS if not c.isascii()]
    have = [c for c in vn if font.glyph(c)]
    print('chu Viet co ma rieng: %d/%d%s' % (len(have), len(vn),
          ('; thieu ' + ''.join(c for c in vn if not font.glyph(c))) if len(have) < len(vn) else ''))
    return 0


def cmd_check(a):
    bad = 0
    for p in font_files(a.font):
        with open(p, 'rb') as f:
            data = f.read()
        font = Font(data, os.path.basename(p))
        back = font.to_bytes()
        ok = back == data
        bad += not ok
        print('%s: %s (%d glyph)' % (font.name, 'OK - ghi lai giong tung byte' if ok else
                                     'KHONG khop (%d -> %d byte)' % (len(data), len(back)), len(font.glyphs)))
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('info', help='glyph count, metrics, which Vietnamese letters have a code')
    s.add_argument('font')
    s = sub.add_parser('check', help='read and write back unchanged (file or folder)')
    s.add_argument('font')
    s = sub.add_parser('export', help='textures as PNG and glyphs.tsv')
    s.add_argument('font')
    s.add_argument('out')
    s = sub.add_parser('preview', help='draw a line of text with the font into a PNG')
    s.add_argument('font', help='a .font.memfs, or a font folder: its four settings fonts '
                                '(standard, extra, extra2, extra3), one under another, each with its outline')
    s.add_argument('text', help='text; \\n starts a new line')
    s.add_argument('out')
    s.add_argument('--outline', help='the matching _outline font, drawn under the text in black')
    s.add_argument('--map', help='encode the text with this map first (as applysheet does)')
    s = sub.add_parser('gen', help='redraw Latin and Vietnamese glyphs from OTF/TTF fonts')
    s.add_argument('--template', required=True, help='JP .font.memfs, or the folder of them')
    s.add_argument('--out', required=True, help='output folder, e.g. <mod>/romfs/spec_win/font')
    s.add_argument('--font', action='append', required=True,
                   help='source font; repeat in priority order. "file.ttc#1" picks a face')
    for n in FAMILIES:
        s.add_argument('--font-' + n, metavar='FILE',
                       help='source font for %s(_outline).font.memfs only, tried before --font' % n)
    s.add_argument('--px', type=int, help='pixel size for every font; default: fit H to each template')
    for n in FAMILIES:
        s.add_argument('--px-' + n, type=int, metavar='PX',
                       help='pixel size for %s(_outline).font.memfs only, over --px' % n)
    s.add_argument('--width', type=float, metavar='PCT',
                   help='letter width in %% of the source font for every font (90 = 10%% narrower, same height);'
                        ' default 100')
    for n in FAMILIES:
        s.add_argument('--width-' + n, type=float, metavar='PCT',
                       help='letter width in %%%% for %s(_outline).font.memfs only, over --width' % n)
    s.add_argument('--map', help='JSON {letter: code} from applysheet.py --map: draw letters on those codes')
    s.add_argument('--map-out', help='write the map plus every letter added under its own code')
    s.add_argument('--preview', metavar='PNG', help='draw text with the new fonts into this image, also on a dry run:'
                                                    ' the four settings fonts (一 二 三 四), each with its outline')
    s.add_argument('--preview-text', metavar='TEXT', help='text for --preview (\\n starts a new line);'
                                                          ' default: a sentence and every Vietnamese letter')
    s.add_argument('--chars', help='more characters to draw at their own code')
    s.add_argument('--no-latin', action='store_true', help="keep the template's ASCII glyphs")
    s.add_argument('--outline-radius', type=float, help='outline width in px; default: measured')
    s.add_argument('--apply', action='store_true', help='write the files (default: dry run)')
    a = ap.parse_args()
    return {'info': cmd_info, 'check': cmd_check, 'export': cmd_export,
            'preview': cmd_preview, 'gen': cmd_gen}[a.cmd](a)


if __name__ == '__main__':
    sys.exit(main())
