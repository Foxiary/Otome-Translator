#!/usr/bin/env python3
"""Tests for engines/rrlib/tools on synthetic files - no game data needed."""
import contextlib
import csv
import io
import json
import os
import struct
import sys
import tempfile
import unittest
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'engines', 'rrlib', 'tools'))

import applysheet  # noqa: E402
import exehook  # noqa: E402
import exetext  # noqa: E402
import kuv      # noqa: E402
import memfs    # noqa: E402
import patch    # noqa: E402
import rson     # noqa: E402
import sprite   # noqa: E402
import tags     # noqa: E402

try:
    import PIL  # noqa: F401
    HAVE_PIL = True
except ImportError:
    HAVE_PIL = False


def push(i):
    return b'\x0e' + i.to_bytes(4, 'big')


def call(argc):
    return b'\x2b\x2c' + bytes([argc, 0])


def make_kuv(name, strings, code, header_bad_length=False):
    """A minimal KUV script laid out like the game's."""
    n = len(strings)
    tab = 0xc4
    pool = tab + 8 * n
    body = bytearray(); table = bytearray()
    for s in strings:
        b = s.encode('utf-16le')
        table += struct.pack('<2I', len(body), len(b))
        body += b + b'\0\0'
    pad, section = 0x10, b'\0' * 0x20
    end = pool + len(body) + pad
    h = [0xc0deabc1, struct.unpack('<I', b'KUV ')[0], 0x64, 0xc4, n, 0, 1, 0, 0, 0,
         tab, pool, pool, pool, pool, pool, pool, end, end + len(section), len(code)]
    if header_bad_length:
        h[19] += 1234
    head = bytearray(0xc4)
    struct.pack_into('<20I', head, 0, *h)
    nm = name.encode('utf-16le'); head[0x60:0x60 + len(nm)] = nm
    return bytes(head + table + body + b'\0' * pad + section + code)


def script(name, texts):
    """GuideMess each text, KW after each, WinClear at the end."""
    strs = ['', 'GuideMess', 'KW', 'WinClear'] + texts
    code = b''
    for i in range(len(texts)):
        code += push(4 + i) + push(1) + call(1) + push(2) + call(0)
    code += push(3) + call(0)
    return make_kuv(name, strs, code), strs


class KuvTest(unittest.TestCase):
    def test_round_trip_and_growth(self):
        raw, strs = script('EV.tat', ['あ', 'い'])
        self.assertEqual(kuv.build(raw, kuv.parse(raw)[1]), raw)
        longer = list(strs); longer[4] = 'Một câu dài hơn nhiều'
        out = kuv.build(raw, longer)
        self.assertEqual(kuv.parse(out)[1], longer)
        self.assertEqual(kuv.code(out), kuv.code(raw))
        self.assertTrue(kuv.length_ok(out))
        self.assertEqual(kuv.name(out), 'EV.tat')

    def test_bad_length_field_is_rewritten(self):
        raw, strs = script('EV.tat', ['あ'])
        bad = make_kuv('EV.tat', strs, kuv.code(raw), header_bad_length=True)
        self.assertFalse(kuv.length_ok(bad))
        self.assertTrue(kuv.length_ok(kuv.build(bad, strs)))

    def test_calls(self):
        raw, strs = script('EV.tat', ['a', 'b'])
        cl = [(f, a) for f, a, _ in kuv.calls(raw)]
        self.assertEqual(cl, [('GuideMess', [4]), ('KW', []), ('GuideMess', [5]), ('KW', []), ('WinClear', [])])


def sample_rson():
    files = rson.Map([(rson.Str('/_bytecode/a.tatc'), rson.Arr(0x30, [0, 100])),
                      (rson.Str('/_bytecode/b.tatc'), rson.Arr(0x20, [100, 200]))], (10, 20), 0)
    return rson.Map([(rson.Str('alignBytes'), rson.Raw(b'\x41')), (rson.Str('path'), files),
                     (rson.Str('@fileType'), rson.Str('rrlib/memfs'))], (1, 2, 3), 0)


class RsonTest(unittest.TestCase):
    def test_round_trip(self):
        data = rson.write(sample_rson())
        self.assertEqual(rson.write(rson.parse(data)), data)
        e = rson.entries(rson.parse(data))
        self.assertEqual(e['/_bytecode/a.tatc'].vals, [0, 100])
        self.assertEqual(e['/_bytecode/a.tatc'].etype, 0x30)

    def test_widen_by_rewriting(self):
        root = rson.parse(rson.write(sample_rson()))
        a = rson.entries(root)['/_bytecode/a.tatc']
        a.etype, a.vals = 0x20, [70000, 100]
        back = rson.entries(rson.parse(rson.write(root)))
        self.assertEqual(back['/_bytecode/a.tatc'].vals, [70000, 100])
        self.assertEqual(back['/_bytecode/b.tatc'].vals, [100, 200])

    def test_widen_in_place_breaks_the_file(self):
        # what an in-place patch does: grow the u16 entry to u32, fix only the size field
        data = bytearray(rson.write(sample_rson()))
        i = data.find(b'\xc8\x02\x30')
        data[i:i + 7] = b'\xc8\x02\x20' + struct.pack('<II', 70000, 100)
        struct.pack_into('<I', data, 4, len(data))
        try:
            e = rson.entries(rson.parse(bytes(data)))
            self.assertNotEqual(sorted(e), ['/_bytecode/a.tatc', '/_bytecode/b.tatc'])
        except (ValueError, KeyError, UnicodeDecodeError, struct.error, IndexError):
            pass                                    # or it does not parse at all


class ExeHookTest(unittest.TestCase):
    def test_finds_redirect(self):
        A, S, B = 9232, 19937, 2562405
        words = [0xd503201f] * 3 + [
            0x52800010 | (A << 5), 0x6b10007f, 0x54000101,
            0x52800010 | (S << 5), 0x6b10005f, 0x54000040, 0x14000005,
            0x52800003 | ((B & 0xffff) << 5), 0x72a00003 | ((B >> 16) << 5), 0x52800002 | (S << 5),
        ] + [0xd503201f] * 4
        self.assertEqual(exehook.redirects(struct.pack('<%dI' % len(words), *words)), {(A, S): B})

    def test_plain_code_has_none(self):
        self.assertEqual(exehook.redirects(b'\x1f\x20\x03\xd5' * 64), {})


class TagsTest(unittest.TestCase):
    def restore(self, jp_texts, vi_texts):
        jraw, jstrs = script('EV.tat', jp_texts)
        vstrs = list(jstrs[:4]) + vi_texts
        return tags.restore(jraw, vstrs)

    def test_stacks_longer_translation(self):
        new, rep = self.restore(['#P(500,130)一行', '#P(500,280)二行'],
                                ['dòng 1\ndòng 2\ndòng 3', 'câu sau'])
        self.assertTrue(new[4].startswith('#P(500,130)'))
        # JP left 150 px for one line: pitch clamps to 80, three VI lines need 240
        self.assertTrue(new[5].startswith('#P(500,370)'), new[5])
        self.assertTrue(any(r['shifted'] for r in rep))

    def test_offscreen_stays_untagged(self):
        new, rep = self.restore(['#P(520,1200)「天地」'], ['Trời đất'])
        self.assertEqual(new[4], 'Trời đất')
        self.assertEqual(rep[0]['how'], 'offscreen')

    def test_hand_wrapped_paragraph_is_one_block(self):
        new, rep = self.restore(['#P(230,780)この日、私は\n#P(230,840)舞っていた。'],
                                ['Ngày hôm ấy, tôi múa.'])
        self.assertEqual(new[4], '#P(230,780)Ngày hôm ấy, tôi múa.')
        self.assertEqual(rep[0]['how'], 'single')

    def test_split_at_sentences(self):
        new, rep = self.restore(['#P(660,420)さあ、ご覧あれ！\n#P(540,490)奇妙な言い伝え。'],
                                ['Xin mời xem! Một truyền thuyết lạ.'])
        self.assertEqual(new[4], '#P(660,420)Xin mời xem!\n#P(540,490)Một truyền thuyết lạ.')
        self.assertEqual(rep[0]['how'], 'multi')

    def test_strip_offscreen_and_losses(self):
        out, changed = tags.strip_offscreen(['#P(440,1200)Ẩn', '#P(500,130)Hiện', 'x'])
        self.assertEqual(out, ['Ẩn', '#P(500,130)Hiện', 'x'])
        self.assertEqual(changed, [0])
        self.assertEqual(tags.losses('#T1A#T2B#T0C', 'A B C'), ['#T'])
        self.assertEqual(tags.losses('#P(520,1200)x', 'x'), [])


def write_pair(folder, chunk_raws, table):
    """script.membody from chunk_raws, script.memfs from [(path, etype, [off, size])]."""
    os.makedirs(folder)
    body = b''.join(memfs.rz(c) for c in chunk_raws)
    files = rson.Map([(rson.Str(p), rson.Arr(t, v)) for p, t, v in table], tuple(range(len(table))), 0)
    with open(os.path.join(folder, 'script.membody'), 'wb') as f:
        f.write(body)
    with open(os.path.join(folder, 'script.memfs'), 'wb') as f:
        f.write(rson.write(rson.Map([(rson.Str('path'), files)], (7,), 0)))


class PatchTest(unittest.TestCase):
    """The 02/10 layout in miniature: B's memfs entry is u16 and points at a stale
    JP copy with the new size; an exe redirect sends that read to the copy
    appended past 65535."""

    def test_rebuild_follows_redirect_and_widens(self):
        import random
        import shutil
        rnd = random.Random(1)
        big = ''.join(chr(rnd.randrange(0x4e00, 0x9fff)) for _ in range(40000))   # does not compress
        jp_a, _ = script('A.tat', ['#P(500,130)一'])
        jp_c, _ = script('C.tat', ['三'])
        jp_b, _ = script('B.tat', ['二'])
        vi_a, _ = script('A.tat', ['một'])
        vi_c, _ = script('C.tat', [big])
        vi_b_new, _ = script('B.tat', ['hai'])
        a, b_old, c, b_new = (memfs.rz(x) for x in (vi_a, jp_b, vi_c, vi_b_new))
        self.assertGreater(len(a) + len(c), 0xFFFF)
        d = tempfile.mkdtemp()
        try:
            ja, jc = len(memfs.rz(jp_a)), len(memfs.rz(jp_c))
            write_pair(os.path.join(d, 'jp'), [jp_a, jp_c, jp_b],
                       [('/_bytecode/A.tatc', 0x30, [0, ja]), ('/_bytecode/C.tatc', 0x30, [ja, jc]),
                        ('/_bytecode/B.tatc', 0x30, [ja + jc, len(memfs.rz(jp_b))])])
            write_pair(os.path.join(d, 'vi'), [vi_a, jp_b, vi_c, vi_b_new],
                       [('/_bytecode/A.tatc', 0x30, [0, len(a)]),
                        ('/_bytecode/C.tatc', 0x20, [len(a) + len(b_old), len(c)]),
                        ('/_bytecode/B.tatc', 0x30, [len(a), len(b_new)])])
            redirect = {(len(a), len(b_new)): len(a) + len(b_old) + len(c)}
            jp = memfs.Archive(*patch.find_pair(os.path.join(d, 'jp')))
            vi = memfs.Archive(*patch.find_pair(os.path.join(d, 'vi')), redirects=redirect)

            body, mem, rep = patch.build(jp, vi)
            self.assertEqual(patch.verify(body, mem, jp, {}), [])
            self.assertEqual(len(rep['repointed']), 1)
            self.assertEqual(rep['widened'], ['/_bytecode/B.tatc'])
            self.assertEqual(len(rep['dropped']), 1)                       # the stale JP copy of B
            ents = rson.entries(rson.parse(mem))
            self.assertGreater(ents['/_bytecode/B.tatc'].vals[0], 0xFFFF)
            self.assertEqual(ents['/_bytecode/A.tatc'].etype, 0x30)       # still fits, left u16
            out = dict((ch.pos, ch.raw) for ch in memfs.chunks(body))
            self.assertEqual(out[ents['/_bytecode/B.tatc'].vals[0]], vi_b_new)
            self.assertEqual(kuv.parse(out[0])[1][4], '#P(500,130)một')
            # an entry equal to a redirect pair would be moved by the exe: refused
            vi.redirects = {tuple(ents['/_bytecode/A.tatc'].vals): 1}
            with self.assertRaises(SystemExit):
                patch.build(jp, vi)
        finally:
            shutil.rmtree(d, ignore_errors=True)


def sheet_row(n, ci, jp, vi, script='A.tat'):
    return dict(tab=script[:-4], row=n, rid=n, cmd='GuideMess', script=script, ci=ci, jp=jp, vi=vi)


class ApplySheetTest(unittest.TestCase):
    def test_prepare_does_what_the_vi_builder_did(self):
        self.assertEqual(applysheet.prepare('「Ừ, “đi” "nhé"」\n\nTiếp　theo'), "Ừ, đi 'nhé'\nTiếp theo")
        self.assertEqual(applysheet.prepare('Việt'), 'Việt')            # NFC
        long = applysheet.prepare(' '.join(['chữ'] * 30))
        self.assertGreater(long.count('\n'), 0)
        self.assertTrue(all(tags.vis(line) <= tags.WRAP for line in long.split('\n')))

    def test_learns_the_font_from_the_mod_and_encodes(self):
        jp = {'A.tat': ['一', '二', '三']}
        mod = {'A.tat': ['mばt', 'Viるt', 'khác hẳn']}
        rows = [sheet_row(2, 0, '一', 'một'), sheet_row(3, 1, '二', 'Việt'), sheet_row(4, 2, '三', 'không khớp')]
        fmap, seen = applysheet.learn_font(rows, jp, mod)
        self.assertEqual(fmap, {'ộ': 'ば', 'ệ': 'る'})
        self.assertEqual(applysheet.encode('Việt một', fmap, seen), ('Viるt mばt', []))
        # a capital the mod never used falls back to its small letter, and is reported
        self.assertEqual(applysheet.encode('Ệ', fmap, seen), ('る', [('Ệ', 'lower')]))

    def test_plan_never_writes_a_worse_line(self):
        js = {'A.tat': ['', 'GuideMess', '「はい」', '「っ！」', '一つ', '二', '三', '四']}
        fmap, seen = {'ệ': 'る'}, set('âạ')
        rows = [sheet_row(2, 2, '「はい」', '「Vâng」'),
                sheet_row(3, 3, '「っ！」', '「っ！」'),            # a gasp reads the same: written
                sheet_row(4, 4, '一つ', 'Việt の'),                # kana left in: would show wrong letters
                sheet_row(5, 5, '二', '二'),                       # still the JP line
                sheet_row(6, 6, '違う', 'x'),                      # sheet of another version
                sheet_row(7, 2, '「はい」', '「Dạ」'),              # second row, other translation
                sheet_row(8, 7, '四', 'Việt\n')]                   # JP has no trailing break
        writes, rep = applysheet.plan(rows, js, fmap, seen)
        self.assertEqual(writes['A.tat'], {2: 'Vâng', 3: 'っ！', 7: 'Viるt'})
        self.assertEqual(dict((x['r']['row'], x.get('why', x['action'])) for x in rep),
                         {2: 'write', 3: 'write', 4: 'japanese', 5: 'untranslated', 6: 'jp-mismatch',
                          7: 'duplicate', 8: 'write'})

    def test_build_writes_cells_as_they_are_and_keeps_the_mods_other_lines(self):
        import shutil
        jp_a, _ = script('A.tat', ['#P(500,130)一', '名前', '#P(520,1200)詩'])
        mod_a, _ = script('A.tat', ['#P(500,130)mばt', 'Tên', 'thơ'])
        d = tempfile.mkdtemp()
        try:
            write_pair(os.path.join(d, 'jp'), [jp_a], [('/_bytecode/A.tatc', 0x30, [0, len(memfs.rz(jp_a))])])
            write_pair(os.path.join(d, 'mod'), [mod_a], [('/_bytecode/A.tatc', 0x30, [0, len(memfs.rz(mod_a))])])
            jp = memfs.Archive(*patch.find_pair(os.path.join(d, 'jp')))
            mod = memfs.Archive(*patch.find_pair(os.path.join(d, 'mod')))
            js = applysheet.script_strings(jp)
            # tags are the translator's call: a cell without #P stays without, an
            # off-screen #P stays on; there is no row for the name
            rows = [sheet_row(2, 4, '#P(500,130)一', 'một nữa'), sheet_row(3, 6, '#P(520,1200)詩', '#P(520,1200)thơ')]
            writes, _ = applysheet.plan(rows, js, {'ộ': 'ば', 'ữ': '㈷'}, set('ơ'))
            body, mem, rep = applysheet.build(jp, mod, writes)
            self.assertEqual(patch.verify(body, mem, jp, {}, check_tags=False), [])
            self.assertEqual(patch.verify(body, mem, jp, {}), ['1 strings still lose #P'])   # what audit-style checks see
            out = applysheet.script_strings(memfs.Archive(data=(mem, body)))['A.tat']
            self.assertEqual(out[4:], ['mばt n㈷a', 'Tên', '#P(520,1200)thơ'])
            self.assertEqual((rep['rows'], rep['stripped']), ([], []))
        finally:
            shutil.rmtree(d, ignore_errors=True)


def make_rtex(w, h, pw, ph, pixel, flags=0x02):
    """An RGBA8 RTEX of w x h padded to pw x ph; pixel(x, y) gives 4 bytes."""
    stride = pw * 4
    raw = b''.join(pixel(x, y) for y in range(ph) for x in range(pw))
    payload = b'RZ' + len(raw).to_bytes(4, 'big') + zlib.compress(raw)
    return b'RTEX' + struct.pack('<I4H4I', 0, w, h, pw, ph, 0x20, len(payload), flags, stride) + payload


def make_ssdata(textures, parts, states, frames):
    """parts: [(name, texture index)]; states: [(part, x, y, w, h)]; frames: [[state index]]."""
    hsize = 0x18
    out = bytearray(hsize)
    for part, x, y, w, h in states:
        out += struct.pack('<IH4H', 0, part, x, y, w, h) + b'\0' * 26

    def put(b):
        while len(out) % 4:
            out.append(0)
        p = len(out); out.extend(b); return p
    tex_names = [put(t.encode() + b'\0') for t in textures]
    tex_p = put(struct.pack('<%dI' % (len(tex_names) + 1), *(tex_names + [0])))
    names = [put(n.encode() + b'\0') for n, _ in parts]
    parts_p = put(b''.join(struct.pack('<I4HI', names[i], i, 0, t, 0, 0) for i, (_, t) in enumerate(parts)))
    lists = [put(struct.pack('<%dH' % len(f), *f)) for f in frames]
    frames_p = put(b''.join(struct.pack('<3I', p, 0, len(f)) for p, f in zip(lists, frames)))
    po = put(b'\xff\xff\xff\xffABSS' + struct.pack('<5I3H', 3, 0, parts_p, frames_p, tex_p, len(parts), len(frames), 60))
    out[:8] = b'SSAD1.03'
    struct.pack_into('<4I', out, 8, hsize, 16, po, 0)
    return bytes(out)


def ui_ssdata():
    parts = [('root', 0), ('label_off', 0), ('label_on', 0), ('star', 0), ('twin', 0)]
    states = [(0, 0, 0, 0, 0), (1, 1, 1, 4, 2), (2, 1, 3, 4, 2), (3, 6, 0, 2, 2), (3, 6, 2, 2, 2), (4, 1, 1, 4, 2)]
    return make_ssdata(['ui.png'], parts, states, [[0, 1, 2, 3], [0, 1, 4, 5]])


def write_sprite_pair(folder, files, u16=()):
    """ui.memfs/ui.membody from [(path, bytes)], back to back; paths in u16 get u16 entries."""
    os.makedirs(folder, exist_ok=True)
    body, table = b'', []
    for p, d in files:
        table.append((rson.Str(p), rson.Arr(0x30 if p in u16 else 0x20, [len(body), len(d)])))
        body += d
    root = rson.Map([(rson.Str('alignBytes'), rson.Raw(b'\x41')),
                     (rson.Str('path'), rson.Map(table, tuple(range(len(table))), 0))], (1, 2), 0)
    with open(os.path.join(folder, 'ui.memfs'), 'wb') as f:
        f.write(rson.write(root))
    with open(os.path.join(folder, 'ui.membody'), 'wb') as f:
        f.write(body)
    return os.path.join(folder, 'ui.memfs')


def gradient(x, y):
    return bytes([x * 30, y * 30, 100, 255 if x < 8 and y < 6 else 7])


class SpriteCellsTest(unittest.TestCase):
    def test_cells_from_frames(self):
        c = sprite.cells(ui_ssdata())
        self.assertEqual(c[('ui.png', 1, 1, 4, 2)], {'label_off', 'twin'})     # one rectangle, two parts
        self.assertEqual(c[('ui.png', 1, 3, 4, 2)], {'label_on'})
        self.assertEqual(c[('ui.png', 6, 0, 2, 2)], {'star'})
        self.assertEqual(c[('ui.png', 6, 2, 2, 2)], {'star'})
        self.assertEqual(len(c), 4)                                            # the 0x0 state is not a cell


@unittest.skipUnless(HAVE_PIL, 'Pillow is not installed')
class SpriteTest(unittest.TestCase):
    """An 8x6 RGBA8 atlas padded to 8x8, a block-compressed texture that is left
    alone, and a filler that puts the next u16 entry right at 65535."""

    def setUp(self):
        import shutil
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, ignore_errors=True)
        self.atlas = make_rtex(8, 6, 8, 8, gradient)
        bc = b'RTEX' + struct.pack('<I4H4I', 0, 4, 4, 4, 4, 0x20, 8, 0x81014, 2) + b'\x11' * 8
        filler = b'\x5a' * (0xFFFF - len(self.atlas))
        self.files = [('/filler.bin', filler), ('/ui.rtex', self.atlas), ('/ui.ssdata', ui_ssdata()), ('/bg.rtex', bc)]
        self.memfs = write_sprite_pair(os.path.join(self.d, 'jp'), self.files, u16={'/ui.ssdata'})

    def quiet(self, fn, *args):
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()) as buf:
            rc = fn(*args)
        return rc, buf.getvalue()

    def export(self):
        arc = sprite.Archive(self.memfs)
        folder = os.path.join(self.d, 'anh')
        self.assertEqual(self.quiet(sprite.cmd_export, arc, folder)[0], 0)
        return arc, folder

    def test_check_rebuilds_byte_for_byte(self):
        arc = sprite.Archive(self.memfs)
        self.assertEqual(arc.build({}), (arc.memfs, arc.body))
        self.assertEqual(self.quiet(sprite.cmd_check, arc)[0], 0)
        self.assertFalse(arc.textures['/bg.rtex'].editable)

    def test_export_names_cells(self):
        from PIL import Image
        arc, folder = self.export()
        files = sorted(c.file for c in arc.cells)
        self.assertEqual(files, ['ui/label_off.png', 'ui/label_on.png', 'ui/star_6_0.png', 'ui/star_6_2.png'])
        for rel, size in (('ui/label_on.png', (4, 2)), ('ui.png', (8, 6))):
            with Image.open(os.path.join(folder, rel)) as im:
                self.assertEqual(im.size, size)
        self.assertFalse(os.path.exists(os.path.join(folder, 'bg.png')))       # BC: skipped
        new, _, problems = sprite.plan_import(arc, folder)
        self.assertEqual((new, problems), ({}, []))                            # untouched export: no change

    def test_export_without_folder_only_lists(self):
        arc = sprite.Archive(self.memfs)
        before = sorted(os.listdir(self.d))
        rc, log = self.quiet(sprite.cmd_export, arc, None)
        self.assertEqual(rc, 0)
        self.assertEqual(sorted(os.listdir(self.d)), before)                   # nothing written
        self.assertIn('ui/label_on.png', log)
        self.assertIn('4 o sua duoc', log)

    def test_import_pastes_cell_and_keeps_the_rest(self):
        from PIL import Image
        arc, folder = self.export()
        noise = bytes((i * 97 + 13) % 256 for i in range(4 * 2 * 4))
        Image.frombytes('RGBA', (4, 2), noise).save(os.path.join(folder, 'ui', 'label_on.png'))
        out = os.path.join(self.d, 'mod')
        rc, log = self.quiet(sprite.cmd_import, arc, folder, out, False)
        self.assertEqual(rc, 0, log)
        self.assertFalse(os.path.exists(out))                                  # dry run writes nothing
        rc, log = self.quiet(sprite.cmd_import, arc, folder, out, True)
        self.assertEqual(rc, 0, log)
        res = sprite.Archive(os.path.join(out, 'ui.memfs'))
        img = res.textures['/ui.rtex'].image()
        self.assertEqual(img.crop((1, 3, 5, 5)).tobytes(), noise)
        before = arc.textures['/ui.rtex'].image()
        for y in range(6):
            for x in range(8):
                if not (1 <= x < 5 and 3 <= y < 5):
                    self.assertEqual(img.getpixel((x, y)), before.getpixel((x, y)))
        t = res.textures['/ui.rtex']
        self.assertEqual(t.raw()[t.stride * 6:], arc.textures['/ui.rtex'].raw()[t.stride * 6:])   # padding rows
        for p in ('/filler.bin', '/ui.ssdata', '/bg.rtex'):
            self.assertEqual(res.files[p], arc.files[p])
        self.assertEqual(res.entries['/ui.ssdata'].etype, 0x20)                # pushed past 65535: widened
        self.quiet(sprite.cmd_import, arc, folder, out, True)
        self.assertTrue(os.path.exists(os.path.join(out, 'ui.membody.bak')))

    def test_cell_wins_over_whole_texture(self):
        from PIL import Image
        arc, folder = self.export()
        Image.new('RGBA', (8, 6), (1, 2, 3, 255)).save(os.path.join(folder, 'ui.png'))
        Image.new('RGBA', (2, 2), (9, 9, 9, 9)).save(os.path.join(folder, 'ui', 'star_6_0.png'))
        new, report, problems = sprite.plan_import(arc, folder)
        self.assertEqual(problems, [])
        img = new['/ui.rtex']
        self.assertEqual(img.getpixel((0, 0)), (1, 2, 3, 255))
        self.assertEqual(img.getpixel((7, 1)), (9, 9, 9, 9))

    def test_wrong_size_and_stray_files_are_reported(self):
        from PIL import Image
        arc, folder = self.export()
        Image.new('RGBA', (5, 2)).save(os.path.join(folder, 'ui', 'label_off.png'))
        Image.new('RGBA', (2, 2)).save(os.path.join(folder, 'ui', 'label_of.png'))
        _, report, problems = sprite.plan_import(arc, folder)
        self.assertEqual(len(problems), 1)
        self.assertIn('4x2', problems[0])
        self.assertTrue(any('label_of.png' in r for r in report))
        self.assertEqual(self.quiet(sprite.cmd_import, arc, folder, os.path.join(self.d, 'mod'), True)[0], 1)

    def test_import_needs_a_folder_taken_out_of_this_screen(self):
        arc = sprite.Archive(self.memfs)
        empty = os.path.join(self.d, 'empty')
        os.makedirs(empty)
        rc, log = self.quiet(sprite.cmd_import, arc, empty, os.path.join(self.d, 'mod'), False)
        self.assertEqual(rc, 1)
        self.assertIn('chua co anh lay ra', log)

    def test_export_asks_before_overwriting(self):
        from PIL import Image
        arc, folder = self.export()
        mine = os.path.join(folder, 'ui', 'label_on.png')
        Image.new('RGBA', (4, 2), (9, 9, 9, 9)).save(mine)                      # a redrawn cell
        rc, log = self.quiet(sprite.cmd_export, arc, folder)                      # held back
        self.assertEqual(rc, 0)
        self.assertIn('1 file khac ban goc', log)
        self.assertIn('ui/label_on.png -> label_on.png.bak', log)
        self.assertIn('them --overwrite de ghi de vao %s' % folder, log)
        with Image.open(mine) as im:
            self.assertEqual(im.convert('RGBA').getpixel((0, 0)), (9, 9, 9, 9))
        self.assertFalse(os.path.exists(mine + '.bak'))
        rc, log = self.quiet(sprite.cmd_export, arc, folder, True)                # the user said yes
        self.assertEqual(rc, 0)
        with Image.open(mine + '.bak') as im:                                      # the drawing is kept
            self.assertEqual(im.convert('RGBA').getpixel((0, 0)), (9, 9, 9, 9))
        before = arc.textures['/ui.rtex'].image().crop((1, 3, 5, 5)).tobytes()
        with Image.open(mine) as im:
            self.assertEqual(im.convert('RGBA').tobytes(), before)
        self.assertEqual([n for n in os.listdir(os.path.join(folder, 'ui')) if n.endswith('.bak')], ['label_on.png.bak'])

    def test_translate_picks_the_half_by_the_folder(self):
        from PIL import Image
        arc = sprite.Archive(self.memfs)
        folder, out = os.path.join(self.d, 'anh'), os.path.join(self.d, 'mod')
        rc, log = self.quiet(sprite.cmd_translate, arc, folder, None, False)        # empty: take out
        self.assertEqual(rc, 0)
        self.assertTrue(os.path.exists(os.path.join(folder, 'ui', 'label_on.png')))
        self.assertIn('Buoc tiep theo', log)
        rc, log = self.quiet(sprite.cmd_translate, arc, folder, out, False)         # nothing redrawn yet
        self.assertEqual(rc, 0)
        self.assertIn('chua co o nao duoc ve lai', log)
        self.assertNotIn('--apply', log)                                           # the app asks nothing
        Image.new('RGBA', (4, 2), (9, 9, 9, 9)).save(os.path.join(folder, 'ui', 'label_on.png'))
        self.assertEqual(self.quiet(sprite.cmd_translate, arc, folder, None, False)[0], 1)   # needs --out
        rc, log = self.quiet(sprite.cmd_translate, arc, folder, out, False)         # dry run
        self.assertEqual(rc, 0)
        self.assertIn('--apply de ghi vao %s' % out, log)
        self.assertFalse(os.path.exists(out))
        self.assertEqual(self.quiet(sprite.cmd_translate, arc, folder, out, True)[0], 0)
        self.assertTrue(os.path.exists(os.path.join(out, 'ui.membody')))
        rc, log = self.quiet(sprite.cmd_translate, arc, folder, out, False)         # the dialog says what goes
        self.assertIn('se thay file da co, ban cu chep sang file .bak cung thu muc: '
                      'ui.memfs -> ui.memfs.bak, ui.membody -> ui.membody.bak', log)
        rc, log = self.quiet(sprite.cmd_translate, arc, folder, out, True)          # and where it went
        self.assertIn('ban cu -> %s' % os.path.join(out, 'ui.membody.bak'), log)
        rc, log = self.quiet(sprite.cmd_translate, arc, folder, out, False)         # never over an older copy
        self.assertIn('ui.membody -> ui.membody.bak2', log)
        other = os.path.join(self.d, 'other')                                      # someone else's files
        os.makedirs(other)
        open(os.path.join(other, 'notes.txt'), 'w').close()
        self.assertEqual(self.quiet(sprite.cmd_translate, arc, other, out, False)[0], 1)
        rc, log = self.quiet(sprite.cmd_translate, arc, None, None, False)          # no folder: list
        self.assertEqual(rc, 0)
        self.assertIn('ui/label_on.png', log)


# A tiny exefs/main: text at 0, rodata at 0x1000, data at 0x2000, then .bss.
NOP, BL = 0xd503201f, 0x94000001
S1, S2, S3, S4, S5 = 0x1010, 0x1100, 0x1200, 0x1300, 0x1400      # rodata strings
RELA, DYN = 0x1800, 0x2000


def u32text(s):
    return s.encode('utf-32le') + b'\0\0\0\0'


def add_imm(rd, rn, imm):
    return 0x91000000 | (imm << 10) | (rn << 5) | rd


def adr(pc, target, rd):
    imm = (target - pc) & ((1 << 21) - 1)
    return 0x10000000 | ((imm & 3) << 29) | ((imm >> 2) << 5) | rd


def lz4_literals(d):
    """An LZ4 block of literals only: what exehook.lz4_block reads back as d."""
    n = len(d)
    out = bytearray([min(n, 15) << 4])
    if n >= 15:
        rest = n - 15
        while rest >= 255:
            out.append(255); rest -= 255
        out.append(rest)
    return bytes(out + d)


def make_main(compress=False):
    text = bytearray(0x1000)
    words = {0: 0x14000010, 4: 8,                                # b 0x40, MOD0 at 8
             0x40: exetext.adrp(0x40, S1, 1), 0x44: add_imm(1, 1, S1 & 0xfff),     # S1 by code
             0x48: adr(0x48, S4, 2),                                                # S4 by ADR
             0x4c: exetext.adrp(0x4c, S3, 3), 0x50: add_imm(3, 3, S3 & 0xfff),     # S3 is ASCII
             0x54: exetext.adrp(0x54, S5, 1), 0x58: BL, 0x5c: add_imm(0, 1, S5 & 0xfff)}  # x1 lost in the call
    for i in range(0, 0x1000, 4):
        struct.pack_into('<I', text, i, words.get(i, NOP))
    text[8:12] = b'MOD0'
    struct.pack_into('<6i', text, 12, DYN - 8, 0x2100 - 8, 0x3100 - 8, 0, 0, 0)
    ro = bytearray(0x1000)
    for a, s in ((S1, '前回と同じ名前を使用します｡'), (S2, '\nよろしいですか？'), (S3, 'SYSTEM'),
                 (S4, 'クイックセーブしました｡'), (S5, '設定')):
        b = u32text(s)
        ro[a - 0x1000:a - 0x1000 + len(b)] = b
    relas = ((0x2080, S2), (0x2088, S1), (0x2090, S2 + 4))       # the last shares S2's tail
    for k, (off, add) in enumerate(relas):
        struct.pack_into('<QQq', ro, RELA - 0x1000 + 24 * k, off, 1027, add)
    data = bytearray(0x100)
    struct.pack_into('<8Q', data, 0, 7, RELA, 8, 24 * len(relas), 9, 24, 0, 0)
    h = bytearray(0x100)
    h[:4] = b'NSO0'
    struct.pack_into('<I', h, 0x0C, 0x3f if compress else 0x38)
    struct.pack_into('<I', h, 0x1C, 0x100)
    struct.pack_into('<I', h, 0x2C, 1)
    struct.pack_into('<I', h, 0x3C, 0x1000)
    pos, body = 0x101, b''
    for k, (moff, seg) in enumerate(((0, text), (0x1000, ro), (0x2000, data))):
        packed = lz4_literals(bytes(seg)) if compress else bytes(seg)
        struct.pack_into('<3I', h, 0x10 + 0x10 * k, pos, moff, len(seg))
        struct.pack_into('<I', h, 0x60 + 4 * k, len(packed))
        pos += len(packed); body += packed
    return bytes(h) + b'\0' + body


FONT = {'ạ': 'ヒ', 'ồ': 'ん', 'ứ': 'ソ', 'ư': 'ゔ', 'ớ': 'ロ', 'đ': 'コ', 'ậ': 'ノ', 'ầ': 'ハ'}


class ExeTextTest(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.main = os.path.join(self.d, 'main')
        with open(self.main, 'wb') as f:
            f.write(make_main(compress=True))
        self.map = os.path.join(self.d, 'font.json')
        with open(self.map, 'w', encoding='utf-8') as f:
            json.dump(FONT, f, ensure_ascii=False)

    def quiet(self, fn, *args):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = fn(*args)
        return rc, buf.getvalue()

    def test_adrp_encoding(self):
        self.assertEqual(exetext.adrp(0x10, 0x1000, 1), 0xb0000001)      # adrp x1, #0x1000
        self.assertEqual(exetext.adrp_target(exetext.adrp(0x7ff0, 0x6a6123, 9), 0x7ff0), 0x6a6000)

    def test_finds_what_the_program_points_at(self):
        exe = exetext.Exe(make_main(compress=True))
        self.assertEqual(sorted(exe.strings), [S1, S2, S2 + 4, S4])       # not ASCII, not S5 after the call
        self.assertEqual(sorted(k for k, _ in exe.refs[S1]), ['add', 'rela'])
        self.assertEqual(exe.refs[S4], [('adr', 0x48)])
        self.assertEqual(exe.strings[S2 + 4], 'よろしいですか？')

    def test_moves_translations_and_repoints(self):
        exe = exetext.Exe(make_main())
        writes = {S1: 'Dùng lại tên lần trước, dài hơn câu tiếng Nhật nhiều.', S2: '\nBạn đồng ý chứ?', S4: 'Đã lưu.'}
        raw, where = exetext.build(exe, writes)
        self.assertEqual(exetext.verify(raw, exe, writes, where), [])
        img = exetext.Nso(raw).image()
        self.assertEqual(where[S1] % 0x1000, 0)                           # reached by ADRP
        self.assertEqual(where[S4] % 0x1000, 0)
        self.assertGreaterEqual(where[S1], 0x4000)                        # past the old .bss
        self.assertEqual(exetext.adrp_target(struct.unpack_from('<I', img, 0x44)[0], 0x44), where[S1])
        self.assertEqual(struct.unpack_from('<I', img, 0x40)[0], exetext.adrp(0x40, S1, 1))   # its ADRP kept
        self.assertEqual(struct.unpack_from('<q', img, RELA + 16)[0], where[S2])
        self.assertEqual(struct.unpack_from('<q', img, RELA + 64)[0], S2 + 4)        # the shared tail untouched
        self.assertEqual(exetext.read_text(img, S2 + 4), 'よろしいですか？')
        self.assertEqual(exetext.read_text(img, S1), '前回と同じ名前を使用します｡')     # JP bytes stay
        self.assertEqual(exetext.read_text(img, where[S1]), writes[S1])

    def test_import_on_its_own_output_starts_from_the_original(self):
        exe = exetext.Exe(make_main(compress=True))
        first, _ = exetext.build(exe, {S1: 'Một', S4: 'Hai'})
        again = exetext.Exe(first)
        self.assertEqual(again.img, exe.img)
        self.assertEqual(again.current_text(S4), 'Hai')
        self.assertEqual(sorted(again.strings), sorted(exe.strings))
        self.assertEqual(exetext.build(again, {S2: '\nBa'})[0], exetext.build(exe, {S2: '\nBa'})[0])

    def test_rows_are_checked_like_sheet_cells(self):
        exe = exetext.Exe(make_main())
        rows = [dict(row=2, address=S1, jp='前回と同じ名前を使用します｡', vi='Dùng lại tên cũ.'),
                dict(row=3, address=S2, jp='よろしいですか？', vi='Bạn đồng ý chứ?'),      # sheet trimmed the \n
                dict(row=4, address=S4, jp='クイックセーブしました｡', vi='Đã lưu nhanh した'),
                dict(row=5, address=S2 + 4, jp='よろしいですか？', vi=''),
                dict(row=6, address=0x1234, jp='x', vi='y'),
                dict(row=7, address=S1, jp='前回と同じ名前を使用します｡', vi='Lần hai')]
        writes, rep = exetext.plan(rows, exe, FONT)
        self.assertEqual([x['why'].split(',')[0] for x in rep], ['', '', 'japanese', 'empty', 'no-string', 'duplicate'])
        self.assertEqual(writes[S2], '\nBヒn コんng ý chソ?')                 # \n kept, letters on the font's codes
        self.assertEqual(writes[S1], 'Dùng lヒi tên cũ.')

    def test_printf_codes_must_match(self):
        exe = exetext.Exe(make_main())
        exe.strings[S4] = '残り %d 個'
        bad = exetext.plan([dict(row=2, address=S4, jp='残り %d 個', vi='Còn lại')], exe, FONT)[1]
        good = exetext.plan([dict(row=2, address=S4, jp='残り %d 個', vi='Còn %d cái')], exe, FONT)[1]
        self.assertEqual((bad[0]['why'], good[0]['action']), ('format', 'write'))

    def test_export_then_import(self):
        sheet, out = os.path.join(self.d, 'chu_exe.csv'), os.path.join(self.d, 'mod', 'exefs')
        self.assertEqual(self.quiet(exetext.cmd_export, self.main, sheet, None)[0], 0)
        with open(sheet, encoding='utf-8-sig', newline='') as f:
            rows = list(csv.reader(f))
        self.assertEqual(rows[0], list(exetext.COLUMNS))
        self.assertEqual([r[0] for r in rows[1:]], ['0x%x' % a for a in (S1, S2, S2 + 4, S4)])
        rows[1][3] = 'Dùng lại tên cũ.'
        with open(sheet, 'w', encoding='utf-8-sig', newline='') as f:
            csv.writer(f).writerows(rows)
        rc, log = self.quiet(exetext.cmd_import, self.main, sheet, self.map, out, None, False)
        self.assertEqual(rc, 0)
        self.assertIn('--apply de ghi vao %s' % out, log)
        self.assertFalse(os.path.exists(out))
        self.assertEqual(self.quiet(exetext.cmd_import, self.main, sheet, self.map, out, None, True)[0], 0)
        new = exetext.open_exe(os.path.join(out, 'main'))
        self.assertEqual(new.current_text(S1), 'Dùng lヒi tên cũ.')
        rc, log = self.quiet(exetext.cmd_export, os.path.join(out, 'main'), sheet, self.map)
        self.assertIn('1 dong da dien', log)
        self.assertEqual(self.quiet(exetext.cmd_check, os.path.join(out, 'main'))[0], 0)


if __name__ == '__main__':
    unittest.main(verbosity=1)
