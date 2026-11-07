# -*- coding: utf-8 -*-
"""nsp.py - take single files out of a Switch NSP, without hactool.

    python nsp.py romfs <game.nsp> <out dir> common/script.memfs common/script.membody
    python nsp.py romfs <game.nsp> <out dir> --list            # every RomFS path
    python nsp.py exefs <game.nsp> <out dir>                   # main, rtld, sdk, ...

Keys: --keys, else ~/.switch/prod.keys. AES comes from pycryptodome when it is
installed, else from the `openssl` command (XTS is then done block by block
over AES-ECB, which `openssl enc` lacks).

Unlike engines/unity/tools/switchfs.py this never unpacks the whole RomFS -
Matsurika's is 12,842 files and 5.7 GB, almost all of it voice.

Traps that give plausible garbage rather than an error: the XTS tweak is the
sector number BIG-endian, and the CTR counter counts from the offset inside
the NCA, not inside the NSP. Base-game NSPs only (no BKTR update RomFS).
"""
import argparse
import fnmatch
import os
import shutil
import struct
import subprocess
import sys

OPENSSL = shutil.which('openssl') or '/opt/homebrew/bin/openssl'


def load_keys(path=None):
    path = path or os.path.expanduser('~/.switch/prod.keys')
    if not os.path.isfile(path):
        raise SystemExit('khong thay prod.keys (%s) - dung --keys' % path)
    k = {}
    with open(path) as f:
        for line in f:
            if '=' in line:
                a, b = line.split('=', 1)
                try:
                    k[a.strip()] = bytes.fromhex(b.strip())
                except ValueError:
                    pass
    return k


def _ossl(args, data):
    r = subprocess.run([OPENSSL] + args, input=data, capture_output=True)
    if r.returncode:
        raise RuntimeError(r.stderr.decode(errors='replace'))
    return r.stdout


def ecb(key, data, encrypt=False):
    try:
        from Crypto.Cipher import AES
        c = AES.new(key, AES.MODE_ECB)
        return c.encrypt(data) if encrypt else c.decrypt(data)
    except ImportError:
        return _ossl(['enc', '-e' if encrypt else '-d', '-aes-128-ecb', '-K', key.hex(), '-nopad'], data)


def ctr(key, iv, data):
    try:
        from Crypto.Cipher import AES
        from Crypto.Util import Counter
        c = AES.new(key, AES.MODE_CTR, counter=Counter.new(128, initial_value=int.from_bytes(iv, 'big')))
        return c.decrypt(data)
    except ImportError:
        return _ossl(['enc', '-d', '-aes-128-ctr', '-K', key.hex(), '-iv', iv.hex(), '-nopad'], data)


def xts_sector(key, sector, data):
    """Nintendo AES-XTS: tweak = sector number, big-endian."""
    k1, k2 = key[:16], key[16:]
    t = int.from_bytes(ecb(k2, sector.to_bytes(16, 'big'), True), 'little')
    tweaks = []
    for _ in range(len(data) // 16):
        tweaks.append(t.to_bytes(16, 'little'))
        t <<= 1
        if t >> 128:
            t = (t & ((1 << 128) - 1)) ^ 0x87
    tw = b''.join(tweaks)
    x = ecb(k1, bytes(a ^ b for a, b in zip(data, tw)))
    return bytes(a ^ b for a, b in zip(x, tw))


def pfs0(read, base=0):
    head = read(base, 16)
    if head[:4] != b'PFS0':
        raise ValueError('not PFS0')
    n, st = struct.unpack_from('<II', head, 4)
    blob = read(base, 16 + 0x18 * n + st)
    names = blob[16 + 0x18 * n:]
    data = base + 16 + 0x18 * n + st
    out = []
    for i in range(n):
        off, size, no = struct.unpack_from('<QQI', blob, 16 + 0x18 * i)
        out.append((names[no:names.index(b'\0', no)].decode(), data + off, size))
    return out


class NCA(object):
    def __init__(self, f, off, keys, tik):
        self.f, self.off = f, off
        f.seek(off); enc = f.read(0xC00)
        h = b''.join(xts_sector(keys['header_key'], i, enc[i * 0x200:(i + 1) * 0x200]) for i in range(6))
        if h[0x200:0x204] not in (b'NCA3', b'NCA2'):
            raise ValueError('NCA header does not decrypt - wrong keys?')
        self.h = h
        self.content = h[0x205]
        rev = max(max(h[0x206], h[0x220]) - 1, 0)
        if any(h[0x230:0x240]):
            if tik is None:
                raise ValueError('title key needed but no ticket in the NSP')
            self.key = ecb(keys['titlekek_%02x' % rev], tik[0x180:0x190])
        else:
            kak = keys[('key_area_key_application_%02x', 'key_area_key_ocean_%02x',
                        'key_area_key_system_%02x')[h[0x207]] % rev]
            self.key = ecb(kak, h[0x300:0x340])[0x20:0x30]
        self.sections = []
        for i in range(4):
            st, en = struct.unpack_from('<II', h, 0x240 + 0x10 * i)
            if en:
                self.sections.append((st * 0x200, h[0x400 + 0x200 * i:0x600 + 0x200 * i]))

    def reader(self, sec):
        start, fh = sec

        def read(rel, size):
            a = start + rel; a0 = a & ~0xF; pad = a - a0
            self.f.seek(self.off + a0)
            data = self.f.read((pad + size + 0xF) & ~0xF)
            if fh[4] == 1:                      # not encrypted
                return data[pad:pad + size]
            iv = bytes(reversed(fh[0x140:0x148])) + (a0 >> 4).to_bytes(8, 'big')
            return ctr(self.key, iv, data)[pad:pad + size]
        return read


def program_nca(path, keys):
    f = open(path, 'rb')
    ents = pfs0(lambda o, s: (f.seek(o), f.read(s))[1])
    tik = None
    for name, o, s in ents:
        if name.endswith('.tik'):
            f.seek(o); tik = f.read(s)
    for name, o, s in sorted(ents, key=lambda e: -e[2]):
        if name.endswith('.nca'):
            n = NCA(f, o, keys, tik)
            if n.content == 0:
                return n
    raise SystemExit('khong thay NCA program trong %s' % path)


def romfs_files(nca):
    for sec in nca.sections:
        fh = sec[1]
        if fh[2] != 0 or fh[8:12] != b'IVFC':
            continue
        read = nca.reader(sec)
        base = struct.unpack_from('<Q', fh, 0x18 + 0x18 * 5)[0]
        v = struct.unpack_from('<10Q', read(base, 0x50), 0)
        dmeta, fmeta, data = read(base + v[3], v[4]), read(base + v[7], v[8]), base + v[9]

        def dpath(o):
            parts = []
            while o:
                parent, _, _, _, _, nl = struct.unpack_from('<6I', dmeta, o)
                parts.append(dmeta[o + 24:o + 24 + nl].decode()); o = parent
            return '/'.join(reversed(parts))
        out = {}; o = 0
        while o < len(fmeta):
            parent, _, doff, dsz, _, nl = struct.unpack_from('<IIQQII', fmeta, o)
            out[(dpath(parent) + '/' + fmeta[o + 32:o + 32 + nl].decode()).lstrip('/')] = (data + doff, dsz)
            o += 32 + ((nl + 3) & ~3)
        return read, out
    raise SystemExit('khong thay RomFS')


def cmd_romfs(a):
    read, files = romfs_files(program_nca(a.nsp, load_keys(a.keys)))
    if a.list:
        for p in sorted(files):
            print('%12d  %s' % (files[p][1], p))
        return 0
    want = [p for p in sorted(files) if any(fnmatch.fnmatch(p, pat) for pat in a.paths)]
    if not want:
        raise SystemExit('khong file nao khop %s' % ' '.join(a.paths))
    for p in want:
        off, size = files[p]
        dst = os.path.join(a.out, p)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, 'wb') as w:
            w.write(read(off, size))
        print('%12d  %s' % (size, dst))
    return 0


def cmd_exefs(a):
    nca = program_nca(a.nsp, load_keys(a.keys))
    for sec in nca.sections:
        fh = sec[1]
        if fh[2] != 1:
            continue
        layers = struct.unpack_from('<I', fh, 0x2C)[0]
        base = struct.unpack_from('<Q', fh, 0x30 + (layers - 1) * 0x10)[0]
        read = nca.reader(sec)
        items = pfs0(read, base)
        if not any(n == 'main' for n, _, _ in items):
            continue
        os.makedirs(a.out, exist_ok=True)
        for n, off, size in items:
            with open(os.path.join(a.out, n), 'wb') as w:
                w.write(read(off, size))
            print('%12d  %s' % (size, os.path.join(a.out, n)))
        return 0
    raise SystemExit('khong thay ExeFS')


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('romfs')
    p.add_argument('nsp'); p.add_argument('out'); p.add_argument('paths', nargs='*')
    p.add_argument('--list', action='store_true'); p.add_argument('--keys')
    p = sub.add_parser('exefs')
    p.add_argument('nsp'); p.add_argument('out'); p.add_argument('--keys')
    a = ap.parse_args()
    if a.cmd == 'romfs' and not a.list and not a.paths:
        ap.error('romfs: can duong dan file (vd. common/script.*) hoac --list')
    return cmd_romfs(a) if a.cmd == 'romfs' else cmd_exefs(a)


if __name__ == '__main__':
    sys.exit(main())
