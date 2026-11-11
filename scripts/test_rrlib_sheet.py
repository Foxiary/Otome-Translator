#!/usr/bin/env python3
"""Tests for engines/rrlib/tools/extractsheet.py on a synthetic script archive -
no game data needed. The workbook round trip runs only where openpyxl is."""
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'engines', 'rrlib', 'tools'))

import extractsheet  # noqa: E402
import memfs         # noqa: E402
import rson          # noqa: E402
from test_rrlib import call, make_kuv, push, write_pair  # noqa: E402

try:
    import openpyxl  # noqa: F401
    HAVE_XLSX = True
except ImportError:
    HAVE_XLSX = False


def sample():
    strs = ['NameMess', 'GuideMess', 'SltAdd', 'Mov', 'KW',          # 0-4
            'ルヲ', '「行こう」\r\n　まだ', '${FirstName}', '「……！」',  # 5-8
            '#P(500,130)夜が明ける。#KW\n\n', '……', '0', 'SLT_A', '帰る',  # 9-13
            'GAMESTR_DictWords', '四凶', '　　', '#P(520,1200)「天地」\n']  # 14-17
    code = (push(5) + push(6) + push(0) + call(2) + push(4) + call(0) +       # dialogue
            push(7) + push(8) + push(0) + call(2) +                          # heroine's 「……！」: left out
            push(9) + push(1) + call(1) +                                    # narration
            push(10) + push(1) + call(1) +                                   # dots: left out
            push(11) + push(12) + push(13) + push(2) + call(3) +             # choice
            push(14) + push(15) + push(3) + call(2) +                        # glossary key
            push(16) + push(17) + push(0) + call(2) +                        # blank speaker
            push(5) + push(6) + push(0) + call(2))                           # same string again
    return make_kuv('A.tat', strs, code)


class ExtractTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        raw = sample()
        other = make_kuv('B.tat', ['GuideMess', '終わり'], push(1) + push(0) + call(1))
        self.dir = os.path.join(self.tmp, 'jp')
        size = len(memfs.rz(raw))
        write_pair(self.dir, [raw, other], [('/_bytecode/B.tatc', 0x20, [size, len(memfs.rz(other))]),
                                            ('/_bytecode/A.tatc', 0x20, [0, size])])
        self.arc = memfs.Archive(os.path.join(self.dir, 'script.memfs'), os.path.join(self.dir, 'script.membody'))

    def test_rows(self):
        out = extractsheet.extract(self.arc)
        self.assertEqual(list(out), ['B.tat', 'A.tat'])          # script.memfs order
        rows = out['A.tat']
        self.assertEqual([(r['command'], r['category'], r['const_index']) for r in rows], [
            ('NameMess', 'dialogue', 6), ('GuideMess', 'narration', 9), ('SltAdd', 'choice', 13),
            ('Mov', 'system_optional', 15), ('NameMess', 'dialogue', 17), ('NameMess', 'dialogue', 6)])
        self.assertEqual([r['record_id'] for r in rows], list(range(2, 8)))
        d = rows[0]
        self.assertEqual(d['jp_text'], '「行こう」\n\n　まだ')
        self.assertEqual(d['speaker_jp'], 'ルヲ')
        self.assertEqual(d['source_preview_jp'], 'ルヲ\n「行こう」\n\n　まだ')
        self.assertEqual(d['all_args_json'], '["ルヲ", "「行こう」\\r まだ"]')
        self.assertEqual(d['opcode_bytes_hex'], '0e 00 00 00 05 0e 00 00 00 06 0e 00 00 00 00 2b 2c 02 00')
        self.assertEqual(d['block_index'], 1)
        self.assertEqual(d['rz_kind'], '0000')
        raw = self.arc.raw('/_bytecode/A.tatc')
        h = memfs.kuv.parse(raw)[0]
        self.assertEqual(int(d['call_offset'], 16), h[18] + 15)
        self.assertEqual(int(d['push_offsets_json'][2:-2].split('", "')[0], 16), h[18])
        tab = raw[int(d['const_offset'], 16):].decode('utf-16le', 'replace')
        self.assertTrue(tab.startswith('「行こう」'))
        self.assertEqual(rows[1]['all_args_json'], '["#P(500,130)夜が明ける。#KW "]')
        self.assertEqual((rows[2]['choice_index'], rows[2]['choice_label'], rows[2]['source_preview_jp']),
                         ('0', 'SLT_A', 'SLT_A\n帰る'))
        self.assertEqual(rows[3]['arg_position'], 1)
        self.assertIsNone(rows[4]['speaker_jp'])
        self.assertEqual(rows[4]['speaker_const_index'], 16)

    def test_carry_over_takes_each_rows_own_cell(self):
        out = extractsheet.extract(self.arc)
        cells = {('A.tat', 6): [{'vi_text': 'Đi thôi', 'speaker_vi': 'Ruwo'}, {'vi_text': 'Đi nào'}],
                 ('A.tat', 99): [{'vi_text': 'mất'}]}
        n, lost = extractsheet.carry_over(out, cells)
        rows = out['A.tat']
        self.assertEqual((rows[0]['vi_text'], rows[0]['speaker_vi'], rows[5]['vi_text']), ('Đi thôi', 'Ruwo', 'Đi nào'))
        self.assertEqual((n, lost), (2, [('A.tat', 99)]))

    @unittest.skipUnless(HAVE_XLSX, 'openpyxl missing')
    def test_workbook_reads_back_as_a_sheet(self):
        import sheetfix
        out = extractsheet.extract(self.arc)
        path = os.path.join(self.tmp, 'sheet.xlsx')
        extractsheet.write_book(path, out, {'SYSTEM': 'note'})
        rows = sheetfix.read_sheet(path)
        self.assertEqual(len(rows), 7)
        self.assertEqual(rows[0]['script'], 'A.tat')       # tabs sorted by name
        cells, routes, _ = extractsheet.read_old(path)
        self.assertEqual(routes, {'SYSTEM': 'note'})
        self.assertIn(('B.tat', 1), cells)


if __name__ == '__main__':
    unittest.main()
