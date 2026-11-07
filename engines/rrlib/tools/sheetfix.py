# -*- coding: utf-8 -*-
"""sheetfix.py - a workbook of tag fixes to copy into the translation sheet.

    python sheetfix.py --sheet export.xlsx --jp jp/romfs/common --out fixes.xlsx

--sheet  the translation sheet downloaded as .xlsx: one tab per script, with
         columns record_id, command, script, const_index, jp_text, vi_text
--jp     folder with the JP script.memfs/membody

Output tabs:
  "#P - đề xuất"    vi_text with #P put back (tags.restore, as patch.py does);
                    a single-tag line keeps the translator's text and breaks
                    exactly, and only breaks the tool had to add are written
  "#P - KHÔNG thêm" lines JP draws off-screen on purpose: leave them untagged
  "#T - cần sửa tay", "#KW - cần sửa tay"   lost variants / waits, by hand

const_index is the KUV string index, so a row is matched to the game by it -
the JP text only confirms the match. The sheet writes a blank line where the
game has \\r\\n, so that comparison ignores line breaks. Two rows may point at
one game string; each gets its own proposal.

Needs openpyxl.
"""
import argparse
import collections
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kuv       # noqa: E402
import memfs     # noqa: E402
import tags      # noqa: E402
from patch import find_pair   # noqa: E402

NEED = ('script', 'const_index', 'jp_text', 'vi_text')


def read_sheet(path):
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True)
    rows = []
    for name in wb.sheetnames:
        it = wb[name].iter_rows(values_only=True)
        try:
            hdr = list(next(it))
        except StopIteration:
            continue
        ix = dict((h, i) for i, h in enumerate(hdr) if h)
        if not all(k in ix for k in NEED):
            continue
        for rn, r in enumerate(it, start=2):
            if r[ix['jp_text']] is None or r[ix['const_index']] is None:
                continue
            g = lambda k: r[ix[k]] if k in ix else None
            rows.append(dict(tab=name, row=rn, rid=g('record_id'), cmd=g('command'), script=g('script'),
                             ci=int(float(g('const_index'))), jp=str(g('jp_text')),
                             vi=None if g('vi_text') is None else str(g('vi_text'))))
    return rows


def render(new_s, vi, jp, x):
    """The sheet text for a restored string, and notes."""
    segs = re.split(r'\n(?=#P\()', new_s)
    out = []; explicit = False
    for sg in segs:
        m = re.match(r'(#P\(-?\d+,-?\d+\))(.*)', sg, re.S)
        tag, lines = m.group(1), m.group(2).split('\n')
        flat = ' '.join(l.strip() for l in lines)
        if len(segs) == 1 and '\n'.join(lines) == tags.builder_wrap(vi):
            out.append(tag + vi)
        elif len(segs) > 1 and tags.wrap(flat, tags.WRAP) == lines:
            out.append(tag + flat)
        else:
            out.append(tag + '\n'.join(lines)); explicit = True
    notes = []
    if x['how'] == 'multi':
        notes.append('Tách câu tự động' + (' - nên đọc lại chỗ tách' if x.get('cost', 0) > 0.3 else ''))
    moved = []
    for (_, y, _, _), o in zip(tags.merged(jp), out):
        ny = int(re.match(r'#P\(-?\d+,(-?\d+)\)', o).group(1))
        if ny != y:
            moved.append('y %d→%d' % (y, ny))
    if moved:
        notes.append('Dời vị trí vì bản dịch dài hơn JP: ' + ', '.join(moved))
    if explicit:
        notes.append('Có xuống dòng thủ công (x lớn, để tool tự ngắt ở %d ký tự sẽ tràn mép phải)' % tags.WRAP)
    if x.get('flag'):
        notes.append(x['flag'])
    return '\n'.join(out), notes


def proposals(rows, jp):
    jp_by_name = dict((memfs.script_name(p), jp.raw(p)) for p in jp.entries)
    key = lambda t: re.sub(r'[\r\n]', '', t).strip()
    by = collections.defaultdict(list)
    for r in rows:
        by[r['script']].append(r)
    props = []; offs = []; tkw = []; mismatch = []
    for script, rs in by.items():
        jd = jp_by_name.get(script)
        if jd is None:
            mismatch += rs; continue
        js = kuv.parse(jd)[1]
        v = list(js); first = {}
        for r in rs:
            if r['ci'] >= len(js) or key(js[r['ci']]) != key(r['jp']):
                mismatch.append(r); continue
            if r['vi'] is None:
                continue
            a, b = js[r['ci']], r['vi']
            if re.search(r'#T[12]', a) and not re.search(r'#T[12]', b):
                tkw.append(('#T', r))
            if a.count('#KW') > b.count('#KW'):
                tkw.append(('#KW', r))
            if tags.all_offscreen([(int(x), int(y)) for x, y in tags.P.findall(b)]):
                props.append(dict(r=r, prop=tags.P.sub('', b), strip=True,
                                  notes=['Bỏ tag: JP đặt câu ngoài màn hình, bản Việt cần hiện chữ']))
                continue
            first.setdefault(r['ci'], r)
            if first[r['ci']] is r:
                v[r['ci']] = tags.builder_wrap(r['vi'])
        lost = set(ci for ci, r in first.items() if tags.P.search(js[ci]) and not tags.P.search(r['vi']))
        new, rep = tags.restore(jd, v, only=lost)
        for x in rep:
            r = first[x['idx']]
            if x['how'] == 'offscreen':
                offs.append(r); continue
            if x['how'] == 'unsplittable':
                props.append(dict(r=r, prop=None, notes=['Không tự tách được, cần sửa tay'])); continue
            text, notes = render(new[x['idx']], r['vi'], js[x['idx']], x)
            props.append(dict(r=r, prop=text, notes=notes))
        # a game string two rows share: the second row on its own
        for r in rs:
            ci = r['ci']
            if ci not in first or first[ci] is r or not r['vi'] or r in mismatch:
                continue
            if not (tags.P.search(js[ci]) and not tags.P.search(r['vi'])):
                continue
            v2 = list(v); v2[ci] = tags.builder_wrap(r['vi'])
            new2, rep2 = tags.restore(jd, v2, only={ci})
            if not rep2 or rep2[0]['how'] == 'offscreen':
                offs.append(r); continue
            text, notes = render(new2[ci], r['vi'], js[ci], rep2[0])
            others = [o for o in rs if o['ci'] == ci and o is not r]
            notes.append('Cùng một câu game với dòng %s' % ', '.join(str(o['row']) for o in others))
            if any(o['vi'] != r['vi'] for o in others):
                notes.append('HAI DÒNG DỊCH KHÁC NHAU - tool build chỉ dùng được một bản')
            props.append(dict(r=r, prop=text, notes=notes))
    return props, offs, tkw, mismatch


def write_book(path, rows, props, offs, tkw):
    import openpyxl
    from openpyxl.styles import Alignment, Font, PatternFill
    order = dict((t, i) for i, t in enumerate(dict.fromkeys(r['tab'] for r in rows)))
    k = lambda r: (order[r['tab']], r['row'])
    props.sort(key=lambda p: k(p['r'])); offs.sort(key=k)
    review = lambda n: any(('đọc lại' in s) or ('KHÁC NHAU' in s) or ('thủ công' in s) or ('sửa tay' in s) for s in n)
    cnt = collections.Counter('Nên xem lại' if review(p['notes']) else 'Tự động' for p in props)
    nT = sum(1 for kk, _ in tkw if kk == '#T'); nK = sum(1 for kk, _ in tkw if kk == '#KW')
    wb = openpyxl.Workbook()
    H = Font(bold=True, color='FFFFFF'); HF = PatternFill('solid', fgColor='37474F')
    REV = PatternFill('solid', fgColor='FFF3CD'); wrapA = Alignment(wrap_text=True, vertical='top')

    def table(ws, header, data, widths, review_col=None):
        ws.append(header)
        for c in ws[1]:
            c.font = H; c.fill = HF; c.alignment = wrapA
        for row in data:
            ws.append(row)
        for i, w in enumerate(widths, 1):
            ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = w
        for row in ws.iter_rows(min_row=2):
            for c in row:
                c.alignment = wrapA
            if review_col is not None and row[review_col].value == 'Nên xem lại':
                for c in row:
                    c.fill = REV
        ws.freeze_panes = 'A2'; ws.auto_filter.ref = ws.dimensions

    ws = wb.active; ws.title = 'Hướng dẫn'
    for line in [
        ['Sửa tag điều khiển bị mất (so với kịch bản JP gốc)'], [],
        ['#P - đề xuất', '%d dòng mất tag vị trí #P(x,y). "vi_text đề xuất" là chữ đang có trong sheet, chỉ thêm tag (tách câu khi JP có nhiều tag). Chép đè vào vi_text đúng tab + dòng.' % len(props)],
        ['', 'Tự động: %d. Nên xem lại (tô vàng): %d - tách câu chưa chắc, có xuống dòng thủ công, hoặc một câu game dịch hai lần khác nhau.' % (cnt['Tự động'], cnt['Nên xem lại'])],
        ['', '"Dời vị trí": bản dịch nhiều dòng hơn JP nên y được đẩy đi để các câu trên cùng màn hình không đè nhau. x giữ như JP.'],
        ['#P - KHÔNG thêm', '%d dòng JP đặt ngoài màn hình (y=1200) vì câu đã vẽ trong tranh. Bản Việt để KHÔNG có #P để chữ dịch hiện ra.' % len(offs)],
        ['#T - cần sửa tay', '%d dòng mất #T1/#T2: game hiện cả hai cách gọi tên. Viết lại #T1<gọi Naya> #T2<gọi ${FirstName}> #T0<phần chung> theo cột JP.' % nT],
        ['#KW - cần sửa tay', '%d dòng mất #KW (dừng chờ bấm giữa câu). Chèn #KW vào chỗ tương ứng với JP.' % nK],
    ]:
        ws.append(line)
    ws.column_dimensions['A'].width = 20; ws.column_dimensions['B'].width = 120
    for row in ws.iter_rows():
        for c in row:
            c.alignment = wrapA
    ws['A1'].font = Font(bold=True, size=13)
    iv = lambda x: int(float(x)) if x is not None else None
    table(wb.create_sheet('#P - đề xuất'),
          ['Tab', 'Dòng', 'record_id', 'const_index', 'command', 'Mức', 'jp_text', 'vi_text hiện tại', 'vi_text đề xuất', 'Ghi chú'],
          [[p['r']['tab'], p['r']['row'], iv(p['r']['rid']), p['r']['ci'], p['r']['cmd'],
            'Nên xem lại' if review(p['notes']) else 'Tự động', p['r']['jp'], p['r']['vi'], p['prop'],
            '; '.join(p['notes'])] for p in props], [16, 7, 10, 8, 11, 12, 45, 55, 60, 40], review_col=5)
    table(wb.create_sheet('#P - KHÔNG thêm'), ['Tab', 'Dòng', 'record_id', 'const_index', 'jp_text', 'vi_text hiện tại'],
          [[r['tab'], r['row'], iv(r['rid']), r['ci'], r['jp'], r['vi']] for r in offs], [16, 7, 10, 8, 60, 70])
    for name, kind in (('#T - cần sửa tay', '#T'), ('#KW - cần sửa tay', '#KW')):
        table(wb.create_sheet(name), ['Tab', 'Dòng', 'record_id', 'const_index', 'jp_text', 'vi_text hiện tại'],
              [[r['tab'], r['row'], iv(r['rid']), r['ci'], r['jp'], r['vi']] for kk, r in tkw if kk == kind],
              [16, 7, 10, 8, 60, 70])
    wb.save(path)
    return cnt, nT, nK


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--sheet', required=True)
    ap.add_argument('--jp', required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    if os.path.abspath(a.out) == os.path.abspath(a.sheet):
        raise SystemExit('--out phai khac --sheet')
    rows = read_sheet(a.sheet)
    jp = memfs.Archive(*find_pair(a.jp))
    props, offs, tkw, mismatch = proposals(rows, jp)
    if mismatch:
        print('%d dong khong khop chuoi JP trong game (bo qua), vd. %s dong %s' % (
            len(mismatch), mismatch[0]['tab'], mismatch[0]['row']))
    cnt, nT, nK = write_book(a.out, rows, props, offs, tkw)
    print('#P de xuat %d (tu dong %d, nen xem %d), khong them %d, #T %d, #KW %d -> %s' % (
        len(props), cnt['Tự động'], cnt['Nên xem lại'], len(offs), nT, nK, a.out))
    return 0


if __name__ == '__main__':
    sys.exit(main())
