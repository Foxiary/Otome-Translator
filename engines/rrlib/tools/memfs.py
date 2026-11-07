# -*- coding: utf-8 -*-
"""memfs.py - the script archive: script.memfs (index) + script.membody (data).

    python memfs.py list   script.memfs script.membody [--exe exefs/main]
    python memfs.py unpack script.memfs script.membody out/ [--exe exefs/main]
    python memfs.py check  script.memfs script.membody

script.membody is chunks laid back to back, no padding:

    'RZ'  u32 BIG-endian uncompressed size  zlib stream

script.memfs (RSON, see rson.py) maps '/_bytecode/EV00/EV00_0001_01.tatc' to
[offset, size] of its chunk; size includes the 6-byte RZ header. The arrays are
u32 or u16, whichever fitted when the file was written - the first seven are
u16, so those offsets cannot pass 65535.

Which chunk the game loads is the memfs offset, unless a patched exe redirects
it (see exehook.py): pass --exe and `list` shows where each read really lands.
A chunk no entry reaches is dead weight - the VI patch of 02/10 carries three,
the JP copies of the scripts it redirected.
"""
import argparse
import os
import sys
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rson    # noqa: E402
import kuv     # noqa: E402


def read_file(path):
    with open(path, 'rb') as f:
        return f.read()


class Chunk(object):
    def __init__(self, pos, length, raw):
        self.pos, self.length, self.raw = pos, length, raw

    @property
    def name(self):
        return kuv.name(self.raw)


def chunks(body):
    out = []; pos = 0
    while pos < len(body):
        if body[pos:pos + 2] != b'RZ':
            raise ValueError('no RZ chunk at %d' % pos)
        size = int.from_bytes(body[pos + 2:pos + 6], 'big')
        o = zlib.decompressobj()
        raw = o.decompress(body[pos + 6:])
        if not o.eof or len(raw) != size:
            raise ValueError('chunk at %d: bad zlib stream or size' % pos)
        n = len(body) - pos - len(o.unused_data)
        out.append(Chunk(pos, n, raw))
        pos += n
    return out


def rz(raw, level=9):
    return b'RZ' + len(raw).to_bytes(4, 'big') + zlib.compress(raw, level)


class Archive(object):
    """An opened memfs + membody pair."""

    def __init__(self, memfs_path=None, body_path=None, redirects=None, data=None):
        """From two files, or from data=(memfs bytes, membody bytes)."""
        if data is None:
            data = (read_file(memfs_path), read_file(body_path))
        self.memfs, self.body = data
        self.root = rson.parse(self.memfs)
        self.entries = rson.entries(self.root)
        self.chunks = chunks(self.body)
        self.at = dict((c.pos, i) for i, c in enumerate(self.chunks))
        self.redirects = redirects or {}

    def loaded(self, path):
        """Index of the chunk the game reads for path."""
        off, size = self.entries[path].vals
        off = self.redirects.get((off, size), off)
        if off not in self.at:
            raise ValueError('%s points at %d, which is not a chunk start' % (path, off))
        return self.at[off]

    def raw(self, path):
        return self.chunks[self.loaded(path)].raw

    def unreached(self):
        used = set(self.loaded(p) for p in self.entries)
        return [i for i in range(len(self.chunks)) if i not in used]


def script_name(path):
    """'/_bytecode/EV00/EV00_0001_01.tatc' -> 'EV00_0001_01.tat'."""
    base = path.rsplit('/', 1)[-1]
    return base[:-1] if base.endswith('.tatc') else base


def load_redirects(exe):
    if not exe:
        return {}
    import exehook
    return exehook.from_main(exe)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('cmd', choices=['list', 'unpack', 'check'])
    ap.add_argument('memfs')
    ap.add_argument('membody')
    ap.add_argument('out', nargs='?')
    ap.add_argument('--exe', help='patched exefs/main, to follow its read redirects')
    a = ap.parse_args()
    arc = Archive(a.memfs, a.membody, load_redirects(a.exe))
    if a.cmd == 'check':
        back = rson.write(arc.root)
        print('memfs: %s' % ('doc/ghi lai giong tung byte' if back == arc.memfs else 'KHONG KHOP'))
        print('membody: %d chunk, %d byte' % (len(arc.chunks), len(arc.body)))
        bad = 0
        for p, arr in arc.entries.items():
            i = arc.loaded(p); c = arc.chunks[i]
            if c.name and c.name != script_name(p):
                print('  %s doc vao chunk cua %s' % (p, c.name)); bad += 1
        dead = arc.unreached()
        if dead:
            print('  %d chunk khong muc nao tro toi: %s' % (len(dead), ', '.join(
                '%s@%d' % (arc.chunks[i].name, arc.chunks[i].pos) for i in dead)))
        return 1 if back != arc.memfs or bad else 0
    rows = sorted(arc.entries.items(), key=lambda kv: kv[1].vals[0])
    if a.cmd == 'list':
        for p, arr in rows:
            off, size = arr.vals
            i = arc.loaded(p)
            note = '' if arc.chunks[i].pos == off else '  -> doc tai %d (exe chuyen huong)' % arc.chunks[i].pos
            print('%-44s %s %9d %7d%s' % (p, 'u16' if arr.etype == 0x30 else 'u32', off, size, note))
        for i in arc.unreached():
            print('%-44s     %9d %7d  (khong muc nao tro toi)' % (
                '(%s)' % arc.chunks[i].name, arc.chunks[i].pos, arc.chunks[i].length))
        return 0
    if not a.out:
        raise SystemExit('unpack can thu muc ra')
    for p in arc.entries:
        rel = p.lstrip('/')
        dst = os.path.join(a.out, rel[:-1] if rel.endswith('.tatc') else rel)   # written decompressed
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, 'wb') as f:
            f.write(arc.raw(p))
    print('%d file -> %s' % (len(arc.entries), a.out))
    return 0


if __name__ == '__main__':
    sys.exit(main())
