#!/usr/bin/env python3
"""Tests for engines/rrlib/tools/font.py on synthetic fonts - no game data needed.

The glyph-drawing tests need a TrueType font with Vietnamese letters; they look
for a common system one and are skipped when there is none."""
import contextlib
import io
import json
import os
import shutil
import struct
import sys
import tempfile
import unittest
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'engines', 'rrlib', 'tools'))

import font  # noqa: E402

try:
    from PIL import Image, ImageDraw
    HAVE_PIL = True
except ImportError:
    HAVE_PIL = False

TTF = next((p for p in (
    '/System/Library/Fonts/Supplemental/Arial.ttf',
    '/Library/Fonts/Arial Unicode.ttf',
    'C:/Windows/Fonts/arial.ttf',
    '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
    '/usr/share/fonts/TTF/DejaVuSans.ttf') if os.path.isfile(p)), None)


def mk(pairs):
    m = font.Map()
    for k, v in pairs:
        m.insert(k, v)
    return m


def rtex(raw, size):
    pay = b'RZ' + len(raw).to_bytes(4, 'big') + zlib.compress(bytes(raw))
    head = b'RTEX' + struct.pack('<I4H4I', 0, size, size, size, size, 0x20, len(pay), font.BC3_FLAGS, size)
    return head + pay


def draw_h(cell):
    """A blocky 'H', cap 32 px on baseline 53 with the pen at x 8, like the JP fonts."""
    d = ImageDraw.Draw(cell)
    d.rectangle((10, 21, 14, 52), fill=255)
    d.rectangle((27, 21, 31, 52), fill=255)
    d.rectangle((10, 35, 31, 38), fill=255)
    return cell


def make_font(chars, size=1024, outline=0):
    """A one-texture rrlib/rfnt2 font with `chars`; H and 漢 carry ink."""
    rows = size // 64
    tex = font.Texture(rtex(bytearray(font.EMPTY_BLOCK * (size * size // 16)), size))
    glyphs = []
    for i, ch in enumerate(chars):
        x, y = (i // rows) * 62, (i % rows) * 64
        glyphs.append(font.IntArr([0, x, y, 60, 62, 40 if ord(ch) > 0x3000 else 27, 0, 7]))
        if ch in 'H漢':
            a = Image.new('L', (60, 62), 0)
            draw_h(a) if ch == 'H' else ImageDraw.Draw(a).rectangle((12, 20, 44, 52), fill=200)
            if outline:
                a = font.widen(a, outline, 1.0)
            tex.write(x, y, a, font.mask(a))
    base = mk([('textureHeight', size), ('paddingBottom', 8), ('packMarginY', 1), ('packMarginX', 1),
               ('renderMarginY', 22), ('paddingRight', 0), ('offsetY', -19), ('offsetX', -8),
               ('textureCount', 1), ('renderMarginX', 20), ('textureWidth', size), ('charWidth', 40),
               ('rgb', 'FFFFFF'), ('bTrimGryph', False), ('charaCount', len(chars)), ('charHeight', 40)])
    info = mk([('baseInfo', base), ('gryphInfo', glyphs), ('@fileType', 'rrlib/rfnt2'),
               ('charToIndex', mk([(ch, i) for i, ch in enumerate(chars)])), ('@version', 100)])
    root = mk([('alignBytes', 4), ('bin', [tex.to_blob(), font.write(info)]), ('hasSeparateBody', False),
               ('path', mk([('/fontdata.00.rtex', 0), ('/fontdata.rson', 1)])),
               ('@fileType', 'rrlib/memfs'), ('@version', 102)])
    return font.write(root)


def quiet(fn, *args):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        rc = fn(*args)
    return rc, out.getvalue()


class RsonTest(unittest.TestCase):
    def test_int_encodings_found_in_the_game(self):
        self.assertEqual(font._int_bytes(4), b'\x47')          # alignBytes
        self.assertEqual(font._int_bytes(2), b'\x43')          # /fontdata.02.rtex
        self.assertEqual(font._int_bytes(-19), b'\x4f\xed')    # offsetY
        self.assertEqual(font._int_bytes(2048), b'\x50\x08\x00')
        for v in (0, 1, -1, 3, -3, 4, 5, -4, 1023, 1024, -1024, -1025, 4582, 262143, 262144, -300000):
            self.assertEqual(font.parse(font.write(mk([('v', v)])))['v'], v)

    def test_key_hash_is_crc16_ccitt_of_utf16(self):
        self.assertEqual(font.key_hash('alignBytes'), 4064)
        self.assertEqual(font.key_hash('bin'), 22728)
        self.assertEqual(font.key_hash('paddingBottom'), 4064)   # a real collision in baseInfo

    def test_lengths_and_node_offsets(self):
        self.assertEqual(font._size_head(0x88 & 0xe0, 6), b'\x88\x06')   # 'bin': never the 1-byte form
        self.assertEqual(font._size_head(0xa0, 0x613ff), b'\xb6\x13\xff')
        big = font.write(mk([('a', [b'x' * 70000, 'y'])]))
        p = big.index(b'\xc8\x02')
        self.assertEqual(big[p + 2], 2)            # 3-byte offsets ...
        target = p - int.from_bytes(big[p + 3:p + 6], 'big')      # ... big-endian
        self.assertEqual(big[target] & 0xe0, 0xa0)
        small = font.write(mk([('a', [b'x' * 300, 'y'])]))
        p = small.index(b'\xc8\x02')
        self.assertEqual(small[p + 2], 1)          # 2-byte offsets, little-endian
        self.assertEqual(small[p - int.from_bytes(small[p + 3:p + 5], 'little')] & 0xe0, 0xa0)
        self.assertEqual(font.parse(big)['a'][1], 'y')

    def test_typed_arrays_keep_negatives(self):
        back = font.parse(font.write(mk([('g', font.IntArr([7, 62, 1280, 60, 62, 40, -3 & 0xffffffff, 10]))])))
        self.assertEqual(font._s32(back['g'].vals[6]), -3)

    def test_insert_keeps_hash_order(self):
        m = mk([(c, i) for i, c in enumerate('漢字あいう')])
        m.insert('Ể', 99)
        hs = [font.key_hash(k) for k in m.keys()]
        self.assertEqual(hs, sorted(hs))
        self.assertEqual(font.parse(font.write(m))['Ể'], 99)


class BC3Test(unittest.TestCase):
    def test_nothing_is_the_jp_empty_block(self):
        self.assertEqual(font.encode_block([0] * 16, [0] * 16), font.EMPTY_BLOCK)
        self.assertEqual(font.decode_block(font.EMPTY_BLOCK), ([0] * 16, [0] * 16))

    def test_edges_survive(self):
        alpha = [0, 0, 36, 244, 255, 255, 206, 24, 0, 0, 0, 120, 255, 255, 255, 60]
        gray = [0, 255, 255, 255, 255, 255, 255, 255, 0, 0, 255, 255, 255, 255, 255, 255]
        a, g = font.decode_block(font.encode_block(alpha, gray))
        self.assertLessEqual(max(abs(x - y) for x, y in zip(a, alpha)), 20)
        self.assertEqual(g, gray)


@unittest.skipUnless(HAVE_PIL, 'needs Pillow')
class FontFileTest(unittest.TestCase):
    def setUp(self):
        self.data = make_font(' AH漢あいるろ')
        self.f = font.Font(self.data, 'standard.font.memfs')

    def test_round_trip(self):
        self.assertEqual(self.f.to_bytes(), self.data)

    def test_metrics_from_the_template(self):
        m = font.Metrics(self.f)
        self.assertEqual((m.cap, m.baseline, m.origin), (32, 53, 8))

    def test_free_slot_follows_the_grid(self):
        t, x, y = self.f.free_slot()
        self.assertEqual((t, x % 62, y % 64), (0, 0, 0))
        self.assertNotIn((x, y), [(g.x, g.y) for g in self.f.glyphs])

    def test_clean_map_keeps_the_small_letter_on_a_shared_code(self):
        m, dropped = font.clean_map({'Ể': 'ろ', 'ể': 'ろ', 'ệ': 'る'})
        self.assertEqual(m, {'ể': 'ろ', 'ệ': 'る'})
        self.assertEqual(dropped, ['Ể'])


@unittest.skipUnless(HAVE_PIL and TTF, 'needs Pillow and a TrueType font with Vietnamese')
class GenTest(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.jp = os.path.join(self.d, 'jp')
        os.makedirs(self.jp)
        chars = ' AH漢あいるろ'
        with open(os.path.join(self.jp, 'standard.font.memfs'), 'wb') as f:
            f.write(make_font(chars))
        with open(os.path.join(self.jp, 'standard_outline.font.memfs'), 'wb') as f:
            f.write(make_font(chars, outline=3.0))
        self.map = os.path.join(self.d, 'map.json')
        with open(self.map, 'w', encoding='utf-8') as f:
            json.dump({'ệ': 'る', 'ể': 'ろ', 'Ể': 'ろ'}, f, ensure_ascii=False)

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def gen(self, *extra):
        out = os.path.join(self.d, 'out')
        args = ['gen', '--template', self.jp, '--out', out, '--font', TTF, '--map', self.map,
                '--map-out', os.path.join(self.d, 'map-out.json')] + list(extra)
        old = sys.argv
        sys.argv = ['font.py'] + args
        try:
            rc, log = quiet(font.main)
        finally:
            sys.argv = old
        return rc, log, out

    def test_dry_run_writes_no_font(self):
        rc, log, out = self.gen()
        self.assertEqual(rc, 0)
        self.assertIn('chay thu', log)
        self.assertFalse(os.path.exists(os.path.join(out, 'standard.font.memfs')))

    def test_draws_on_mapped_codes_and_adds_the_rest(self):
        rc, log, out = self.gen('--apply')
        self.assertEqual(rc, 0, log)
        jp = font.Font.load(os.path.join(self.jp, 'standard.font.memfs'))
        new = font.Font.load(os.path.join(out, 'standard.font.memfs'))
        # ệ is drawn into る's cell, which keeps its glyph number
        self.assertEqual(new.char_index['る'], jp.char_index['る'])
        self.assertNotEqual(new.cell(new.glyph('る'))[0].tobytes(), jp.cell(jp.glyph('る'))[0].tobytes())
        # 漢 and あ are not touched, to the byte
        for ch in '漢あ':
            g = jp.glyph(ch)
            self.assertEqual(new.cell(new.glyph(ch)), jp.cell(g))
        # Ể shared ろ with ể: it gets its own code, and so does every letter the map lacks
        self.assertIsNotNone(new.glyph('Ể'))
        self.assertIsNotNone(new.glyph('ạ'))
        self.assertEqual(new.base['charaCount'], len(new.glyphs))
        with open(os.path.join(self.d, 'map-out.json'), encoding='utf-8') as f:
            m = json.load(f)
        self.assertEqual((m['ệ'], m['ể'], m['Ể'], m['ạ']), ('る', 'ろ', 'Ể', 'ạ'))
        self.assertNotIn('る', m)
        # the outline font gets the same new cells, widened by the measured radius
        ol = font.Font.load(os.path.join(out, 'standard_outline.font.memfs'))
        self.assertEqual([g.vals() for g in ol.glyphs], [g.vals() for g in new.glyphs])
        self.assertIn('vien 3.', log)
        a_main = new.cell(new.glyph('Ể'))[0].getbbox()
        a_ol = ol.cell(ol.glyph('Ể'))[0].getbbox()
        self.assertLess(a_ol[0], a_main[0])
        self.assertGreater(a_ol[2], a_main[2])

    def test_size_for_one_font_only(self):
        rc, log, _ = self.gen('--px-standard', '30')
        self.assertEqual(rc, 0, log)
        self.assertIn('30 px (dat tay; vua chu H', log)
        self.assertNotIn('CANH BAO', log)
        rc, log, _ = self.gen('--px-extra', '30')          # no extra here: standard keeps the fitted size
        self.assertIn('(vua chu H)', log)
        self.assertNotIn('dat tay', log)

    def test_warns_without_a_map(self):
        out = os.path.join(self.d, 'out')
        old = sys.argv
        sys.argv = ['font.py', 'gen', '--template', self.jp, '--out', out, '--font', TTF]
        try:
            rc, log = quiet(font.main)
        finally:
            sys.argv = old
        self.assertEqual(rc, 0)
        self.assertIn('CANH BAO: khong co --map', log)

    def test_second_run_keeps_a_backup(self):
        self.gen('--apply')
        rc, log, out = self.gen('--apply')
        self.assertEqual(rc, 0)
        self.assertTrue(os.path.exists(os.path.join(out, 'standard.font.memfs.bak')))

    def test_preview_draws_a_line(self):
        _, _, out = self.gen('--apply')
        png = os.path.join(self.d, 'p.png')
        old = sys.argv
        sys.argv = ['font.py', 'preview', os.path.join(out, 'standard.font.memfs'), 'Hệ Ể', png,
                    '--outline', os.path.join(out, 'standard_outline.font.memfs'),
                    '--map', os.path.join(self.d, 'map-out.json')]
        try:
            rc, log = quiet(font.main)
        finally:
            sys.argv = old
        self.assertEqual(rc, 0)
        self.assertNotIn('khong co', log)
        with Image.open(png) as im:
            self.assertGreater(im.width, 60)

    def preview(self, *args):
        old = sys.argv
        sys.argv = ['font.py', 'preview'] + list(args)
        try:
            return quiet(font.main)
        finally:
            sys.argv = old

    def test_preview_of_a_folder_stacks_the_four_settings_fonts(self):
        _, _, out = self.gen('--apply')
        one, four = os.path.join(self.d, 'one.png'), os.path.join(self.d, 'four.png')
        rc, _ = self.preview(os.path.join(out, 'standard.font.memfs'), 'Hệ', one,
                             '--outline', os.path.join(out, 'standard_outline.font.memfs'),
                             '--map', os.path.join(self.d, 'map-out.json'))
        self.assertEqual(rc, 0)
        # The same font under the four names the settings screen uses.
        for n in font.SETTINGS[1:]:
            for suffix in ('', '_outline'):
                shutil.copy(os.path.join(out, 'standard%s.font.memfs' % suffix),
                            os.path.join(out, '%s%s.font.memfs' % (n, suffix)))
        rc, log = self.preview(out, 'Hệ', four, '--map', os.path.join(self.d, 'map-out.json'))
        self.assertEqual(rc, 0)
        self.assertIn('standard 一, extra 二, extra2 三, extra3 四', log)
        with Image.open(one) as a, Image.open(four) as b:
            self.assertEqual(b.size, (a.width, 4 * a.height + 3 * font.PREVIEW_GAP))
            # each block is the single-font image, outline included
            block = b.crop((0, a.height + font.PREVIEW_GAP, a.width, 2 * a.height + font.PREVIEW_GAP))
            self.assertEqual(block.tobytes(), a.convert('RGBA').tobytes())

    def test_preview_of_a_folder_names_what_is_missing(self):
        _, _, out = self.gen('--apply')
        png = os.path.join(self.d, 'p.png')
        rc, log = self.preview(out, 'Hệ', png)
        self.assertEqual(rc, 0)
        self.assertIn('khong thay extra.font.memfs', log)
        self.assertIn('standard khong co: ệ', log)       # no map: ệ is only on its kana code
        self.assertIn('--map', log)
        empty = os.path.join(self.d, 'empty')
        os.makedirs(empty)
        rc, log = self.preview(empty, 'x', png)
        self.assertEqual(rc, 1)
        self.assertIn('LOI', log)


if __name__ == '__main__':
    unittest.main(verbosity=1)
