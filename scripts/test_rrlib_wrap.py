# -*- coding: utf-8 -*-
"""Wrapping story text by pixel width (overflow.fit_wrap, applysheet --fonts)
on synthetic fonts: a face is a table of advances, nothing else."""
import csv
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'engines', 'rrlib', 'tools'))

import applysheet  # noqa: E402
import overflow  # noqa: E402
import tags      # noqa: E402


def letters(px):
    """ASCII letters px wide, the space half that."""
    out = dict((chr(c), px) for c in range(0x21, 0x7f))
    out[' '] = px // 2
    return out


def row(n, ci, jp, vi):
    return dict(tab='A', row=n, rid=n, cmd='GuideMess', script='A.tat', ci=ci, jp=jp, vi=vi)


LOG = (1258 - 240) / 0.9        # the backlog's room in font px, the tightest box of a window line


class FitWrapTest(unittest.TestCase):
    def setUp(self):
        self.narrow = overflow.Face('extra2', letters(10))
        self.wide = overflow.Face('standard', letters(22))

    def width(self, line, faces):
        return overflow.line_width(line, faces, 'Naya')

    def test_lines_that_fit_keep_the_62_character_wrap(self):
        t = '\n' + ' '.join(['abcd'] * 30) + '\n\n#P(500,130)' + ' '.join(['xy'] * 40) + '\n'
        self.assertEqual(overflow.fit_wrap(t, [self.narrow]), (tags.builder_wrap(t), 0, 0))

    def test_a_line_too_wide_for_the_backlog_is_wrapped_shorter(self):
        t = ' '.join(['abcd'] * 36)                       # 62 characters = 12 words, 1177 px at 22 px
        self.assertEqual([l.count('abcd') for l in tags.builder_wrap(t).split('\n')], [12, 12, 12])
        out, added, _ = overflow.fit_wrap(t, [self.narrow, self.wide])
        lines = out.split('\n')
        self.assertEqual([l.count('abcd') for l in lines], [11, 11, 11, 3])
        self.assertEqual(added, 1)
        self.assertTrue(all(self.width(l, [self.wide]) <= LOG for l in lines))

    def test_a_p_line_gets_the_room_from_its_x_to_the_screen_edge(self):
        face = overflow.Face('standard', letters(20))
        t = 'ab ab\n#P(1500,100)' + ' '.join(['ab'] * 20) + '\n' + ' '.join(['ab'] * 10)
        out, added, _ = overflow.fit_wrap(t, [face])
        lines = out.split('\n')
        # (1920 - 1500) / 1.05 = 400 px: 8 words of 40 px and their spaces
        self.assertEqual(lines[0], 'ab ab')                                   # before any #P: the window
        self.assertEqual([l.count('ab') for l in lines[1:]], [8, 8, 4, 8, 2])  # the next line stays at x 1500
        self.assertTrue(lines[1].startswith('#P(1500,100)ab'))
        self.assertEqual(added, 3)

    def test_a_p_block_is_refilled_before_it_grows(self):
        """EV01_0007_01 #97: wrapping only the too-wide paragraph gave the #P
        block a fourth line, on the row of the next #P block."""
        face = overflow.Face('standard', letters(20))
        # (1920 - 870) / 1.05 = 1000 px: 21 words of 'ab' are 62 characters and 1040 px
        head = '#P(870,700)' + ' '.join(['ab'] * 21)
        t = head + '\n' + ' '.join(['cd'] * 3) + '\n#P(230,880)ef'
        out, added, _ = overflow.fit_wrap(t, [face])
        self.assertEqual(added, 0)
        self.assertEqual(out.split('\n'), ['#P(870,700)' + ' '.join(['ab'] * 20), 'ab cd cd cd', '#P(230,880)ef'])
        # a block that cannot keep its height grows, paragraph by paragraph
        out, added, _ = overflow.fit_wrap(head + '\n' + ' '.join(['cd'] * 20), [face])   # 41 words: 3 lines either way
        self.assertEqual(added, 1)
        self.assertEqual(out.split('\n')[1], 'ab')

    def test_without_a_character_count_each_line_is_filled_to_its_room(self):
        t = ' '.join(['abcd'] * 30)            # 62 characters: 12, 12, 6 words; 1131 px of backlog holds 25 at 10 px
        out, added, merged = overflow.fit_wrap(t, [self.narrow], chars=0)
        self.assertEqual([l.count('abcd') for l in out.split('\n')], [25, 5])
        self.assertEqual((added, merged), (-1, 0))
        self.assertTrue(all(self.width(l, [self.narrow]) <= LOG for l in out.split('\n')))

    def test_a_string_over_three_lines_gets_its_breaks_joined(self):
        t = 'aa bb\ncc dd\nee ff\ngg hh'
        self.assertEqual(overflow.fit_wrap(t, [self.narrow], chars=0), (t, 0, 0))
        self.assertEqual(overflow.fit_wrap(t, [self.narrow], chars=0, max_rows=3), ('aa bb cc dd ee ff gg hh', -3, 1))
        # blocks are refilled one at a time, a #P block apart from the text before it, until it fits
        p = 'aa\nbb\n#P(500,130)cc\ndd'
        self.assertEqual(overflow.fit_wrap(p, [self.narrow], chars=0, max_rows=3)[0], 'aa bb\n#P(500,130)cc\ndd')
        # a blank line is the translator's spacing: that block is left as it is
        self.assertEqual(overflow.fit_wrap('aa\n\nbb\ncc\ndd', [self.narrow], chars=0, max_rows=3)[2], 0)

    def test_every_name_variant_gets_lines_that_fit(self):
        """EV01_0009_01 #251: a break inside the #T2 part does not exist in the
        #T1 text, which then ran on as one line, 779 px past the window. Each
        variant is wrapped on its own and all breaks go in."""
        face = overflow.Face('standard', letters(20))
        t = ('#T0' + ' '.join(['ab'] * 12) + ' #T1' + ' '.join(['cd'] * 6) + ' #T2' + ' '.join(['ef'] * 6)
             + ' #T0' + ' '.join(['gh'] * 12))
        for chars in (None, 0):
            out = overflow.fit_wrap('#P(1100,100)' + t, [face], chars=chars)[0]
            room = (1920 - 1100) / 1.05
            for _, v in overflow.variants(out):
                for line in v.split('\n'):
                    self.assertLessEqual(overflow.line_width(line, [face], 'Naya'), room, (chars, line))
        # a #T1 sentence on a line of its own, then the #T2 one (EV06_0009_01 #158)
        t = '#T1' + ' '.join(['cd'] * 30) + '\n#T2' + ' '.join(['ef'] * 30)
        out = overflow.fit_wrap(t, [face], chars=0)[0]
        for _, v in overflow.variants(out):
            self.assertTrue(all(overflow.line_width(l, [face], 'Naya') <= LOG for l in v.split('\n')))

    def test_a_long_name_part_is_written_as_two_wrapped_variants(self):
        """EV06_0009_01 #158: a whole sentence inside #T1 and again inside #T2
        has no shared space to break at."""
        face = overflow.Face('standard', letters(20))
        t = '#P(500,100)#T1' + ' '.join(['cd'] * 30) + '#T2' + ' '.join(['ef'] * 30) + '#T0 gh'
        out, added, _ = overflow.fit_wrap(t, [face], chars=0)
        self.assertTrue(out.startswith('#P(500,100)#T1cd'))
        self.assertEqual(out.count('#P('), 1)
        got = dict(overflow.variants(out))
        self.assertEqual(got['#T1'].replace('\n', ' '), '#P(500,100)' + ' '.join(['cd'] * 30) + ' gh')
        self.assertEqual(got['#T2'].replace('\n', ' '), '#P(500,100)' + ' '.join(['ef'] * 30) + ' gh')
        for v in got.values():
            self.assertTrue(all(overflow.line_width(l, [face], 'Naya') <= LOG for l in v.split('\n')))
        self.assertEqual(overflow.rows(out), 2)             # what each variant shows, not the two added up

    def test_rows_counts_what_the_backlog_shows(self):
        self.assertEqual(overflow.rows('a\n#P(1,2)b\n\nc'), 3)
        self.assertEqual(overflow.rows('#T1a\nb#T2c#T0\nd'), 3)         # #T1: a / b / d
        self.assertEqual(overflow.rows('#KW\na'), 1)

    def test_an_off_screen_line_only_has_the_backlog(self):
        face = overflow.Face('standard', letters(20))
        t = '#P(1500,1200)' + ' '.join(['ab'] * 20)          # hidden on the screen, logged only
        self.assertEqual(overflow.fit_wrap(t, [face]), (t, 0, 0))

    def test_width_is_the_widest_variant_without_tags(self):
        face = overflow.Face('standard', letters(20))
        self.assertEqual(self.width('#T1aaaa#T2aa#T0 b', [face]), 4 * 20 + 10 + 20)
        self.assertEqual(self.width('#P(1,2)${FirstName}#KW!', [face]), 5 * 20)   # Naya!
        self.assertEqual(self.width('ab', [self.narrow, face]), 40)


class ApplySheetFitTest(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def test_plan_wraps_by_width_and_reports_the_rows(self):
        js = {'A.tat': ['', '一', '二', '三']}
        long = ' '.join(['abcd'] * 36)
        rows = [row(2, 1, '一', long), row(3, 2, '二', 'abcd abcd'), row(4, 3, '三', '#P(1500,100)' + long)]
        plain, _ = applysheet.plan(rows, js, {}, set())
        faces = [overflow.Face('standard', letters(22))]
        writes, rep = applysheet.plan(rows, js, {}, set(), faces=faces, chars=62, max_lines=0)
        self.assertEqual(plain['A.tat'][1].count('\n'), 2)
        self.assertEqual(writes['A.tat'][1].count('\n'), 3)
        self.assertEqual(writes['A.tat'][2], plain['A.tat'][2])                  # fits: unchanged
        p_lines = writes['A.tat'][3].split('\n')
        self.assertEqual(len(p_lines), 9)                  # 400 px: 4 words of 88 px a line
        self.assertTrue(all(overflow.line_width(l, faces, 'Naya') <= (1920 - 1500) / 1.05 for l in p_lines))
        self.assertEqual(dict((x['r']['row'], x['fit']) for x in rep), {2: 1, 3: 0, 4: 6})
        path = os.path.join(self.d, 'r.csv')
        applysheet.write_report(path, rep)
        with open(path, encoding='utf-8-sig') as f:
            notes = dict((r[1], r[6]) for r in list(csv.reader(f))[1:])
        self.assertEqual(sorted(notes), ['2', '4'])
        self.assertIn('Nhiều hơn 1 dòng', notes['2'])
        self.assertNotIn('câu có #P', notes['2'])
        self.assertIn('câu có #P', notes['4'])

    def test_plan_fills_lines_and_keeps_strings_within_three(self):
        js = {'A.tat': ['', '一', '二', '三']}
        faces = [overflow.Face('standard', letters(10))]
        rows_ = [row(2, 1, '一', ' '.join(['abcd'] * 30)),          # 3 lines at 62, 2 filled
                 row(3, 2, '二', 'aa bb\n\ncc dd\n\nee ff\n\ngg hh'),   # 4 cell lines (the sheet doubles breaks)
                 row(4, 3, '三', ' '.join(['abcd'] * 120))]          # 5 lines however it is wrapped
        writes, rep = applysheet.plan(rows_, js, {}, set(), faces=faces)
        self.assertEqual(writes['A.tat'][1].count('\n'), 1)
        self.assertEqual(writes['A.tat'][2], 'aa bb cc dd ee ff gg hh')
        self.assertEqual(overflow.rows(writes['A.tat'][3]), 5)
        got = dict((x['r']['row'], (x['fit'], x['merged'], x['rows'])) for x in rep)
        self.assertEqual(got, {2: (-1, 0, 0), 3: (-3, 1, 0), 4: (-5, 0, 5)})
        path = os.path.join(self.d, 'r.csv')
        applysheet.write_report(path, rep)
        with open(path, encoding='utf-8-sig') as f:
            notes = dict((r[1], r[6]) for r in list(csv.reader(f))[1:])
        self.assertEqual(sorted(notes), ['3', '4'])
        self.assertIn('nối các dòng', notes['3'])
        self.assertIn('vẫn có 5 dòng', notes['4'])

    def test_a_trailing_break_only_where_jp_has_one(self):
        js = {'A.tat': ['', '一\n', '二']}
        faces = [overflow.Face('standard', letters(10))]
        writes, _ = applysheet.plan([row(2, 1, '一\n', 'abc\n'), row(3, 2, '二', 'abc\n')], js, {}, set(), faces=faces)
        self.assertEqual(writes['A.tat'], {1: 'abc\n', 2: 'abc'})

    def test_story_faces_needs_the_four_settings_fonts(self):
        with self.assertRaises(SystemExit) as e:
            overflow.story_faces(self.d)
        self.assertIn('standard.font.memfs', str(e.exception))


if __name__ == '__main__':
    unittest.main()
