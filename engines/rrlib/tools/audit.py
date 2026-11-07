# -*- coding: utf-8 -*-
"""audit.py - check a VI patch against the JP scripts, without changing anything.

    python audit.py --jp jp/romfs/common --patch <mod folder> [--csv issues.csv]

Per script, on the chunk the game loads (exe redirects followed):

  - the code is byte-identical to JP and the string count matches - code
    refers to strings by index, so a translation never needs to touch it
  - control tags lost against JP: #P (position; off-screen JP lines excluded),
    #T1/#T2 (both name variants shown at once), #KW (no wait mid-message)
  - #P tags that hide a translated line off-screen (y >= 1080)
  - the header's code-length field
  - chunks no entry reaches, and entries that only reach their script through
    an exe redirect

Exit status 1 when the structure is broken (code, string count, wrong chunk);
tag findings are reported but do not fail the run.
"""
import argparse
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kuv       # noqa: E402
import memfs     # noqa: E402
import tags      # noqa: E402
from patch import find_pair, find_exe   # noqa: E402


def audit(jp, vi):
    jp_by_name = dict((memfs.script_name(p), jp.raw(p)) for p in jp.entries)
    broken = []; rows = []; counts = {}

    def add(kind, nm, i, a, b):
        counts[kind] = counts.get(kind, 0) + 1
        rows.append((nm, i, kind, a, b))

    for p in sorted(vi.entries):
        k = vi.loaded(p)
        raw = vi.chunks[k].raw
        nm = kuv.name(raw)
        if nm is None:
            continue
        if nm != memfs.script_name(p):
            broken.append('%s doc vao chunk cua %s' % (p, nm)); continue
        if vi.chunks[k].pos != vi.entries[p].vals[0]:
            counts['chuyen huong qua exe'] = counts.get('chuyen huong qua exe', 0) + 1
        if not kuv.length_ok(raw):
            counts['do dai code sai o header'] = counts.get('do dai code sai o header', 0) + 1
        j = jp_by_name.get(nm)
        if j is None:
            broken.append('%s: khong co ban JP' % nm); continue
        if kuv.code(raw) != kuv.code(j):
            broken.append('%s: code khac JP' % nm)
        js, vs = kuv.parse(j)[1], kuv.parse(raw)[1]
        if len(js) != len(vs):
            broken.append('%s: %d chuoi, JP co %d' % (nm, len(vs), len(js))); continue
        for i, (a, b) in enumerate(zip(js, vs)):
            for kind in tags.losses(a, b):
                add('mat ' + kind, nm, i, a, b)
            pos = [(int(x), int(y)) for x, y in tags.P.findall(b)]
            if tags.all_offscreen(pos):
                add('#P an chu ngoai man hinh', nm, i, a, b)
    dead = vi.unreached()
    if dead:
        counts['chunk khong ai tro toi'] = len(dead)
    return broken, rows, counts


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--jp', required=True)
    ap.add_argument('--patch', required=True)
    ap.add_argument('--exe')
    ap.add_argument('--csv', help='every tag finding, with JP and VI text')
    a = ap.parse_args()
    exe = a.exe or find_exe(a.patch)
    jp = memfs.Archive(*find_pair(a.jp))
    vi = memfs.Archive(*find_pair(a.patch), redirects=memfs.load_redirects(exe))
    broken, rows, counts = audit(jp, vi)
    for line in broken:
        print('LOI: ' + line)
    for kind, n in sorted(counts.items()):
        print('%-28s %d' % (kind, n))
    if not broken:
        print('cau truc: OK (code giong JP, so chuoi khop, moi muc doc dung file)')
    if a.csv:
        with open(a.csv, 'w', newline='', encoding='utf-8-sig') as f:
            w = csv.writer(f)
            w.writerow(['script', 'index', 'issue', 'jp', 'vi'])
            w.writerows(rows)
        print('-> %s (%d dong)' % (a.csv, len(rows)))
    return 1 if broken else 0


if __name__ == '__main__':
    sys.exit(main())
