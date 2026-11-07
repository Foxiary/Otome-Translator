# -*- coding: utf-8 -*-
"""rson.py - read and write rrlib RSON, the format of script.memfs.

    python rson.py dump  script.memfs          # print the tree
    python rson.py check script.memfs          # parse, write back, must be byte-identical

Only the node types script.memfs uses are known; anything else raises.

    header   'RSON', u32 file size, u32 root offset, u32 1
    0xe8     map:   count, 1 byte, then 2*count u16 offsets (values first, then
                    keys) and count u16 key hashes, sorted. Offsets are counted
                    BACKWARDS from the map's own tag byte: target = tag - offset.
    0xc8     array: count, element type (0x20 = u32, 0x30 = u16), elements
    0x88     string: byte length, UTF-16LE, two NUL bytes
    0x41 / 0x21 / 0x48 xx   int 1 / true / int8 - kept as raw bytes

The writer lays nodes out depth first - a map's values, then its keys, then the
map itself - and pads with NUL so an array's or map's payload after its 3-byte
header is 4-aligned. That reproduces both the JP and the VI file byte for byte,
which is what makes widening an entry safe: every offset is recomputed, none is
patched in place. Patching in place is what breaks the file.
"""
import argparse
import struct
import sys

ETYPE = {0x20: 'I', 0x30: 'H'}          # array element type -> struct code


class Map(object):
    def __init__(self, items, hashes, hdr3):
        self.items, self.hashes, self.hdr3 = items, hashes, hdr3


class Arr(object):
    def __init__(self, etype, vals):
        self.etype, self.vals = etype, list(vals)


class Str(object):
    def __init__(self, text):
        self.t = text


class Raw(object):
    """A small scalar kept as its exact bytes."""
    def __init__(self, b):
        self.b = b


def parse(m):
    if m[:4] != b'RSON':
        raise ValueError('not RSON (%r)' % m[:4])
    size, root, one = struct.unpack_from('<3I', m, 4)
    if size != len(m) or one != 1:
        raise ValueError('RSON header says size %d, file is %d' % (size, len(m)))

    def node(p):
        t = m[p]
        if t == 0xe8:
            n, hdr3 = m[p + 1], m[p + 2]
            offs = struct.unpack_from('<%dH' % (2 * n), m, p + 3)
            hashes = struct.unpack_from('<%dH' % n, m, p + 3 + 4 * n)
            vals = [node(p - o) for o in offs[:n]]
            keys = [node(p - o) for o in offs[n:]]
            return Map(list(zip(keys, vals)), hashes, hdr3)
        if t == 0xc8:
            n, et = m[p + 1], m[p + 2]
            if et not in ETYPE:
                raise ValueError('array element type %#x at %#x' % (et, p))
            return Arr(et, struct.unpack_from('<%d%s' % (n, ETYPE[et]), m, p + 3))
        if t == 0x88:
            n = m[p + 1]
            return Str(m[p + 2:p + 2 + n].decode('utf-16le'))
        if t in (0x41, 0x21):
            return Raw(bytes([t]))
        if t == 0x48:
            return Raw(m[p:p + 2])
        raise ValueError('unknown RSON tag %#x at %#x' % (t, p))

    return node(root)


def write(root):
    out = bytearray(b'RSON' + b'\0' * 12)

    def align(hdr):
        while (len(out) + hdr) % 4:
            out.append(0)

    def emit(v):
        if isinstance(v, Raw):
            p = len(out); out.extend(v.b); return p
        if isinstance(v, Str):
            b = v.t.encode('utf-16le')
            p = len(out); out.extend(bytes([0x88, len(b)]) + b + b'\0\0'); return p
        if isinstance(v, Arr):
            align(3); p = len(out)
            out.extend(bytes([0xc8, len(v.vals), v.etype]))
            out.extend(struct.pack('<%d%s' % (len(v.vals), ETYPE[v.etype]), *v.vals))
            return p
        if isinstance(v, Map):
            vp = [emit(val) for _, val in v.items]
            kp = [emit(k) for k, _ in v.items]
            align(3); p = len(out)
            offs = [p - x for x in vp + kp]
            if not all(0 < o <= 0xFFFF for o in offs):
                raise OverflowError('map offset out of u16 range')
            out.extend(bytes([0xe8, len(v.items), v.hdr3]))
            out.extend(struct.pack('<%dH' % len(offs), *offs))
            out.extend(struct.pack('<%dH' % len(v.hashes), *v.hashes))
            return p
        raise TypeError(type(v))

    root_pos = emit(root)
    struct.pack_into('<3I', out, 4, len(out), root_pos, 1)
    return bytes(out)


def entries(root):
    """{path: Arr([offset, size])} - the file table of a memfs."""
    for k, v in root.items:
        if k.t == 'path':
            return dict((kk.t, vv) for kk, vv in v.items)
    raise ValueError('no "path" table in this RSON')


def dump(v, indent=0):
    pad = '  ' * indent
    if isinstance(v, Map):
        for k, val in v.items:
            if isinstance(val, (Map,)):
                print('%s%s:' % (pad, k.t)); dump(val, indent + 1)
            else:
                print('%s%s: ' % (pad, k.t), end=''); dump(val, 0)
    elif isinstance(v, Arr):
        print('%s[%s] %s' % (pad, 'u32' if v.etype == 0x20 else 'u16', ', '.join(map(str, v.vals))))
    elif isinstance(v, Str):
        print('%s%r' % (pad, v.t))
    else:
        print('%s<%s>' % (pad, v.b.hex()))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('cmd', choices=['dump', 'check'])
    ap.add_argument('file')
    a = ap.parse_args()
    with open(a.file, 'rb') as f:
        data = f.read()
    root = parse(data)
    if a.cmd == 'dump':
        dump(root)
        return 0
    back = write(root)
    if back != data:
        print('KHONG khop: ghi lai ra %d byte, file goc %d byte' % (len(back), len(data)))
        return 1
    print('OK: %d byte, doc roi ghi lai giong tung byte' % len(data))
    return 0


if __name__ == '__main__':
    sys.exit(main())
