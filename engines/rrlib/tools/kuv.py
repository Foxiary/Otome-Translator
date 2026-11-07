# -*- coding: utf-8 -*-
"""kuv.py - read and rebuild a .tat script ("KUV " bytecode).

    python kuv.py strings EV00_0001_01.tat [--grep TEXT]   # index + string
    python kuv.py calls   EV00_0001_01.tat [--from N --to N]
    python kuv.py check   EV00_0001_01.tat                 # rebuild unchanged, compare

Header, 20 x u32:

    [0] 0xc0deabc1  [1] 'KUV '  [2] 0x64  [3] header size
    [4] string count            [8] label count
    [10] string table: count x (u32 offset into pool, u32 byte length)
    [16] string pool, UTF-16LE, each string NUL-terminated
    [17] end of pool + padding  [18] code start  [19] code length
    name of the script, UTF-16 at 0x60; build date at 0xa0

Code refers to strings by index only - push is `0e` + big-endian u32 index,
call is `2b 2c argc 00` with the function name pushed last - so strings can be
replaced at any length without touching a byte of code. `build()` rewrites the
table, the pool and the offsets after it, and copies the code verbatim.

[19] must equal the code length. An older VI build added the pool growth to it
in 10 files; the game tolerated that, the JP files never have it, and `build()`
always writes the true length.
"""
import argparse
import struct
import sys

MAGIC = b'KUV '


def is_kuv(raw):
    return raw[4:8] == MAGIC


def name(raw):
    return raw[0x60:0xa0].decode('utf-16le').split('\0')[0] if is_kuv(raw) else None


def parse(d):
    """-> (header list, strings, bytes of pool used)."""
    if not is_kuv(d):
        raise ValueError('not a KUV script')
    h = list(struct.unpack_from('<20I', d, 0))
    n, tab, pool = h[4], h[10], h[16]
    offs = [struct.unpack_from('<2I', d, tab + 8 * i) for i in range(n)]
    strs = [d[pool + o:pool + o + l].decode('utf-16le') for o, l in offs]
    used = offs[-1][0] + offs[-1][1] + 2 if n else 0
    return h, strs, used


def code(d):
    h = struct.unpack_from('<20I', d, 0)
    return d[h[18]:]


def length_ok(d):
    h = struct.unpack_from('<20I', d, 0)
    return h[18] + h[19] == len(d)


def build(d, strs):
    """d with its strings replaced by strs (same count). Code is copied as is."""
    h, old, used = parse(d)
    if len(strs) != len(old):
        raise ValueError('need %d strings, got %d' % (len(old), len(strs)))
    n, tab, pool = h[4], h[10], h[16]
    pad_after_pool = h[17] - (pool + used)
    section = d[h[17]:h[18]]
    body = bytearray(); table = bytearray()
    for s in strs:
        b = s.encode('utf-16le')
        table += struct.pack('<2I', len(body), len(b))
        body += b + b'\0\0'
    out = bytearray(d[:pool])
    out[tab:tab + 8 * n] = table
    out += body + b'\0' * pad_after_pool + section
    c = code(d)
    nh = h[:]
    nh[17] = pool + len(body) + pad_after_pool
    nh[18] = nh[17] + len(section)
    nh[19] = len(c)
    struct.pack_into('<20I', out, 0, *nh)
    return bytes(out + c)


def calls(d):
    """[(function name, [arg string indices], code offset)] in code order.

    Reads only the push/call pattern; other opcodes are stepped over a byte at
    a time, which is enough to see which message calls follow which."""
    h, strs, _ = parse(d)
    c = code(d)
    out = []; stack = []; i = 0
    while i < len(c):
        if c[i] == 0x0e and i + 5 <= len(c):
            v = struct.unpack('>I', c[i + 1:i + 5])[0]
            if v < len(strs):
                stack.append(v); i += 5; continue
        if c[i:i + 2] == b'\x2b\x2c' and i + 4 <= len(c):
            argc = c[i + 2]
            if stack:
                out.append((strs[stack[-1]], stack[-1 - argc:-1] if argc else [], i))
            stack = []; i += 4; continue
        i += 1
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('cmd', choices=['strings', 'calls', 'check'])
    ap.add_argument('file')
    ap.add_argument('--grep')
    ap.add_argument('--from', dest='lo', type=int, default=0)
    ap.add_argument('--to', dest='hi', type=int, default=None)
    a = ap.parse_args()
    with open(a.file, 'rb') as f:
        d = f.read()
    h, strs, _ = parse(d)
    if a.cmd == 'strings':
        for i, s in enumerate(strs):
            if a.grep and a.grep not in s:
                continue
            print('%5d  %r' % (i, s))
    elif a.cmd == 'calls':
        cl = calls(d)
        hi = a.hi if a.hi is not None else 1 << 30
        hit = [k for k, (_, args, _) in enumerate(cl) if any(a.lo <= x <= hi for x in args)]
        # print the whole stretch of code between the first and last call touching the range,
        # so argument-less calls (KW, WinClear) in between stay visible
        lo_k, hi_k = (hit[0], hit[-1]) if hit else (0, -1)
        if a.lo == 0 and a.hi is None:
            lo_k, hi_k = 0, len(cl) - 1
        for f, args, off in cl[lo_k:hi_k + 1]:
            print('%06x  %-18s %s' % (off, f, ' | '.join('#%d %r' % (x, strs[x][:50]) for x in args)))
    else:
        back = build(d, strs)
        if back == d:
            print('OK: %s, %d chuoi, dung lai giong tung byte' % (name(d), len(strs)))
            return 0
        if not length_ok(d) and back[:0x4c] + back[0x50:] == d[:0x4c] + d[0x50:]:
            print('OK: %s chi khac do dai code o header (file goc ghi sai, ban dung lai ghi dung)' % name(d))
            return 0
        print('KHONG khop: %s' % name(d))
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
