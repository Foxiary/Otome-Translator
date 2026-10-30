#!/usr/bin/env python3
"""What the replace-fonts page needs to know about stock .ffu files and source fonts.

Run from the project folder. Reads only the .ffu header and palette, so even the
~100 MB ADV fonts answer at once, and uses the generator's own charset and
palette check (tools/ffugen.py) so the page agrees with what ffugen will do.

    python font_info.py ffu <file.ffu>...      -> one JSON list, a row per file
    python font_info.py font <file[#face]>     -> Vietnamese coverage of one font
    python font_info.py fit <cell> <stroke> <file[#face]>
                                               -> the largest px that fits the cell
"""
import json
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.getcwd(), 'tools'))
from ffugen import VN_CHARS, Chain, measure, outline_palette, stroke_margin  # noqa: E402


def ffu_info(path):
    try:
        with open(path, 'rb') as fh:
            head = fh.read(0x28)
            if len(head) < 0x28 or struct.unpack_from('<H', head, 0)[0] != 0x4655:
                return {'path': path, 'error': 'not-ffu'}
            glyphs = struct.unpack_from('<H', head, 4)[0]
            cell = head[0x0A]
            range_off = struct.unpack_from('<I', head, 0x14)[0]
            # The first 16 palette entries; the ADV fonts hold only these.
            raw = fh.read(min(64, max(0, range_off - 0x28)))
    except OSError as error:
        return {'path': path, 'error': 'read', 'message': str(error)}
    palette = [tuple(raw[i:i + 4]) for i in range(0, len(raw) - 3, 4)]
    try:
        outline_palette(palette)
        outline = True
    except SystemExit:
        outline = False
    return {'path': path, 'glyphs': glyphs, 'cell': cell, 'outline': outline}


def font_info(spec):
    from fontTools.ttLib import TTFont
    path, _, face = spec.partition('#')
    try:
        font = TTFont(path, fontNumber=int(face or 0), lazy=True)
        cmap = font.getBestCmap() or {}
        name = font['name'].getDebugName(4) or font['name'].getDebugName(1) or os.path.basename(path)
    except Exception as error:  # fontTools raises many kinds for a file that is not a font
        return {'path': spec, 'error': 'not-font', 'message': str(error)}
    missing = [c for c in VN_CHARS if ord(c) not in cmap]
    return {'path': spec, 'name': name, 'total': len(VN_CHARS),
            'vn': len(VN_CHARS) - len(missing), 'missing': ''.join(missing)}


def fit_px(cell, stroke, spec):
    """The largest size at which every Vietnamese letter, outline included, fits
    the cell. ffugen's own auto-fit matches the template's cap height instead,
    which in a forced cell cuts the tone marks off capitals; every px in
    fonts.json is this number (Tinos 75, Source Serif 4 67, Open Sans 65,
    Newsreader 29)."""
    room = cell - 2 * stroke_margin(stroke)
    lo, hi, best = 4, cell * 2, None
    while lo <= hi:
        mid = (lo + hi) // 2
        top, bottom = measure(Chain([spec], mid), VN_CHARS)
        if bottom - top <= room:
            best, lo = mid, mid + 1
        else:
            hi = mid - 1
    return {'px': best}


def main():
    mode, files = sys.argv[1], sys.argv[2:]
    if mode == 'fit':
        result = fit_px(int(files[0]), float(files[1]), files[2])
    else:
        result = [ffu_info(f) for f in files] if mode == 'ffu' else font_info(files[0])
    # UTF-8 whatever the console's code page, so Vietnamese survives the pipe.
    sys.stdout.buffer.write((json.dumps(result, ensure_ascii=False) + '\n').encode('utf-8'))


if __name__ == '__main__':
    main()
