#!/usr/bin/env python3
"""Tests for engines/rrlib/tools on synthetic files - no game data needed
(SpriteGameScreensTest also reads the JP screens when they are there)."""
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
import exepatch  # noqa: E402
import exetext  # noqa: E402
import font     # noqa: E402
import kuv      # noqa: E402
import memfs    # noqa: E402
import overflow  # noqa: E402
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
        self.assertEqual(applysheet.prepare('「Ừ, “đi” "nhé"」\n\nTiếp　theo'), 'Ừ, đi "nhé"\nTiếp theo')
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

    def test_a_pasted_csv_row_writes_only_its_vi_part(self):
        jp1 = '「……ふふ。ありがとう、皆さん。\r\n　良き一年に！」'
        jp2 = '影は濃くなっていた。\r\n蛇が這う音が、\r\nどこからか聞こえる。'
        js = {'A.tat': ['', jp1, jp2, '「――……」', '一', '「んっ……、――」', '「はい」']}
        said = lambda row: dict(row, cmd='NameMess')
        sheet = lambda t: t.replace('\r\n', '\n\n')
        rows = [said(sheet_row(2, 1, sheet(jp1), '「……ふふ.ありがとう,皆さん. 良き一年に！」,Ko Seirin,'
                                                 '「...Phù phù. Cảm ơn mọi người!」')),
                # narration: no speaker, empty columns after it, a typo in the JP part
                sheet_row(3, 2, sheet(jp2), '影は濃くなってぃた. 蛇が這う音が, どこからか聞こえる.,'
                                            'Cái bóng đậm hơn, tiếng rắn vang lên.,,,,,'),
                said(sheet_row(4, 3, '「――……」', '「――……」,Ko Seirin,「—...」')),   # VI all punctuation
                sheet_row(5, 4, '一', 'Một, hai,,,,,'),                               # only the empty columns
                sheet_row(6, 5, '「んっ……、――」', '「んっ……,――」'),                     # the JP line itself
                said(sheet_row(7, 6, '「はい」', '「Vâng, Seirin, đi thôi」')),            # VI with commas stays whole
                said(sheet_row(8, 3, '「――……」', '「――……」,Ko Ouyo,「—...」'))]       # same string, other speaker
        writes, rep = applysheet.plan(rows, js, {}, set('ùơóôạ'))
        self.assertEqual(writes['A.tat'], {1: '...Phù phù. Cảm ơn mọi người!', 2: 'Cái bóng đậm hơn, tiếng rắn vang lên.',
                                           3: '—...', 4: 'Một, hai', 6: 'Vâng, Seirin, đi thôi'})
        self.assertEqual(dict((x['r']['row'], (x.get('why', x['action']), x['csv'] and x['csv'][1:])) for x in rep),
                         {2: ('write', ('Ko Seirin', 'row')), 3: ('write', (None, 'row')), 4: ('write', ('Ko Seirin', 'row')),
                          5: ('write', (None, 'columns')), 6: ('japanese', None), 7: ('write', None),
                          8: ('same', ('Ko Ouyo', 'row'))})
        # ruby and #T lines in the JP part as the old export wrote them
        self.assertEqual(applysheet.csv_row('「水剋火――龍は水.」,Ko Ouyo,「Thủy khắc Hỏa.」',
                                            '「#R(すい,こく,か)水剋火――龍は水。」', 'NameMess'),
                         ('「Thủy khắc Hỏa.」', 'Ko Ouyo', 'row'))
        self.assertEqual(applysheet.csv_row('#T1「え？ ナーヤ！？\n#T2「え？\n#T0 父上,何故」,Ko Seirin,「Hả? Naya!? Vì sao?」',
                                            '#T1「え？　ナーヤ！？\n\n#T2「え？\n\n#T0　父上、何故」', 'NameMess'),
                         ('「Hả? Naya!? Vì sao?」', 'Ko Seirin', 'row'))
        with tempfile.TemporaryDirectory() as d:
            applysheet.write_report(os.path.join(d, 'r.csv'), rep)
            with open(os.path.join(d, 'r.csv'), encoding='utf-8-sig') as f:
                noted = [row[1] for row in csv.reader(f) if 'CSV' in row[-1] or ',,,,,' in row[-1]]
        self.assertEqual(noted, ['2', '3', '4', '5', '8'])

    def test_a_speaker_name_or_comma_in_front_of_the_cell_is_dropped(self):
        js = {'A.tat': ['', '「止まれ……！」', '「もう、立って歩かれているわ……」', '#P(250,300)「はい」', '（無理……）',
                        '彼は言った。', '「はい」', '「え？」']}
        said = lambda row: dict(row, cmd='NameMess')
        rows = [said(sheet_row(2, 1, '「止まれ……！」', 'Fey,「Dừng lại……!」')),
                said(sheet_row(3, 2, '「もう、立って歩かれているわ……」',
                               'Thị nữ Tuyết Nguyệt Hoa Vương triều 1,「Trời ạ, đã đi được rồi……」')),   # 37 letters
                said(sheet_row(4, 3, '#P(250,300)「はい」', '#P(250,300)Kỷ Uyển,「Vâng」')),            # tag stays
                said(sheet_row(5, 4, '（無理……）', ',（Không thể...）')),                                # comma in front
                sheet_row(6, 5, '彼は言った。', ',,Anh ấy nói.'),                                        # narration too
                sheet_row(7, 6, '「はい」', 'Ừ,「Vâng」'),                     # not a NameMess line: left alone
                said(sheet_row(8, 7, '「え？」', '「Hả?」, Fey, à'))]          # name not in front: left alone
        writes, rep = applysheet.plan(rows, js, {}, set('ùơóôạ'))
        self.assertEqual(writes['A.tat'], {1: 'Dừng lại……!', 2: 'Trời ạ, đã đi được rồi……', 3: '#P(250,300)Vâng',
                                           4: '（Không thể...）', 5: 'Anh ấy nói.', 6: 'Ừ,Vâng', 7: "Hả?, Fey, à"})
        self.assertEqual(dict((x['r']['row'], x['csv'] and x['csv'][1:]) for x in rep),
                         {2: ('Fey', 'name'), 3: ('Thị nữ Tuyết Nguyệt Hoa Vương triều 1', 'name'), 4: ('Kỷ Uyển', 'name'),
                          5: (None, 'comma'), 6: (None, 'comma'), 7: None, 8: None})
        # both leftovers in one cell, and a JP line that itself opens with 、 keeps its comma
        self.assertEqual(applysheet.cleanup(',Fey,「Ừ」,,,,', '「うん」', 'NameMess'), ('「Ừ」', 'Fey', 'columns+comma+name'))
        self.assertIsNone(applysheet.cleanup(', và thế là', '、そして', 'GuideMess'))

    def test_two_p_faults_are_mended(self):
        self.assertEqual(applysheet.fix_tags('#P(1110220),――Khổ quá.', '#P(1110,220)――苦しい。'),
                         ('#P(1110,220)――Khổ quá.', ['broken']))
        self.assertEqual(applysheet.fix_tags('#P(440,1124)Vạn vật\n#P(440,1200)thuận', '#P(440,1200)「全てが」'),
                         ('Vạn vật\nthuận', ['offscreen']))
        self.assertEqual(applysheet.fix_tags('#P(440,300)a\n#P(440,1200)b', '#P(440,300)あ'),
                         ('#P(440,300)a\n#P(440,1200)b', []))                    # part on screen: left alone
        self.assertEqual(applysheet.fix_tags('#P(999),x', '#P(1,2)あ'), ('#P(999),x', []))   # no JP tag reads so
        js = {'A.tat': ['', '#P(520,1200)「天地は」\n', '#P(1110,220)――苦しい。']}
        rows = [sheet_row(2, 1, '#P(520,1200)「天地は」\n', '#P(520,1200)Trời đất.\n'),
                sheet_row(3, 2, '#P(1110,220)――苦しい。', '#P(1110220),――Khổ quá.')]
        writes, rep = applysheet.plan(rows, js, {}, set('ờấổá'))
        self.assertEqual(writes['A.tat'], {1: 'Trời đất.\n', 2: '#P(1110,220)――Khổ quá.'})
        with tempfile.TemporaryDirectory() as d:
            applysheet.write_report(os.path.join(d, 'r.csv'), rep)
            with open(os.path.join(d, 'r.csv'), encoding='utf-8-sig') as f:
                notes = [row[-1] for row in csv.reader(f)][1:]
        self.assertEqual([n.split(' ')[1] for n in notes], ['#P', '#P'])
        self.assertIn('ngoài màn hình', notes[0])
        self.assertIn('hỏng', notes[1])

    def test_jp_text_without_its_dashes_still_matches(self):
        js = {'A.tat': ['', '「――……」', '「――オマ、エ……」']}
        rows = [sheet_row(2, 1, '「……」', '..'), sheet_row(3, 2, '「オマエ……」', 'Ngươi...')]   # 3: really another line
        writes, rep = applysheet.plan(rows, js, {}, set('ươ'))
        self.assertEqual(writes['A.tat'], {1: '..'})
        self.assertEqual([(x.get('why') or x['action'], x.get('fixed')) for x in rep],
                         [('write', ['dashes']), ('jp-mismatch', None)])

    def test_book_title_marks_turned_into_quotes_still_match(self):
        js = {'A.tat': ['', '「生きる《月下ノ国》だ」', '「生きる《月下ノ国》よ」']}
        rows = [sheet_row(2, 1, '「生きる"月下ノ国"だ」', 'X'),
                sheet_row(3, 2, '「生きる"月下ノ国"だ」', 'Lệch.')]          # よ became だ: another line
        writes, rep = applysheet.plan(rows, js, {}, set())
        self.assertEqual(writes['A.tat'], {1: 'X'})
        self.assertEqual([(x.get('why') or x['action'], x.get('fixed')) for x in rep],
                         [('write', ['brackets']), ('jp-mismatch', None)])

    def test_a_kanji_in_brackets_is_a_gloss(self):
        js = {'A.tat': ['', '嬅一族のこと。', '揺れ動く', 'あ']}
        rows = [sheet_row(2, 1, '嬅一族のこと。', 'Chỉ tộc Hoa (嬅).'),
                sheet_row(3, 2, '揺れ動く', 'lay動'),                    # a kanji in the text: a typo
                sheet_row(4, 3, 'あ', 'cài（だ）')]                        # kana: wrong letter even in brackets
        writes, rep = applysheet.plan(rows, js, {}, set('ỉộ'))
        self.assertEqual(writes['A.tat'], {1: 'Chỉ tộc Hoa (嬅).'})
        self.assertEqual([(x.get('why') or x['action'], x.get('chars')) for x in rep],
                         [('write', None), ('japanese', '動'), ('japanese', 'だ')])
        self.assertEqual(exetext.japanese_left('Hoa (嬅) っ'), [])

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
            # tags are the translator's call: a cell without #P stays without; an
            # off-screen #P goes (else the line shows only in the backlog); no row for the name
            rows = [sheet_row(2, 4, '#P(500,130)一', 'một nữa'), sheet_row(3, 6, '#P(520,1200)詩', '#P(520,1200)thơ')]
            writes, _ = applysheet.plan(rows, js, {'ộ': 'ば', 'ữ': '㈷'}, set('ơ'))
            body, mem, rep = applysheet.build(jp, mod, writes)
            self.assertEqual(patch.verify(body, mem, jp, {}, check_tags=False), [])
            self.assertEqual(patch.verify(body, mem, jp, {}), ['1 strings still lose #P'])   # what audit-style checks see
            out = applysheet.script_strings(memfs.Archive(data=(mem, body)))['A.tat']
            self.assertEqual(out[4:], ['mばt n㈷a', 'Tên', 'thơ'])
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
    """parts: [(name, texture index)]; states: [(part, x, y, w, h[, flags])], each
    at position (part * 10, -part); frames: [[state index]]."""
    hsize = 0x18
    out = bytearray(hsize)
    for s in states:
        part, x, y, w, h = s[:5]
        out += struct.pack('<IH4H2h', s[5] if len(s) > 5 else 0, part, x, y, w, h, part * 10, -part) + b'\0' * 22

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
        Image.new('RGBA', (5, 2)).save(os.path.join(folder, 'ui', 'label_off.png'))   # bigger: no empty pixel here
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

    def test_export_saves_the_games_images_to_compare(self):
        from PIL import Image
        arc, folder = self.export()
        Image.new('RGBA', (4, 2), (9, 9, 9, 9)).save(os.path.join(folder, 'ui', 'label_on.png'))
        rc, log = self.quiet(sprite.cmd_export, arc, folder)
        line = [l for l in log.splitlines() if l.startswith('anh goc de so sanh -> ')]
        self.assertEqual(len(line), 1)
        originals = line[0].split(' -> ', 1)[1]
        with Image.open(os.path.join(originals, 'ui', 'label_on.png')) as im:      # the game's pixels
            self.assertEqual(im.convert('RGBA').tobytes(), arc.textures['/ui.rtex'].image().crop((1, 3, 5, 5)).tobytes())
        self.assertFalse(os.path.exists(os.path.join(originals, 'ui', 'label_off.png')))   # only changed ones

    def test_export_keeps_what_the_user_chose(self):
        from PIL import Image
        arc, folder = self.export()
        self.assertTrue(os.path.exists(os.path.join(folder, 'cells_ui.csv')))   # named per screen
        mine, other = os.path.join(folder, 'ui', 'label_on.png'), os.path.join(folder, 'ui', 'label_off.png')
        Image.new('RGBA', (4, 2), (9, 9, 9, 9)).save(mine)
        Image.new('RGBA', (4, 2), (7, 7, 7, 7)).save(other)
        rc, log = self.quiet(sprite.cmd_export, arc, folder, True, ['ui/label_on.png'])
        self.assertEqual(rc, 0)
        self.assertIn('giu nguyen ui/label_on.png', log)
        with Image.open(mine) as im:                                               # kept as drawn, no copy
            self.assertEqual(im.convert('RGBA').getpixel((0, 0)), (9, 9, 9, 9))
        self.assertFalse(os.path.exists(mine + '.bak'))
        with Image.open(other + '.bak') as im:                                     # replaced, drawing in .bak
            self.assertEqual(im.convert('RGBA').getpixel((0, 0)), (7, 7, 7, 7))
        with Image.open(other) as im:
            self.assertNotEqual(im.convert('RGBA').getpixel((0, 0)), (7, 7, 7, 7))

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


@unittest.skipUnless(HAVE_PIL, 'Pillow is not installed')
class SpriteResizeTest(unittest.TestCase):
    """A 32x16 atlas, empty but for its cells: label (0,0 6x3, also drawn by
    twin and once faded, flags 0x200), star (8,0 2x2), odd (0,8 4x2, a state
    with flags 0x10)."""

    def setUp(self):
        import shutil
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d, ignore_errors=True)
        boxes = [(0, 0, 6, 3), (8, 0, 2, 2), (0, 8, 4, 2)]

        def px(x, y):
            inside = any(bx <= x < bx + bw and by <= y < by + bh for bx, by, bw, bh in boxes)
            return bytes([x * 7, y * 9, 50, 255]) if inside else b'\0\0\0\0'
        parts = [('root', 0), ('label', 0), ('twin', 0), ('star', 0), ('odd', 0)]
        states = [(0, 0, 0, 0, 0), (1, 0, 0, 6, 3), (1, 0, 0, 6, 3, 0x200), (2, 0, 0, 6, 3), (3, 8, 0, 2, 2),
                  (4, 0, 8, 4, 2), (4, 0, 8, 4, 2, 0x10)]
        ss = make_ssdata(['ui.png'], parts, states, [[0, 1, 3, 4, 5], [0, 2, 3, 6]])
        self.files = [('/ui.rtex', make_rtex(32, 16, 32, 16, px)), ('/ui.ssdata', ss), ('/ui.rson', b'RSON-ish')]
        self.memfs = write_sprite_pair(os.path.join(self.d, 'jp'), self.files)
        self.arc = sprite.Archive(self.memfs)
        self.folder = os.path.join(self.d, 'anh')
        self.out = os.path.join(self.d, 'mod')
        with contextlib.redirect_stdout(io.StringIO()):
            sprite.cmd_export(self.arc, self.folder)

    def draw(self, name, w, h, colour=(200, 10, 10, 255)):
        from PIL import Image
        img = Image.new('RGBA', (w, h), colour)
        img.putpixel((0, 0), (1, 2, 3, 255))
        img.save(os.path.join(self.folder, 'ui', name))
        return img

    def run_import(self, apply=True):
        with contextlib.redirect_stdout(io.StringIO()) as buf:
            rc = sprite.cmd_import(self.arc, self.folder, self.out, apply)
        return rc, buf.getvalue()

    def test_bigger_cell_moves_to_empty_space(self):
        from PIL import Image
        img = self.draw('label.png', 9, 4)
        rc, log = self.run_import()
        self.assertEqual(rc, 0, log)
        self.assertIn('ui/label.png: 9x4 thay cho 6x3 - dat vao cho trong (14,0), 3 trang thai', log)
        self.assertIn('.ssdata chi doi o x/y/w/h', log)
        res = sprite.Archive(os.path.join(self.out, 'ui.memfs'))
        got = dict((c.file, c) for c in res.cells)
        c = got['ui/label.png']
        self.assertEqual(((c.x, c.y, c.w, c.h), c.parts), ((14, 0, 9, 4), ['label', 'twin']))
        atlas = res.textures['/ui.rtex'].image()
        self.assertEqual(atlas.crop(c.box).tobytes(), img.tobytes())
        old = self.arc.textures['/ui.rtex'].image()
        self.assertEqual(atlas.crop((0, 0, 6, 3)).tobytes(), old.crop((0, 0, 6, 3)).tobytes())   # old place kept
        for x in range(32):                                    # nothing else drawn on
            for y in range(16):
                if not (14 <= x < 23 and y < 4):
                    self.assertEqual(atlas.getpixel((x, y)), old.getpixel((x, y)))
        self.assertEqual((got['ui/star.png'].x, got['ui/odd.png'].y), (8, 8))
        self.assertTrue(sprite.rects_only(self.arc.files['/ui.ssdata'], res.files['/ui.ssdata']))
        for p in ('/ui.rson',):
            self.assertEqual(res.files[p], self.arc.files[p])
        again = os.path.join(self.d, 'again')                  # taken out of the rebuilt screen: the new size
        with contextlib.redirect_stdout(io.StringIO()):
            sprite.cmd_export(res, again)
        with Image.open(os.path.join(again, 'ui', 'label.png')) as im:
            self.assertEqual(im.convert('RGBA').tobytes(), img.tobytes())

    def test_smaller_cell_moves_too_and_keeps_distance(self):
        self.draw('star.png', 1, 1)
        new, report, problems = sprite.plan_import(self.arc, self.folder)
        self.assertEqual(problems, [])
        ss = new['/ui.ssdata']
        rect = struct.unpack_from('<4H', ss, 0x18 + 4 * sprite.STATE_SIZE + sprite.STATE_RECT)
        self.assertEqual(rect[2:], (1, 1))
        x, y = rect[:2]                  # 4 empty pixels from label (0..5) and star's old place (8..9)
        self.assertTrue(x >= 14 or y >= 7, rect)

    def test_cell_with_unknown_state_fields_keeps_its_size(self):
        self.draw('odd.png', 5, 2)
        rc, log = self.run_import()
        self.assertEqual(rc, 1)
        self.assertIn('ui/odd.png la 5x2, o game 4x2', log)
        self.assertIn('0x10', log)
        self.assertFalse(os.path.exists(self.out))

    def test_no_room(self):
        self.draw('label.png', 30, 4)
        new, report, problems = sprite.plan_import(self.arc, self.folder)
        self.assertEqual(len(problems), 1)
        self.assertIn('ui.png khong con cho trong 30x4', problems[0])
        self.assertEqual(new, {})

    def test_free_spots_keeps_off_pixels_and_uses_blocks(self):
        from PIL import Image
        img = Image.new('RGBA', (2048, 64), (0, 0, 0, 0))
        img.putpixel((30, 3), (0, 0, 0, 1))                    # barely visible still counts
        spots = sprite.free_spots(img, [(0, 0, 10, 10)], [(16, 8), (5000, 1), (8, 8)])
        self.assertEqual(spots[1], None)
        for (x, y), (w, h) in ((spots[0], (16, 8)), (spots[2], (8, 8))):
            self.assertEqual((x % 4, y % 4), (0, 0))           # 2048 wide: 4-pixel blocks
            self.assertTrue(x >= 14 or y >= 14)                # clear of the taken rectangle
            self.assertFalse(x - 4 <= 30 < x + w + 4 and y - 4 <= 3 < y + h + 4)
        (ax, ay), (bx, by) = spots[0], spots[2]                # and clear of each other
        self.assertTrue(bx >= ax + 16 + 4 or ax >= bx + 8 + 4 or by >= ay + 8 + 4 or ay >= by + 8 + 4)
        self.assertEqual(spots[2], (16, 0))                    # the gap between the two is used


@unittest.skipUnless(HAVE_PIL, 'Pillow is not installed')
class SpriteCellNamesTest(unittest.TestCase):
    """win draws three cells, two of them from the same corner in two widths
    (as advwin's mat_adwin_win does); btn draws one."""

    def test_same_corner_gets_the_size(self):
        import shutil
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        parts = [('root', 0), ('win', 0), ('btn', 0)]
        states = [(0, 0, 0, 0, 0), (1, 0, 0, 8, 2), (1, 0, 0, 4, 2), (1, 0, 4, 4, 2), (2, 4, 2, 4, 2)]
        ss = make_ssdata(['ui.png'], parts, states, [[0, 1, 2, 3, 4]])
        arc = sprite.Archive(write_sprite_pair(os.path.join(d, 'jp'), [('/ui.rtex', make_rtex(8, 6, 8, 8, gradient)),
                                                                     ('/ui.ssdata', ss)]))
        self.assertEqual(sorted(c.file for c in arc.cells),
                         ['ui/btn.png', 'ui/win_0_0_4x2.png', 'ui/win_0_0_8x2.png', 'ui/win_0_4.png'])
        folder = os.path.join(d, 'anh')
        with contextlib.redirect_stdout(io.StringIO()):
            sprite.cmd_export(arc, folder)
        self.assertEqual(sprite.plan_import(arc, folder), ({}, [], []))


GAME_SSDATA = os.environ.get('RRLIB_SSDATA') or os.path.expanduser('~/Documents/Game/matsurika/romfs/spec_win/ssdata')


@unittest.skipUnless(HAVE_PIL and os.path.isdir(GAME_SSDATA), 'needs Pillow and the JP screens in ' + GAME_SSDATA)
class SpriteGameScreensTest(unittest.TestCase):
    """Every JP screen found (RRLIB_SSDATA, or the usual folder): each cell
    has a file of its own, and an export imported back untouched changes
    nothing. advwin's ten mat_adwin_win widths once shared one file."""

    def test_untouched_export_imports_nothing(self):
        import shutil
        from concurrent.futures import ThreadPoolExecutor
        from unittest import mock
        from PIL import Image
        screens = sorted(os.path.join(GAME_SSDATA, n) for n in os.listdir(GAME_SSDATA) if n.endswith('.memfs')
                         and os.path.isfile(os.path.join(GAME_SSDATA, n[:-6] + '.membody')))
        if not screens:
            self.skipTest('no .memfs/.membody pair in ' + GAME_SSDATA)
        save = Image.Image.save

        def quick(img, fp, format=None, **params):       # the pixels are checked, not the file size
            params.setdefault('compress_level', 1)
            return save(img, fp, format, **params)

        def run(memfs):
            arc = sprite.Archive(memfs)
            files = [c.file.lower() for c in arc.cells]     # a case-blind disk counts too
            folder = tempfile.mkdtemp()
            try:
                sprite.cmd_export(arc, folder)
                new, report, problems = sprite.plan_import(arc, folder)
            finally:
                shutil.rmtree(folder, ignore_errors=True)
            return arc.name, sorted(set(f for f in files if files.count(f) > 1)), sorted(new), report, problems
        with mock.patch.object(Image.Image, 'save', quick), contextlib.redirect_stdout(io.StringIO()), \
                ThreadPoolExecutor(4) as pool:
            results = list(pool.map(run, screens))
        for name, shared, new, report, problems in results:
            with self.subTest(screen=name):
                self.assertEqual(shared, [])
                self.assertEqual((new, report, problems), ([], [], []))


# A tiny exefs/main: text at 0, rodata at 0x1000, data at 0x2000, then .bss.
NOP, BL = 0xd503201f, 0x94000001
S1, S2, S3, S4, S5 = 0x1010, 0x1100, 0x1200, 0x1300, 0x1400      # rodata strings
RELA, DYN = 0x1800, 0x2000
TABLE = 0x20c0          # in .data: a struct whose first u32 is 'あ' then 0, like the glossary table
S6, S7 = 0x1500, 0x1600                     # a file name and a string handed to wcscmp: stay JP
JMPREL, SYMTAB, STRTAB, GOT, STUB = 0x1900, 0x1940, 0x1980, 0x20f8, 0x800    # the PLT stub of wcscmp


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


def make_main(compress=False, extra_relas=()):
    text = bytearray(0x1000)
    words = {0: 0x14000010, 4: 8,                                # b 0x40, MOD0 at 8
             0x40: exetext.adrp(0x40, S1, 1), 0x44: add_imm(1, 1, S1 & 0xfff),     # S1 by code
             0x48: adr(0x48, S4, 2),                                                # S4 by ADR
             0x4c: exetext.adrp(0x4c, S3, 3), 0x50: add_imm(3, 3, S3 & 0xfff),     # S3 is ASCII
             0x54: exetext.adrp(0x54, S5, 1), 0x58: BL, 0x5c: add_imm(0, 1, S5 & 0xfff),  # x1 lost in the call
             0x60: exetext.adrp(0x60, TABLE, 4), 0x64: add_imm(4, 4, TABLE & 0xfff),    # a table, not text
             0x70: exetext.adrp(0x70, S7, 0), 0x74: add_imm(0, 0, S7 & 0xfff),     # wcscmp(S7, ...)
             0x78: 0x94000000 | ((STUB - 0x78) >> 2),
             STUB: exetext.adrp(STUB, GOT, 16), STUB + 4: 0xf9400211 | ((GOT & 0xfff) // 8) << 10,
             STUB + 8: add_imm(16, 16, GOT & 0xfff), STUB + 12: 0xd61f0220}           # ldr x17, [x16]; br x17
    for i in range(0, 0x1000, 4):
        struct.pack_into('<I', text, i, words.get(i, NOP))
    text[8:12] = b'MOD0'
    struct.pack_into('<6i', text, 12, DYN - 8, 0x2100 - 8, 0x3100 - 8, 0, 0, 0)
    ro = bytearray(0x1000)
    for a, s in ((S1, '前回と同じ名前を使用します｡'), (S2, '\nよろしいですか？'), (S3, 'SYSTEM'),
                 (S4, 'クイックセーブしました｡'), (S5, '設定'), (S6, 'のぞき見.png'), (S7, '振り子')):
        b = u32text(s)
        ro[a - 0x1000:a - 0x1000 + len(b)] = b
    relas = ((0x2080, S2), (0x2088, S1), (0x2090, S2 + 4), (0x2098, S6)) + tuple(extra_relas)   # 0x2090: S2's tail
    for k, (off, add) in enumerate(relas):
        struct.pack_into('<QQq', ro, RELA - 0x1000 + 24 * k, off, 1027, add)
    struct.pack_into('<QQq', ro, JMPREL - 0x1000, GOT, 1 << 32 | 1026, 0)        # JUMP_SLOT, symbol 1
    struct.pack_into('<I', ro, SYMTAB - 0x1000 + 24, 1)
    ro[STRTAB - 0x1000:STRTAB - 0x1000 + 8] = b'\0wcscmp\0'
    data = bytearray(0x100)
    struct.pack_into('<16Q', data, 0, 7, RELA, 8, 24 * len(relas), 9, 24,
                     23, JMPREL, 2, 24, 6, SYMTAB, 5, STRTAB, 0, 0)
    struct.pack_into('<II', data, TABLE - 0x2000, ord('あ'), 0)
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
        self.assertIn(TABLE, exetext.code_refs(exe.img, exe.text_size, 0x1000, 0x2100))   # the code reaches it,
        self.assertNotIn(TABLE, exe.strings)                              # but text in .data is a struct
        self.assertEqual(sorted(k for k, _ in exe.refs[S1]), ['add', 'rela'])
        self.assertEqual(exe.refs[S4], [('adr', 0x48)])
        self.assertEqual(exe.strings[S2 + 4], 'よろしいですか？')

    def test_names_the_game_looks_up_stay_japanese(self):
        exe = exetext.Exe(make_main(compress=True))
        self.assertEqual(exetext.imports(exe.img, exe.text_size), {STUB: 'wcscmp'})
        self.assertEqual(exe.keys, {S6: ('のぞき見.png', 'file'), S7: ('振り子', 'compare')})
        rows = [dict(row=2, address=S6, jp='のぞき見.png', vi='nozokimi.png'),
                dict(row=3, address=S7, jp='振り子', vi='Con lắc')]
        writes, rep = exetext.plan(rows, exe, FONT)
        self.assertEqual((writes, [x['why'] for x in rep]), ({}, ['key', 'key']))

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

    def test_jp_text_that_sheets_mangled_still_matches(self):
        exe = exetext.Exe(make_main())
        exe.strings[S4] = "'then' が必要です"
        exe.strings[S1] = '"%ls"は既に定義されています'
        rows = [dict(row=2, address=S4, jp="then' が必要です", vi="then' cần có"),      # leading ' dropped in both
                dict(row=3, address=S1, jp='%lsは既に定義されています', vi='%ls đã có')]
        writes, rep = exetext.plan(rows, exe, FONT)
        self.assertEqual(writes, {S4: "'then' cハn có", S1: '%ls コã có'})
        self.assertEqual([x['why'] for x in rep], ['quotes', 'quotes'])
        other = exetext.plan([dict(row=2, address=S4, jp='then が必要', vi='x')], exe, FONT)[1]
        self.assertEqual(other[0]['why'], 'jp-mismatch')

    def test_book_titles_match_and_the_punctuation_list_stays_japanese(self):
        exe = exetext.Exe(make_main())
        exe.strings[S4] = '《爪》の炯眼持ち'
        exe.strings[S1] = ' ()-<=>[]_{}‐–—―‥…≪≫〈〉《》「」『』'
        rows = [dict(row=2, address=S4, jp='"爪"の炯眼持ち', vi='Huynh Nhan'),
                dict(row=3, address=S1, jp='()-<=>[]_{}‐–—―‥…≪≫〈〉""「」『』', vi='broken')]
        writes, rep = exetext.plan(rows, exe, FONT)
        self.assertEqual(writes, {S4: 'Huynh Nhan'})
        self.assertEqual([x['why'] for x in rep], ['brackets', 'symbol'])
        other = exetext.plan([dict(row=2, address=S4, jp='"牙"の炯眼持ち', vi='x')], exe, FONT)[1]
        self.assertEqual(other[0]['why'], 'jp-mismatch')

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


def adv_font(adv):
    """A font file whose glyphs carry advances only - all overflow.py reads."""
    def mk(pairs):
        m = font.Map()
        for k, v in pairs:
            m.insert(k, v)
        return m
    chars = sorted(adv)
    info = mk([('baseInfo', mk([('charWidth', 40)])), ('@fileType', 'rrlib/rfnt2'),
               ('gryphInfo', [font.IntArr([0, 0, 0, 60, 62, adv[c], 0, 7]) for c in chars]),
               ('charToIndex', mk([(c, i) for i, c in enumerate(chars)]))])
    return font.write(mk([('bin', [font.write(info)]), ('hasSeparateBody', False),
                          ('path', mk([('/fontdata.rson', 0)])), ('@fileType', 'rrlib/memfs')]))


def letters(px):
    """ASCII letters px wide, the space half that."""
    out = dict((chr(c), px) for c in range(0x21, 0x7f))
    out[' '] = px // 2
    return out


def scene(name, calls):
    """A script with GuideMess (text), NameMess (name, text) and SltAdd (text) calls."""
    strs = ['', 'GuideMess', 'NameMess', 'SltAdd', 'KW', '0', 'SLT_A']
    code = b''
    for c in calls:
        strs.append(c[-1])
        i = len(strs) - 1
        if c[0] == 'GuideMess':
            code += push(i) + push(1) + call(1)
        elif c[0] == 'NameMess':
            strs.append(c[1])
            code += push(len(strs) - 1) + push(i) + push(2) + call(2)
        else:
            code += push(5) + push(6) + push(i) + push(3) + call(3)
        code += push(4) + call(0)
    return make_kuv(name, strs, code), strs


class OverflowTest(unittest.TestCase):
    def setUp(self):
        self.std = overflow.Face('standard', letters(20))
        self.narrow = overflow.Face('extra', letters(10))

    def test_reads_lines_as_the_game_draws_them(self):
        self.assertEqual(overflow.blocks('Mở đầu\n#P(500,130)một\r\nhai#P(500,250)ba'),
                         [(None, None, ['Mở đầu', '']), (500, 130, ['một', 'hai']), (500, 250, ['ba'])])
        self.assertEqual(overflow.blocks('#P(1,2)a'), [(1, 2, ['a'])])
        self.assertEqual(overflow.variants('#T1Naya cười#T2${FirstName} cười#T0 rồi nói'),
                         [('#T1', 'Naya cười rồi nói'), ('#T2', '${FirstName} cười rồi nói')])
        self.assertEqual(overflow.variants('không tag'), [('', 'không tag')])
        self.assertEqual(overflow.visible('#C(TR,0xff0000ff)Đỏ#C(TR,prev)#KW ${FirstName}#R(あ)亜', 'Hoa'), 'Đỏ Hoa亜')
        self.assertEqual(self.std.width('ab c'), 70)
        self.assertEqual(self.std.width('ab漢'), 80)                     # a missing glyph counts a full cell
        self.assertEqual(self.std.missing('ab 漢'), {'漢'})

    def test_boxes(self):
        screen, log = overflow.BOX['screen'], overflow.BOX['backlog']
        self.assertAlmostEqual(screen.over(100, 1800), -15)               # 1800 + 105 ends inside 1920
        self.assertAlmostEqual(screen.over(200, 1800), 90)
        self.assertAlmostEqual(screen.over(200, 1800, margin=10), 100)
        self.assertAlmostEqual(log.room(), (1258 - 240) / 0.9)
        self.assertEqual(screen.room(1919, margin=50), 1.0)

    def test_measures_each_box_with_the_widest_font(self):
        def run(s, kind='story'):
            fd, tally, missing = overflow.Finding('A', 0, 'GuideMess', s), overflow.Tally(), set()
            hit = overflow.measure(fd, kind, s, [self.narrow, self.std], 'Naya', 0, missing, tally)
            return hit, dict((k, (round(v[0]), v[1])) for k, v in fd.worst.items()), tally
        self.assertEqual(run('#P(1700,100)' + 'a' * 12)[:2], (True, {'screen': (32, 'standard')}))
        hit, worst, tally = run('a' * 60)                                 # window and backlog
        self.assertEqual(worst, {'window': (56, 'standard'), 'backlog': (62, 'standard')})
        self.assertEqual(tally.over, {('standard', 'window'): 1, ('standard', 'backlog'): 1})
        self.assertEqual(tally.per_char('standard'), 20)
        self.assertEqual(tally.shrink('standard'), 6)                     # 1200 px in 1131 of room
        self.assertEqual(tally.shrink('extra'), 0)
        self.assertEqual(run('#P(500,1200)' + 'a' * 60)[1], {'backlog': (62, 'standard')})   # off-screen: logged only
        self.assertEqual(run('a' * 10)[:2], (False, {}))
        self.assertEqual(run('#T1' + 'a' * 10 + '#T2' + 'a' * 60)[1]['window'][0], 56)       # each variant alone
        self.assertEqual(run('b' * 40, 'choice')[1], {'choice': (80, 'standard')})

    def test_rewrap_fits_every_box_the_string_shows_in(self):
        words = ' '.join(['abcd'] * 30)
        out, note = overflow.rewrap(words, 'story', [self.std], 'Naya', 0)
        lines = out.split('\n')
        self.assertEqual([len(l.split(' ')) for l in lines], [12, 12, 6])  # 1131 px of backlog: 12 words of 90
        self.assertTrue(all(self.std.width(l) * 0.9 + 240 <= 1258 for l in lines))
        self.assertEqual(note, 'thêm 2 dòng')
        out, note = overflow.rewrap('#P(500,130)' + words, 'story', [self.std], 'Naya', 0)
        self.assertTrue(out.startswith('#P(500,130)abcd'))
        self.assertIn('xem câu nằm ngay dưới', note)
        self.assertEqual(overflow.rewrap('#T1a#T2b', 'story', [self.std], 'Naya', 0), ('', ''))
        self.assertEqual(overflow.rewrap('#P(1,1)a#P(1,60)b', 'story', [self.std], 'Naya', 0), ('', ''))

    def test_finds_overflow_in_a_mod_folder(self):
        import shutil
        raw, _ = scene('EV01.tat', [('GuideMess', '#P(1700,100)' + 'a' * 12), ('NameMess', '${FirstName}', 'a' * 60),
                                    ('SltAdd', '【N1】' + 'b' * 40), ('GuideMess', 'ngắn'), ('GuideMess', '#P(1900,100)aaaa')])
        d = tempfile.mkdtemp()
        try:
            write_pair(os.path.join(d, 'romfs', 'common'), [raw], [('/_bytecode/EV01.tatc', 0x30, [0, len(memfs.rz(raw))])])
            fonts = os.path.join(d, 'romfs', 'spec_win', 'font')
            os.makedirs(fonts)
            for n, px in (('standard', 20), ('extra', 18), ('extra2', 16), ('extra3', 10)):
                with open(os.path.join(fonts, n + '.font.memfs'), 'wb') as f:
                    f.write(adv_font(letters(px)))
            out = os.path.join(d, 'tran.csv')
            log = io.StringIO()
            with contextlib.redirect_stdout(log):
                self.assertEqual(overflow.main(['--mod', d, '--csv', out]), 0)
            log = log.getvalue()
            self.assertIn('tu dien: khong co exefs/main - bo qua', log)
            self.assertIn('font khong co: ắ', log)
            with open(out, encoding='utf-8-sig', newline='') as f:
                rows = list(csv.DictReader(f))
            self.assertEqual([(r['index'], r['call'], r['over_px'], r['font'], r['fonts']) for r in rows],
                             [('10', 'SltAdd', '80', 'standard', 'chỉ standard'),
                              ('12', 'GuideMess', '64', 'standard', 'mọi font'),       # too far right for any font
                              ('8', 'NameMess', '62', 'standard', 'chỉ standard'),
                              ('7', 'GuideMess', '32', 'standard', 'chỉ extra, standard')])
            self.assertIn('tran o moi font            1 cau', log)
            self.assertIn('chi tran o mot so font     3 cau', log)
            self.assertIn('(standard 3, extra 1, extra2 0, extra3 0)', log)
            self.assertEqual(rows[2]['box'], 'backlog +62 px (1 dòng); khung thoại +56 px (1 dòng), khung ước lượng')
            self.assertEqual(rows[3]['suggestion'], '#P(1700,100)' + 'a' * 12)   # one word: nothing to break
            log = io.StringIO()
            with contextlib.redirect_stdout(log):
                overflow.main(['--mod', d, '--font', 'extra3', '--csv', out])
            self.assertIn('-> %s (1 cau)' % out, log.getvalue())
            self.assertNotIn('kieu tran', log.getvalue())                     # one font: nothing to compare
            with self.assertRaises(SystemExit):
                overflow.main(['--mod', d, '--fonts', d])                 # no font there
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_glossary_descriptions_from_the_program(self):
        raw = make_main(extra_relas=((TABLE + 8, S4), (TABLE + 16, S1)))
        exe = exetext.Exe(raw)
        self.assertEqual(overflow.glossary(exe, TABLE), [(TABLE, S4, S1)])
        face = overflow.Face('extra2', letters(20))
        self.assertEqual(overflow.check_glossary(exe, face, lambda t: t, 0, set(), TABLE), ([], 1, 0))  # JP fits
        desc = 'Ngắn.\n' + ' '.join(['abcd'] * 20)
        new = exetext.Exe(exetext.build(exe, {S1: desc, S4: 'Từ'})[0])
        found, n, done = overflow.check_glossary(new, face, lambda t: t, 0, set(), TABLE)
        self.assertEqual((n, done, len(found)), (1, 1, 1))
        fd = found[0]
        self.assertEqual((fd.where, fd.index, fd.call), ('exefs/main', '0x%x' % S1, 'từ điển: Từ'))
        self.assertEqual(fd.fonts_text(), 'mọi font')                           # the glossary has one font
        self.assertAlmostEqual(fd.worst['glossary'][0], 576 + 1790 * 1.05 - 1362)
        self.assertEqual([len(l.split(' ')) for l in fd.suggestion.split('\n')[1:]], [8, 8, 4])   # 748 px of paper
        self.assertEqual(fd.suggestion.split('\n')[0], 'Ngắn.')                               # its own break kept


class GlossaryKeyTest(unittest.TestCase):
    """The script key (Mov GAMESTR_DictWords) must be the glossary term exactly."""

    def test_exetext_reads_the_glossary_table(self):
        exe = exetext.Exe(make_main(extra_relas=((TABLE + 8, S4), (TABLE + 16, S1))))
        self.assertEqual(exetext.glossary(exe, TABLE), [(TABLE, S4, S1)])
        self.assertEqual(exetext.glossary(exetext.Exe(make_main()), TABLE), [])    # no term pointer: no table

    def test_dict_keys_are_the_values_of_mov_dictwords(self):
        import shutil
        strs = ['', 'Mov', applysheet.DICT_VAR, 'クイックセーブしました｡', 'GAMEFLAG_X', '1', 'GuideMess', '一']
        code = (push(2) + push(3) + push(1) + call(2) +       # Mov GAMESTR_DictWords, key
                push(4) + push(5) + push(1) + call(2) +       # another Mov
                push(7) + push(6) + call(1))
        raw = make_kuv('A.tat', strs, code)
        d = tempfile.mkdtemp()
        try:
            write_pair(os.path.join(d, 'jp'), [raw], [('/_bytecode/A.tatc', 0x30, [0, len(memfs.rz(raw))])])
            jp = memfs.Archive(*patch.find_pair(os.path.join(d, 'jp')))
            self.assertEqual(applysheet.dict_keys(jp), {('A.tat', 3)})
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_keys_follow_the_title_exetext_writes(self):
        import shutil
        d = tempfile.mkdtemp()
        try:
            main = os.path.join(d, 'main')
            with open(main, 'wb') as f:
                f.write(make_main(extra_relas=((TABLE + 8, S4), (TABLE + 16, S1))))
            lst = os.path.join(d, 'exe.csv')
            with open(lst, 'w', encoding='utf-8', newline='') as f:
                csv.writer(f).writerows([['address', 'refs', 'jp_text', 'vi_text', 'note'],
                                         ['0x%x' % S4, '', 'クイックセーブしました｡', '"Lưu" nhanh  ', '']])
            old = exetext.GLOSSARY
            exetext.GLOSSARY = TABLE
            try:
                titles = applysheet.glossary_keys(main, lst, FONT)
                with open(lst, 'w', encoding='utf-8', newline='') as f:
                    csv.writer(f).writerows([['address', 'jp_text', 'vi_text'], ['0x%x' % S4, 'クイックセーブしました｡', '']])
                untranslated = applysheet.glossary_keys(main, lst, FONT)
            finally:
                exetext.GLOSSARY = old
            # the term as exetext writes it: quotes, spaces and letters exactly as there
            self.assertEqual(titles, {'クイックセーブしました｡': ('"Lゔu" nhanh  ', '"Lưu" nhanh  ')})
            self.assertEqual(untranslated, {'クイックセーブしました｡': ('クイックセーブしました｡', None)})
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_read_rows_finds_the_exe_tab_of_the_whole_sheet(self):
        try:
            import openpyxl
        except ImportError:
            self.skipTest('openpyxl')
        wb = openpyxl.Workbook()
        wb.active.title = 'Index'
        wb.active.append(['index', 'sheet_name'])
        ws = wb.create_sheet('exe')
        ws.append(['address', 'refs', 'jp_text', 'vi_text', 'note'])
        ws.append(['0x%x' % S4, '', 'クイックセーブしました｡', 'Đã lưu.', None])
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 'sheet.xlsx')
            wb.save(p)
            self.assertEqual(exetext.read_rows(p), [dict(row=2, address=S4, jp='クイックセーブしました｡', vi='Đã lưu.')])

    def test_plan_writes_the_title_whatever_the_cell_says(self):
        js = {'A.tat': ['', 'Mov', applysheet.DICT_VAR, '石陰村', '蛍', '四凶']}
        keys = {('A.tat', 3): ('Làng Thヒch Âm', 'Làng Thạch Âm'),
                ('A.tat', 4): ('Đom đóm', 'Đom đóm'),
                ('A.tat', 5): ('四凶', None)}                     # title left Japanese in the exe
        rows = [sheet_row(2, 3, '石陰村', 'Thạch Âm Thôn'), sheet_row(3, 4, '蛍', 'Đom đóm'),
                sheet_row(4, 5, '四凶', 'Tứ Hung'), sheet_row(5, 3, '石陰村', 'Thạch Âm Thôn')]
        writes, rep = applysheet.plan(rows, js, {'ạ': 'ヒ'}, set('Đóâ'), keys)
        self.assertEqual(writes['A.tat'], {3: 'Làng Thヒch Âm', 4: 'Đom đóm', 5: '四凶'})
        self.assertEqual([x.get('key') for x in rep], [('Thạch Âm Thôn', 'Làng Thạch Âm'), None, ('Tứ Hung', None)])
        with tempfile.TemporaryDirectory() as d:
            applysheet.write_report(os.path.join(d, 'r.csv'), rep)
            with open(os.path.join(d, 'r.csv'), encoding='utf-8-sig') as f:
                notes = [row[-1] for row in csv.reader(f)][1:]
        self.assertEqual(len(notes), 2)
        self.assertIn('"Làng Thạch Âm"', notes[0])
        self.assertIn('giữ khoá tiếng Nhật', notes[1])


def make_jp_main(text_size=exepatch.JP_TEXT_SIZE, compress=False, pad=0, change=None):
    """A main laid out like JP 1.0.0 (.rodata at 0x2f2000) holding the JP
    instructions exepatch.py replaces; routines' free space filled with
    `pad` (0 = the JP original, NOP = the 02/10 main, whose read-redirect
    caves hold their code: a site's last `old` words); `change` = {address:
    word} overrides."""
    text = bytearray(text_size)
    for p in exepatch.PATCHES:
        for s in p.sites:
            if s.at + 4 * len(s.new) <= text_size:
                if s.at < exepatch.JP_TEXT_SIZE:
                    words = s.old[0]
                else:
                    words = s.old[-1] if pad == exepatch.NOP else (pad,) * len(s.new)
                struct.pack_into('<%dI' % len(words), text, s.at, *words)
    for a, w in (change or {}).items():
        struct.pack_into('<I', text, a, w)
    segs = ((0, bytes(text)), (exepatch.TEXT_END, b'R' * 0x100), (exepatch.TEXT_END + 0x1000, b'D' * 0x100))
    h = bytearray(0x100)
    h[:4] = b'NSO0'
    struct.pack_into('<I', h, 0x0C, 0x3f if compress else 0x38)
    struct.pack_into('<I', h, 0x1C, 0x100)
    struct.pack_into('<I', h, 0x2C, 1)
    struct.pack_into('<I', h, 0x3C, 0x1000)
    pos, body = 0x101, b''
    for k, (moff, seg) in enumerate(segs):
        packed = lz4_literals(seg) if compress else seg
        struct.pack_into('<3I', h, 0x10 + 0x10 * k, pos, moff, len(seg))
        struct.pack_into('<I', h, 0x60 + 4 * k, len(packed))
        pos += len(packed); body += packed
    return bytes(h) + b'\0' + body


class ExePatchTest(unittest.TestCase):
    def run_cmd(self, raw, cmd='apply', apply=True):
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, 'main')
            with open(src, 'wb') as f:
                f.write(raw)
            out = os.path.join(d, 'out')
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = exepatch.cmd_check(src) if cmd == 'check' else exepatch.cmd_write(src, out, apply, cmd == 'revert')
            path = os.path.join(out, 'main')
            written = open(path, 'rb').read() if os.path.exists(path) else None
        return rc, buf.getvalue(), written

    def patch(self, name):
        return next(p for p in exepatch.PATCHES if p.name == name)

    def test_routines(self):
        at = exepatch.FLO_CAVE
        cave = exepatch.flo_cave()
        self.assertEqual(at + 4 * len(cave), exepatch.TEXT_END)
        fmt = (exepatch.flo_format() - at) // 4
        self.assertEqual(''.join(map(chr, cave[fmt:fmt + 8])), '%ls\n%ls\0')
        entry = (exepatch.ev_entry() - at) // 4
        self.assertEqual(cave[entry], 0xd100a3a9)                                    # sub x9, x29, #40
        self.assertEqual(exepatch.branch_target(cave[entry + 1], at + 4 * entry + 4), at + 4)
        self.assertEqual(exepatch.fmov_s(0, 0.875), 0x1e2d9000)                      # llvm-mc
        r, rat = exepatch.route_cave(), exepatch.ROUTE_CAVE
        nat, n = exepatch.NAME_CAVE, exepatch.name_cave()
        self.assertEqual((rat + 4 * len(r), nat + 4 * len(n)), (nat, 0x2f1f00))     # back to back, up to the 02/10 cave
        self.assertEqual(exepatch.branch_target(n[1], nat + 4), 0x2f07e0)           # memcpy
        self.assertEqual(n[2:8], [0xd0001568, 0xf9422508, 0xf9400101, 0x52800100, 0x52800022,  # llvm-mc: adrp x8 0x59f000;
                                  exepatch.bl(nat + 28, 0x1653e0)])                 # ldr x8,[x8,#0x448]; ldr x1,[x8]; w0 8; w2 1
        self.assertEqual(n[9], 0xd65f03c0)                                           # ret
        self.assertEqual(exepatch.branch_target(r[2], rat + 8), 0x2f0b00)           # std::wstring::find
        self.assertEqual(r[1], 0x52800501)                                           # mov w1, #'('
        self.assertEqual(exepatch.branch_target(r[16], rat + 64), rat + 40)         # b L10
        self.assertEqual(r[17], 0xd65f03c0)                                          # ret
        ev = {s.at: s for s in self.patch('ev-route-split').sites}
        self.assertEqual(exepatch.branch_target(ev[0x887d8].old[0][0], 0x887d8), 0x2f0b00)
        self.assertEqual(exepatch.branch_target(ev[0x887d8].new[0], 0x887d8), rat)

    def test_route_first_stub_and_branches(self):
        sites = {s.at: s for s in self.patch('route-first').sites}
        init, nl, end = sites[0x1654f0], sites[0x165568], sites[0x165604]
        # the JP words: the call that gave "\n" its ルート, the branch to the concatenation
        self.assertEqual(exepatch.branch_target(nl.old[0][0], 0x165568), 0x2f0b40)      # wstring::insert
        self.assertEqual(nl.new, (exepatch.NOP,))
        self.assertEqual(end.old[0], (0xb40003e0,))                                      # llvm-mc: cbz x0, 0x165680
        self.assertEqual(end.new, (exepatch.cbz_x(0, 0x165604, 0x165500),))
        n = init.new
        self.assertEqual(len(n), 24)
        self.assertEqual(n[:3], (0xaa0803f3, 0x381d03bf, 0x381e83bf))                    # mov x19,x8; sturb wzr [x29-48], [x29-24]
        self.assertEqual(exepatch.branch_target(n[3], 0x1654fc), 0x16552c)               # hop over the stub
        self.assertEqual(n[4:7], (0xd100c3a0, 0xaa1f03e1, 0xf940aea2))                   # x0 = name, x1 = 0, x2 = [x21,#344]
        self.assertEqual(exepatch.branch_target(n[7], 0x16550c), 0x2f0b40)               # insert(0, ルート)
        self.assertEqual(exepatch.branch_target(n[8], 0x165510), 0x165680)               # on to the concatenation
        self.assertEqual(n[15], init.old[0][15])                                         # adrp x21 stays at 0x16552c
        self.assertEqual((n[21], n[22]), (init.old[0][21], init.old[0][22]))             # the table loads stay
        # nothing past the hop is reached except through the stub: no store into the dummy buffer is left
        self.assertNotIn(0xa9012809, n)
        self.assertEqual(sum(1 for w in n if w == exepatch.NOP), 6 + 5 + 1)

    def test_losa_route_routine(self):
        at, w = exepatch.LOSA_ROUTE, exepatch.losa_route()
        self.assertEqual(len(w), len(exepatch.LOSA_JP))
        self.assertEqual(exepatch.branch_target(exepatch.LOSA_JP[10], at + 40), 0xa55c0)  # JP: its slot-state check
        self.assertEqual((w[0], w[42]), (0xaa1e03ef, 0xd65f01e0))                         # mov x15, x30 ... ret x15
        for i in (10, 14, 23, 31):
            self.assertEqual(exepatch.branch_target(w[i], at + 4 * i), at + 4 * 43)       # bl PFX
        # llvm-mc: adrp x14, 0x59e000; ldr x14, [x14, #4072] / adrp x7, 0x551000; add x7, x7, #2360 / adr x13, +108
        self.assertEqual(w[7:9] + w[17:19] + [w[28]], [0xf000278e, 0xf947f5ce, 0xd0002527, 0x9124e0e7, 0x1000036d])
        self.assertEqual((w[9], w[13]), (0xf940adc3, 0xf94119c3))                           # entries 43 (ルート), 70 (二角獣)
        names = [''.join(chr(c) for c in w[i:i + 5] if c) for i in range(55, len(w), 5)]
        self.assertEqual(names, list(exepatch.LOSA_JP_NAMES))
        # leaf: no stack, nothing callee-saved (x16-x30) written except the BLs' x30
        for x in w[:55]:
            if x & 0x7c000000 != 0x14000000 and x & 0xff000000 not in (0x34000000, 0x36000000, 0xb4000000,
                                                                      0xb5000000, 0x54000000) and x != 0xd65f01e0:
                self.assertTrue(x & 31 < 16 or x & 31 == 31, hex(x))                     # 31: cmp's xzr

    def test_hint_hide_slides(self):
        sites = self.patch('hint-hide').sites
        self.assertEqual(len(sites), 6)
        for s in sites:
            self.assertEqual(s.old, [(0x1e282801,)])                                   # llvm-objdump: fadd s1, s0, s8
            self.assertEqual(s.new, (0x1e202801,))                                     # fadd s1, s0, s0
        # no address shared with another patch (the flowchart's slide is flo-hint-bottom's)
        others = set(s.at for p in exepatch.PATCHES if p.name != 'hint-hide' for s in p.sites)
        self.assertFalse(others & set(s.at for s in sites))
        self.assertIn(0xae91c, others)

    def test_apply_revert_round_trip(self):
        for pad, size in ((0, exepatch.JP_TEXT_SIZE), (exepatch.NOP, exepatch.TEXT_END)):
            raw = make_jp_main(size, compress=True, pad=pad)
            rc, out, new = self.run_cmd(raw)
            self.assertEqual(rc, 0, out)
            after = exepatch.Main(new)
            self.assertEqual(after.text_size, exepatch.TEXT_END)
            self.assertEqual([p.state(after.img) for p in exepatch.PATCHES], ['applied'] * len(exepatch.PATCHES))
            self.assertTrue(exepatch.only_sites_differ(after.img, exepatch.Main(raw).img, exepatch.PATCHES))
            rc, out, again = self.run_cmd(new)
            self.assertEqual((rc, again), (0, None))
            rc, out, back = self.run_cmd(new, 'revert')
            self.assertEqual(rc, 0, out)
            self.assertEqual(exepatch.Main(back).img, exepatch.Main(make_jp_main(exepatch.TEXT_END, pad=exepatch.NOP)).img)

    def test_shared_routine_and_older_cave(self):
        raw = make_jp_main(exepatch.TEXT_END, pad=exepatch.NOP)
        img = bytearray(exepatch.Main(raw).img)
        flo, ev = self.patch('flo-title-rows'), self.patch('ev-title-rows')
        for s in flo.sites:                                     # 2026-11-13 21:17: the routine without ev's entry
            words = exepatch.FLO_CAVE_V2 if s.shared else s.new
            struct.pack_into('<%dI' % len(words), img, s.at, *words)
        v2 = exepatch.Main(raw).write(img)
        self.assertEqual((flo.state(exepatch.Main(v2).img), ev.state(exepatch.Main(v2).img)), ('outdated', 'missing'))
        rc, out, new = self.run_cmd(v2)
        self.assertEqual(rc, 0, out)
        self.assertEqual((flo.state(exepatch.Main(new).img), ev.state(exepatch.Main(new).img)), ('applied', 'applied'))

    def test_other_instructions_are_refused(self):
        raw = make_jp_main(change={0x887d8: exepatch.bl(0x887d8, 0x2f0b10)})
        rc, out, new = self.run_cmd(raw)
        self.assertEqual((rc, new), (1, None))
        self.assertIn('0x887d8', out)
        with self.assertRaises(SystemExit):
            self.run_cmd(make_jp_main(0x2f0000))                # another game version


if __name__ == '__main__':
    unittest.main(verbosity=1)
