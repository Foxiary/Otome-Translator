# -*- coding: utf-8 -*-
"""patch.py - rebuild a VI script.memfs / script.membody with the tags fixed.

    python patch.py --jp jp/romfs/common --patch <mod folder> --out out/
    python patch.py --jp jp/romfs/common --patch <mod folder> --out out/ --apply

--jp     folder holding the JP script.memfs + script.membody (nsp.py romfs)
--patch  the VI mod folder (romfs/common/script.*, and exefs/main if any)
--out    where the new pair is written; an existing file is kept as .bak

Without --apply it builds, verifies and reports, and writes nothing.

What it does, per script, on the chunk the game actually loads (following
the read redirects of a patched exefs/main, see exehook.py):

  1. puts #P back where the translation lost it (tags.restore)
  2. leaves untagged, or untags, any string JP draws entirely off-screen
  3. rebuilds the KUV with the code copied verbatim and the true code length

Then the archive: chunks in their old order, unreached ones dropped, changed
ones recompressed (zlib 9), every memfs entry pointed straight at its chunk.
An u16 entry that no longer fits is widened to u32 and the RSON rewritten as a
whole. No entry may equal an exe redirect pair - the hook would move it.

The result is opened again and checked: every entry decompresses to a script
of the right name, with code identical to the JP script and the same string
count, and no #P lost except the off-screen ones.
"""
import argparse
import csv
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kuv       # noqa: E402
import memfs     # noqa: E402
import rson      # noqa: E402
import tags      # noqa: E402


def find_pair(folder):
    for sub in ('', 'romfs/common', 'common'):
        d = os.path.join(folder, sub)
        m, b = os.path.join(d, 'script.memfs'), os.path.join(d, 'script.membody')
        if os.path.isfile(m) and os.path.isfile(b):
            return m, b
    raise SystemExit('khong thay script.memfs + script.membody trong %s' % folder)


def find_exe(folder):
    p = os.path.join(folder, 'exefs', 'main')
    return p if os.path.isfile(p) else None


def build(jp, vi, restore=True, untag_offscreen=True, edit=None):
    """jp, vi: memfs.Archive. -> (membody, memfs, report dict).

    edit(script name, strings) -> strings, if given, changes a script's strings
    before #P is put back (applysheet.py writes the sheet in through it)."""
    jp_by_name = dict((memfs.script_name(p), jp.raw(p)) for p in jp.entries)
    use = dict((p, vi.loaded(p)) for p in vi.entries)
    rep = dict(rows=[], stripped=[], length_fixed=[], repointed=[], widened=[])
    for p, k in use.items():
        if vi.chunks[k].pos != vi.entries[p].vals[0]:
            rep['repointed'].append((p, vi.entries[p].vals[0], vi.chunks[k].pos))
    new_raw = {}
    for k in sorted(set(use.values())):
        raw = vi.chunks[k].raw
        nm = kuv.name(raw)
        if not nm:
            continue
        _, strs, _ = kuv.parse(raw)
        if edit:
            strs = edit(nm, strs)
        if restore and nm in jp_by_name:
            strs, rows = tags.restore(jp_by_name[nm], strs)
            rep['rows'] += [dict(r, script=nm) for r in rows]
        if untag_offscreen:
            strs, changed = tags.strip_offscreen(strs)
            rep['stripped'] += [(nm, i) for i in changed]
        if not kuv.length_ok(raw):
            rep['length_fixed'].append(nm)
        nr = kuv.build(raw, strs)
        if nr != raw:
            new_raw[k] = nr
    body = bytearray(); where = {}
    for k, c in enumerate(vi.chunks):
        if k not in use.values():
            continue
        blob = memfs.rz(new_raw[k]) if k in new_raw else vi.body[c.pos:c.pos + c.length]
        where[k] = (len(body), len(blob))
        body += blob
    root = rson.parse(vi.memfs)
    ents = rson.entries(root)
    for p, arr in ents.items():
        off, size = where[use[p]]
        if arr.etype == 0x30 and (off > 0xFFFF or size > 0xFFFF):
            arr.etype = 0x20; rep['widened'].append(p)
        arr.vals = [off, size]
        if (off, size) in vi.redirects:
            raise SystemExit('%s se trung cap (%d, %d) ma exe chuyen huong - dung lai' % (p, off, size))
    rep['recompressed'] = len(new_raw)
    rep['dropped'] = [(vi.chunks[i].name, vi.chunks[i].pos) for i in vi.unreached()]
    return bytes(body), rson.write(root), rep


def verify(body, mem, jp, redirects):
    """Open the built pair from bytes and check it. -> list of problems."""
    out = memfs.Archive(redirects=redirects, data=(mem, body))
    problems = []
    if rson.write(out.root) != mem:
        problems.append('memfs does not round-trip')
    jp_by_name = dict((memfs.script_name(p), jp.raw(p)) for p in jp.entries)
    lost = 0
    for p in out.entries:
        raw = out.raw(p)
        nm = kuv.name(raw)
        if nm is None:
            continue
        if nm != memfs.script_name(p):
            problems.append('%s loads %s' % (p, nm)); continue
        if not kuv.length_ok(raw):
            problems.append('%s: code length field wrong' % nm)
        j = jp_by_name.get(nm)
        if j is None:
            continue
        if kuv.code(raw) != kuv.code(j):
            problems.append('%s: code differs from JP' % nm)
        js, vs = kuv.parse(j)[1], kuv.parse(raw)[1]
        if len(js) != len(vs):
            problems.append('%s: %d strings, JP has %d' % (nm, len(vs), len(js)))
        lost += sum(1 for a, b in zip(js, vs) if '#P' in tags.losses(a, b))
    if lost:
        problems.append('%d strings still lose #P' % lost)
    if out.unreached():
        problems.append('%d chunks unreached' % len(out.unreached()))
    return problems


def write_report(path, rows):
    with open(path, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f)
        w.writerow(['script', 'index', 'how', 'split cost', 'moved', 'wide wrap', 'flag'])
        for r in rows:
            w.writerow([r['script'], r['idx'], r['how'], '%.2f' % r.get('cost', 0),
                        'x' if r.get('shifted') else '', 'x' if r.get('wide') else '', r.get('flag', '')])


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--jp', required=True, help='folder with the JP script.memfs/membody')
    ap.add_argument('--patch', required=True, help='VI mod folder')
    ap.add_argument('--out', required=True, help='output folder')
    ap.add_argument('--exe', help='patched exefs/main (default: <patch>/exefs/main if present)')
    ap.add_argument('--no-restore', action='store_true', help='only rebuild, do not touch #P')
    ap.add_argument('--keep-offscreen', action='store_true', help='keep off-screen #P tags')
    ap.add_argument('--report', help='CSV of every string touched')
    ap.add_argument('--apply', action='store_true', help='write the files')
    a = ap.parse_args()

    exe = a.exe or find_exe(a.patch)
    redirects = memfs.load_redirects(exe)
    jp = memfs.Archive(*find_pair(a.jp))
    vi = memfs.Archive(*find_pair(a.patch), redirects=redirects)
    print('exe: %s, %d doan chuyen huong' % (exe or 'khong co', len(redirects)))

    body, mem, rep = build(jp, vi, not a.no_restore, not a.keep_offscreen)
    hows = {}
    for r in rep['rows']:
        hows[r['how']] = hows.get(r['how'], 0) + 1
    print('tra #P: %s' % (', '.join('%s %d' % kv for kv in sorted(hows.items())) or '0'))
    print('  doi y vi ban dich dai hon: %d, ngat dong rong: %d, can xem: %d' % (
        sum(1 for r in rep['rows'] if r.get('shifted')), sum(1 for r in rep['rows'] if r.get('wide')),
        sum(1 for r in rep['rows'] if r.get('flag'))))
    print('bo tag ngoai man hinh: %d' % len(rep['stripped']))
    print('sua do dai code o header: %d file' % len(rep['length_fixed']))
    for p, old, new in rep['repointed']:
        print('tro thang %s: %d -> chunk o %d' % (p, old, new))
    print('noi rong u16 -> u32: %s' % (', '.join(rep['widened']) or 'khong'))
    print('chunk bo di (khong ai tro toi): %d; chunk nen lai: %d' % (len(rep['dropped']), rep['recompressed']))
    print('membody %d -> %d byte, memfs %d -> %d byte' % (len(vi.body), len(body), len(vi.memfs), len(mem)))

    problems = verify(body, mem, jp, redirects)
    if problems:
        print('KIEM TRA LOI:'); [print('  ' + x) for x in problems]
        return 1
    print('kiem tra: OK (code giong JP, so chuoi khop, khong con #P mat ngoai cac cau ngoai man hinh)')
    if a.report:
        write_report(a.report, rep['rows'])
        print('bao cao -> %s' % a.report)
    if not a.apply:
        print('chay thu - them --apply de ghi vao %s' % a.out)
        return 0
    write_files(a.out, (('script.membody', body), ('script.memfs', mem)))
    return 0


def write_files(folder, files):
    """Write (name, bytes) pairs into folder; a file already there is kept as .bak."""
    os.makedirs(folder, exist_ok=True)
    for name, data in files:
        dst = os.path.join(folder, name)
        if os.path.exists(dst):
            bak = dst + '.bak'; n = 2
            while os.path.exists(bak):
                bak = '%s.bak%d' % (dst, n); n += 1
            shutil.copy2(dst, bak)
        with open(dst, 'wb') as f:
            f.write(data)
        print('-> %s' % dst)


if __name__ == '__main__':
    sys.exit(main())
