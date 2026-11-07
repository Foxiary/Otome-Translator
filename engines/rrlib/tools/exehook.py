# -*- coding: utf-8 -*-
"""exehook.py - find the read redirects a patched exefs/main carries.

    python exehook.py exefs/main

The VI patch of 02/10 could not fit three prologue scripts in script.memfs:
those entries are u16, and the Vietnamese copies had to go at the end of
script.membody, past 65535. Instead of widening the entries it hooked the
membody read in `main`. Three call sites branch into a code cave that does

    if (offset == A && size == S) offset = B;     // for three (A, S, B)

so memfs keeps the JP offset with the VI size, and the read lands on the
appended chunk. Any rebuild that leaves an entry equal to one of those (A, S)
pairs gets silently redirected - `patch.py` refuses to write one.

The cave is found by its instruction pattern, not by address:

    movz w16,#A ; cmp w3,w16 ; b.ne ; movz w16,#S ; cmp w2,w16 ; b.eq ; b
    movz w3,#B_lo ; movk w3,#B_hi,lsl#16 ; movz w2,#S

The NSO is decompressed first (LZ4 block segments).
"""
import argparse
import struct
import sys

NSO_MAGIC = b'NSO0'


def lz4_block(src, out_size):
    dst = bytearray(); i, n = 0, len(src)
    while i < n:
        token = src[i]; i += 1
        lit = token >> 4
        if lit == 15:
            while True:
                b = src[i]; i += 1; lit += b
                if b != 255:
                    break
        dst += src[i:i + lit]; i += lit
        if i >= n:
            break
        off = src[i] | (src[i + 1] << 8); i += 2
        mlen = token & 15
        if mlen == 15:
            while True:
                b = src[i]; i += 1; mlen += b
                if b != 255:
                    break
        start = len(dst) - off
        for k in range(mlen + 4):
            dst.append(dst[start + k])
    if len(dst) != out_size:
        raise ValueError('LZ4: %d bytes out, header says %d' % (len(dst), out_size))
    return bytes(dst)


def text_segment(nso):
    if nso[:4] != NSO_MAGIC:
        raise ValueError('not an NSO (%r)' % nso[:4])
    flags = struct.unpack_from('<I', nso, 0x0C)[0]
    foff, _moff, dsize = struct.unpack_from('<3I', nso, 0x10)
    packed = struct.unpack_from('<I', nso, 0x60)[0]
    raw = nso[foff:foff + packed]
    return lz4_block(raw, dsize) if flags & 1 else raw


def _movz(w, rd):
    """imm16 of `movz w<rd>, #imm` (no shift), else None."""
    if w & 0xffe0001f == 0x52800000 | rd:
        return (w >> 5) & 0xffff
    return None


def _movk16(w, rd):
    """imm16 of `movk w<rd>, #imm, lsl #16`, else None."""
    if w & 0xffe0001f == 0x72a00000 | rd:
        return (w >> 5) & 0xffff
    return None


CMP_W3_W16 = 0x6b10007f
CMP_W2_W16 = 0x6b10005f


def redirects(text):
    """{(offset, size): new offset} found in a .text segment."""
    out = {}
    words = struct.unpack('<%dI' % (len(text) // 4), text[:len(text) // 4 * 4])
    for i in range(len(words) - 10):
        a = _movz(words[i], 16)
        if a is None or words[i + 1] != CMP_W3_W16:
            continue
        s = _movz(words[i + 3], 16)
        if s is None or words[i + 4] != CMP_W2_W16:
            continue
        lo, hi, s2 = _movz(words[i + 7], 3), _movk16(words[i + 8], 3), _movz(words[i + 9], 2)
        if lo is None or hi is None or s2 != s:
            continue
        out[(a, s)] = lo | (hi << 16)
    return out


def from_main(path):
    with open(path, 'rb') as f:
        return redirects(text_segment(f.read()))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('main')
    a = ap.parse_args()
    found = from_main(a.main)
    if not found:
        print('Khong co doan chuyen huong nao (exe goc, hoac ban va kieu khac).')
        return 0
    for (off, size), new in sorted(found.items()):
        print('offset %8d  size %6d  ->  offset %8d' % (off, size, new))
    return 0


if __name__ == '__main__':
    sys.exit(main())
