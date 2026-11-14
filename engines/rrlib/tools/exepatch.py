# -*- coding: utf-8 -*-
"""exepatch.py - code changes to the game's program (exefs/main) that text alone cannot make.

    python exepatch.py check  <mod>/exefs/main
    python exepatch.py apply  <mod>/exefs/main --out <mod>/exefs            # dry run
    python exepatch.py apply  <mod>/exefs/main --out <mod>/exefs --apply    # write
    python exepatch.py revert <mod>/exefs/main --out <mod>/exefs --apply

check   says, for every patch below, whether the main has it, lacks it, has
        an older version of it, or holds something else at its places
        (another game version, or a change made by hand). Nothing is written.
apply   writes the patches the main lacks and updates older versions. Every
        instruction a patch replaces is compared with the JP 1.0.0 program
        (or an earlier version of the patch) first; a main that differs
        anywhere is refused. A main already patched is left as it is.
revert  puts the JP instructions back.

Works on any JP 1.0.0 main: the original, the 02/10 patch's (its read
redirects stay), and one exetext.py wrote (its translations stay; exetext
keeps these patches when it runs again on the result). The NSO is written
with its segments uncompressed and their hashes recomputed, as exetext does.

Patches
-------
flo-title-rows   The flowchart screen (ssdata/flo) shows the chosen node's
    chapter and title in a vertical text box right of the chart: one
    character per row, which suits Japanese and puts each Vietnamese letter
    on a row of its own. The patch makes that one box horizontal with each
    word on a line of its own, centred on the column, and starts the title
    on a new line after the chapter. Nothing else uses this box, so no other
    screen changes. Four places in the screen's code (class with vtable
    entry 0xb4690) and a routine in the empty space after the PLT:
      0xb7970  box created (0xb78f0): instead of turning vertical layout on
               (0x151bf0(box+744, 1)), set line alignment to centre
               (0x14fa1c(box+632, 1)). The box then lays text out
               horizontally, its default.
      0xb8eb4  text built (0xb8d00): swprintf("%ls%ls", chapter, title)
               reads its format from 0x2f1fcc instead, "%ls\\n%ls". Japanese
               chapters then split at 【 (route name for the art top left,
               【第五節】 for the box); the Vietnamese ones have ( ) and the
               whole chapter stays in the box, as before.
      0xb9104  text shown: the call that reads the box's current text before
               comparing it with the new one goes to the routine at
               0x2f1f88, which first turns every space of the new text into
               a line break, in place. Doing it before the compare keeps the
               game's "same text: leave the box alone" test working, so the
               scroll below is not restarted every time.
      0xb91ac  the box's x: 1155 (right edge of the old column) -> 1135, the
               middle of that column, where the centred lines go.
    Texts taller than the box (474 px; nine lines) still scroll up and start
    over (0xb9b00), as long Japanese titles do: that code only reads the
    text's height. The art decides how wide a line may be: the box is drawn
    UNDER the background (mat_flo_bg), which has a transparent hole 52 px
    wide (x 1110..1161, y 221..693) over the cell mat_flo_bg_covar, a copy
    of the background 168 px wide (x 1046..1213). Words wider than the hole
    are cut on both sides until the hole is widened in the screen's art
    (x 1060..1209 fits Matsurika, the widest word, ~116 px).

flo-hint-bottom   The flowchart's button help ({A} 決定 {X} 現在地 {L}{R}
    項目切替 {B} 戻る, string 0x40a290 via .data 0x59f070) is one text,
    right-aligned (line alignment 2), shown at (1208, 22) = right edge, top;
    0xae8f0..0xae900 build that vec2 and s8 = 22. Hidden is shown minus
    (0, height + s8) (0xae91c; 0x272908 subtracts), so it slides up just off
    the top. The Vietnamese line is ~938 px wide and ran over the route title
    (top left). The patch moves it onto the purple band at the bottom left
    (y ~985..1077 on screen): right edge and top both 1008 (one register
    carries both, so the five words still fit), line ~73..1011 x 1008..1054;
    s8 = -26 and 0xae91c becomes s8 - height, so it hides by sliding down
    to y 1080. The first version, flo-hint-right (right edge 1576, top 22),
    is updated by apply.

ev-title-rows   The scene replay list (ssdata/ev, title menu 回想) shows
    eight entries a page as vertical columns 80 px apart, each a number box
    ("12.") over a chapter + title box, all one character per row - one
    Vietnamese letter per row. 16 boxes (8 numbers, 8 titles) are made at
    0x86384 and filled at 0x8a0d4 for the page. The patch makes them
    horizontal like flo-title-rows: one word per line, lines centred on the
    column, the title on a line of its own; and draws their text at 87.5%
    (the layout's text scale, 0x150f3c, which other screens set too), since
    full-size words of 80+ px run into the next column:
      0x863e8  boxes created: instead of the turned-character list
               (0x151bf8) and vertical layout (0x151bf0), set line alignment
               to centre (0x14fa1c(box+632, 1)) and the text scale
               (0x150f3c(box+264, 0.875)). The list is only read when
               vertical.
      0x8a0b4  first column x 896 (right edge of the old column) -> 876, its
               middle; the next ones stay 80 px to the left.
      0x8a250  text built: swprintf reads "%ls\\n%ls" from flo-title-rows'
               format (0x2f1fcc) instead of "%ls%ls" at 0x395c94.
      0x8a2fc  text shown: the getText call before the compare goes to the
               second entry of the flo-title-rows routine (0x2f1fec: the
               text is at [x29-40] here), spaces -> line breaks.
    The number boxes get the same centring and scale ("12." on one line).
    Titles still start at y 392 and scroll when taller than 668 px (0x8940c,
    0x88100): that code reads only the height. They show through the
    window of mat_ev_l_base_msk (paper drawn over the list with a hole,
    screen x 262..949, y 390..1045), so only the left column's widest
    words (Matsurika) come near an edge. The two patches share the routine
    at 0x2f1f88: apply and revert write it with either.

default-name   Every scenario starts with common.tat's CHECK_HEROINE_NAME:
    the #T1 text and the voice lines that say the heroine's name (Naya) are
    chosen only when GAMESTR_HeroineFirstName equals
    SYSTEMSTR_CONST_DefaultHeroineFirstName (and the last name its default,
    "" in JP and VI); otherwise #T2, ${FirstName} and voice that says
    お嬢さん. That CONST is SYSTEMSTR 8 inside system.sav. The game writes
    it from the program's default name (.data 0x55a9c8 -> ナーヤ in JP, Naya
    in the VI main) only when it creates system.sav (0x164810 -> 0x164044),
    and a script cannot change a CONST. A system.sav made by the JP game or
    the 02/10 patch therefore keeps ナーヤ for good: the name screen's
    default (Naya, from the program) fails the check and the heroine is
    never called by name (user, 2026-11-14, EV00_0001_01). The name screen's
    own check (0x1a9d48) reads the program's string and is right.
      0x164ee4  system.sav read and its header checked (0x164e40): the
               memcpy into the system data (0x5f84b0) goes to a routine at
               0x2f1ed0 (the 12 words after ev-route-split's) that does the
               memcpy, then 0x1653e0(8, default name, force) as creation
               does. Runs at every boot; the value goes into system.sav
               with the game's next save of system data.
    A play save keeps the result of the last check (GAMEINT
    OutputTextAndSoundType) until the next scenario starts.

route-first   The load/save lists and the save files show a slot's route
    and chapter as two lines ("Fey Route" / chapter title). 0x1654d0 builds
    them from a node: route name (getRouteName 0x81020 -> 0x80f10) + the
    program's ルート (message table 0x54f2c0 + 344, via the GOT) + "\n" +
    title, and the text goes into LISTSAVE_INFO when the slot is saved, so a
    slot made before a change keeps its old text. JP puts ルート after the
    name; the Vietnamese word goes before it ("Tuyến Fey" - the sheet's exe
    row for ルート is "Tuyến ", already with its space; the 21:08 test had
    " Route" and gave "Fey Route", which is what the user asked to turn
    round, 2026-11-14). Nodes whose kind holds 終節 (the three endings and
    the plain one, tested at 0x1655f8 with wstring::find) have no ルート in
    them and are left as they were. The function starts with 24 words that
    only fill the name and title strings with dummy text (ダミー...), so the
    patch uses them:
      0x1654f0  the name and title strings are made empty (short, size 0),
               the 32-byte allocation for the dummy goes; a branch hops
               over a stub at 0x165500:
                   X.insert(0, ルート); b 0x165680
               (X = the name string at [x29-48], the same call the game
               used on the "\n" string).
      0x165568  that "\n" string no longer gets ルート put in front (its
               insert call becomes a NOP; x0 is the string already), so the
               line break stays on its own for the plain ending's replace.
      0x165604  not an ending (find gives 0): go to the stub, then on to
               the concatenation name + "\n" + title as before.

hint-hide   Seven screens show their button help as one right-aligned text
    at the top, shown at (right edge, 22), and hide it by sliding it up by
    (0, height + 22): its box then ends exactly at the screen's top edge,
    and the screen keeps it there after it closes. Japanese glyphs stay
    inside the box; Vietnamese g y p q, the dot under ạ ậ ị ọ ụ ... and the
    low capitals Q X C of the story fonts reach ~10 px below it, so their
    bottoms showed at the top edge of the story and the menus (user,
    2026-11-14, EV01_0007_03 after loading a save: the load screen's
    `{A} Xác nhận {L}{R} Chuyển thẻ {B} Quay lại`, box ~48 px high). Each
    screen sets it up the same way (0x254b4 text, 0x2728bc shown, 0x25654
    size, 0x25624 shown + slide); the patch makes the slide twice the
    height instead of height + 22, so the hidden box ends at 22 - height
    (~-26), clear of the ink. Right edges: 0x47058 1640, 0x7f1fc 1672,
    0xa3b6c 1198 (save/load, ssdata/losa), 0xe76f0 1190 (settings),
    0x11f8b8 1196, 0x1291f8 1258 (affection). The flowchart's (0xae91c,
    1208) is flo-hint-bottom's and hides downwards.
"""
import argparse
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from exetext import Nso                            # noqa: E402
from patch import say_replaced, write_files        # noqa: E402

NOP = 0xd503201f
JP_TEXT_SIZE = 0x2f1e00         # .text of the JP 1.0.0 main as shipped
TEXT_END = 0x2f2000             # .rodata starts here; the 02/10 patch grew .text to it for its read redirects


def bl(pc, target):
    return 0x94000000 | (((target - pc) >> 2) & 0x3ffffff)


def b(pc, target):
    return 0x14000000 | (((target - pc) >> 2) & 0x3ffffff)


def b_ne(pc, target):
    return 0x54000001 | ((((target - pc) >> 2) & 0x7ffff) << 5)


def cbz_x(rt, pc, target):
    return 0xb4000000 | ((((target - pc) >> 2) & 0x7ffff) << 5) | rt


def tbz0_w(rt, pc, target):
    """TBZ Wrt, #0, target"""
    return 0x36000000 | ((((target - pc) >> 2) & 0x3fff) << 5) | rt


def adrp_add(rd, pc, target):
    """ADRP Xrd, target page at pc; ADD Xrd, Xrd, #page offset at pc + 4."""
    imm = ((target >> 12) - (pc >> 12)) & ((1 << 21) - 1)
    return (0x90000000 | ((imm & 3) << 29) | ((imm >> 2) << 5) | rd,
            0x91000000 | ((target & 0xfff) << 10) | (rd << 5) | rd)


def branch_target(word, pc):
    """Where a B or BL at pc goes, or None."""
    if word & 0x7c000000 != 0x14000000:
        return None
    imm = word & 0x3ffffff
    return pc + 4 * (imm - ((imm & 0x2000000) << 1))


def utf32(s):
    return tuple(ord(c) for c in s) + (0,)


class Site(object):
    """Words at one address: the JP ones (any of `old`, each a tuple of
    words), what the patch writes there, and what earlier versions of the
    patch wrote (`prev`), which apply replaces. A `shared` site belongs to
    several patches (a routine they all call)."""

    def __init__(self, at, old, new, why, prev=(), shared=False):
        self.at, self.why, self.shared = at, why, shared
        self.old, self.new, self.prev = [tuple(o) for o in old], tuple(new), [tuple(p) for p in prev]

    def words(self, img):
        return struct.unpack_from('<%dI' % len(self.new), img, self.at)

    def state(self, img):
        w = self.words(img)
        if w == self.new:
            return 'new'
        if w in self.old:
            return 'old'
        if w in self.prev:
            return 'prev'
        return 'other'


class Patch(object):
    def __init__(self, name, title, sites):
        self.name, self.title, self.sites = name, title, sites

    def state(self, img):
        """'applied', 'missing', 'outdated' (an earlier version, maybe with
        places it did not have yet), or 'other' (some place holds none of
        these). A shared site written by another patch does not make this
        one 'outdated': it is 'missing' while its own places are all JP."""
        own = set(s.state(img) for s in self.sites if not s.shared)
        states = own | set(s.state(img) for s in self.sites if s.shared)
        if states == {'new'}:
            return 'applied'
        if 'other' in states:
            return 'other'
        if own == {'old'}:
            return 'missing'
        return 'outdated'


# ---------------------------------------------------------------- flo-title-rows

FLO_CAVE = 0x2f1f88             # JP: zero padding after the PLT; the 02/10 patch's caves end at 0x2f1f88
FLO_CAVE_WORDS = (TEXT_END - FLO_CAVE) // 4     # the whole free run, 30 words


def flo_cave(at=FLO_CAVE, ev=True):
    """The routine 0xb9104 calls instead of the box's getText (box+1480),
    then the swprintf format 0xb8eb4 points at, then the routine's second
    entry, which 0x8a2fc (ev-title-rows) calls, then NOP padding. x0 = the
    box; the text it is about to compare and show is the std::wstring at the
    caller's [x29-96] (flowchart) or [x29-40] (scene replay), changed in
    place (same length). libc++ short string: byte 0 = size*2, the
    characters (UTF-32) from +4; a long one has bit 0 set, its size at +8
    and its buffer at +16. ev=False: without the second entry, as written
    on 2026-11-13."""
    w = [0xd10183a9,        #     sub  x9, x29, #96         ; &text, in the caller's frame
         0x3940012a,        #     ldrb w10, [x9]
         0x9100112b,        #     add  x11, x9, #4          ; short: chars
         0xd341fd4c,        #     lsr  x12, x10, #1         ; short: size
         None,              #     tbz  w10, #0, L7
         0xf940052c,        #     ldr  x12, [x9, #8]        ; long: size
         0xf940092b,        #     ldr  x11, [x9, #16]       ; long: chars
         None,              # L7: cbz  x12, L15
         0xb840456d,        #     ldr  w13, [x11], #4
         0xd100058c,        #     sub  x12, x12, #1
         0x710081bf,        #     cmp  w13, #' '
         None,              #     b.ne L7
         0x5280014d,        #     mov  w13, #'\n'
         0xb81fc16d,        #     stur w13, [x11, #-4]
         None,              #     b    L7
         0x91172000,        # L15: add x0, x0, #1480        ; what getText returns: &box->text
         0xd65f03c0]        #     ret
    pc = lambda i: at + 4 * i
    w[4] = tbz0_w(10, pc(4), pc(7))
    w[7] = cbz_x(12, pc(7), pc(15))
    w[11] = b_ne(pc(11), pc(7))
    w[14] = b(pc(14), pc(7))
    w += utf32('%ls\n%ls')
    if ev:
        w += [0xd100a3a9,                       # sub  x9, x29, #40   ; ev_entry: &text in 0x8a0d4's frame
              b(pc(len(w) + 1), pc(1))]         # b    the routine, past its own sub
    return w + [NOP] * (FLO_CAVE_WORDS - len(w))


def flo_format(at=FLO_CAVE):
    return at + 4 * 17


def ev_entry(at=FLO_CAVE):
    return at + 4 * 25


# What 2026-11-13 21:17's build wrote at FLO_CAVE (the routine and format,
# no second entry). Kept to recognise and update a main patched with it.
FLO_CAVE_V2 = tuple(flo_cave(ev=False))


# What 2026-11-13's first build wrote at FLO_CAVE: a call to the game's
# std::wstring replace-all (0x1bfdd0), then operator= (0x2f08d0) and delete
# (0x276370). Kept to recognise and update a main patched with it.
FLO_CAVE_V1 = (0xa9b97bfd, 0xa90153f3, 0xaa0003f3, 0xd10183b4, 0x910003fd, 0x52800049, 0x390083e9,
               0x3900e3e9, 0xd2800409, 0xf80243e9, 0xd2800149, 0xf803c3e9, 0xaa1403e0, 0x910083e1,
               0x9100e3e2, 0x910143e8, bl(FLO_CAVE + 64, 0x1bfdd0), 0xaa1403e0, 0x910143e1,
               bl(FLO_CAVE + 76, 0x2f08d0), 0x394143e8, 0x36000068, 0xf94033e0, bl(FLO_CAVE + 92, 0x276370),
               0x91172260, 0xa94153f3, 0xa8c77bfd, 0xd65f03c0, NOP, NOP)


CAVE_SITE = Site(FLO_CAVE, [(0,) * FLO_CAVE_WORDS, (NOP,) * FLO_CAVE_WORDS], flo_cave(),
                 'routine and format at 0x%x' % FLO_CAVE, prev=[FLO_CAVE_V1, FLO_CAVE_V2], shared=True)


def _flo_patch():
    return Patch('flo-title-rows', 'flowchart title: one word per line, title under the chapter', [
        Site(0xb7970, [(0xaa1503e0, 0x52800021, bl(0xb7978, 0x151bf0))],      # mov x0, x21; mov w1, #1; bl setVertical
             (0xd101c2a0, 0x52800021, bl(0xb7978, 0x14fa1c)),                  # sub x0, x21, #112; mov w1, #1; bl setLineAlign
             'box created: horizontal, lines centred'),
        Site(0xb8eb4, [adrp_add(0, 0xb8eb4, 0x395c94)], adrp_add(0, 0xb8eb4, flo_format()),
             'text built: "%ls\\n%ls" (chapter, title) instead of "%ls%ls"'),
        Site(0xb9104, [(bl(0xb9104, 0x14e448),)], (bl(0xb9104, FLO_CAVE),),
             'text shown: spaces become line breaks'),
        Site(0xb91ac, [(0x528c0008, 0x72a89208)],                              # mov w8, #0x6000; movk w8, #0x4490, lsl 16 (1155.0)
             (0x529c0008, 0x72a891a8),                                         # mov w8, #0xe000; movk w8, #0x448d, lsl 16 (1135.0)
             'box x 1155 -> 1135'),
        CAVE_SITE,
    ])


# ---------------------------------------------------------------- flo-hint-bottom

def movz_w_hi(rd, imm16):
    """MOVZ Wrd, #imm16, LSL #16 - a float whose low 16 bits are 0."""
    return 0x52a00000 | (imm16 << 5) | rd


FLO_HINT_XY = 1008.0            # right edge AND top; 0x447c0000, the high half alone carries it (4 px steps here)
FLO_HINT_SLIDE = -26.0          # hidden = shown - (0, this - height): top at 1080, just below the screen


def _flo_hint_patch():
    hi = struct.unpack('<I', struct.pack('<f', FLO_HINT_XY))[0]
    assert hi & 0xffff == 0
    jp = (movz_w_hi(8, 0x4497),     # mov  w8, #1208.0
          0x1e26d008,               # fmov s8, #22.0
          0x910063e0,               # add  x0, sp, #24
          0x1e270100,               # fmov s0, w8
          0x1e204101)               # fmov s1, s8          ; shown = (1208, 22)
    right = (movz_w_hi(8, 0x44c5),) + jp[1:]                  # 2026-11-14 flo-hint-right: (1576, 22)
    return Patch('flo-hint-bottom', 'flowchart button help: on the purple band bottom left, (%d, %d)'
                 % (FLO_HINT_XY, FLO_HINT_XY), [
        Site(0xae8f0, [jp],
             (movz_w_hi(8, hi >> 16), fmov_s(8, FLO_HINT_SLIDE), 0x910063e0,
              0x1e270100,           # fmov s0, w8
              0x1e270101),          # fmov s1, w8          ; shown = (1008, 1008)
             'shown position (1208, 22) -> (%d, %d)' % (FLO_HINT_XY, FLO_HINT_XY), prev=[right]),
        Site(0xae91c, [(0x1e282801,)],                          # fadd s1, s0, s8      ; slide (0, height + 22)
             (0x1e203901,),                                     # fsub s1, s8, s0      ; slide (0, -26 - height)
             'hides by sliding down off the screen, not up'),
    ])


# ---------------------------------------------------------------- hint-hide

FADD_S1_S0_S8 = 0x1e282801      # slide (0, height + 22): hidden box ends at y 0
FADD_S1_S0_S0 = 0x1e202801      # slide (0, 2 * height): hidden box ends at 22 - height
HINT_SLIDES = ((0x47058, 1640), (0x7f1fc, 1672), (0xa3b6c, 1198), (0xe76f0, 1190), (0x11f8b8, 1196),
               (0x1291f8, 1258))  # (fadd, right edge); flowchart 0xae91c is flo-hint-bottom's


def _hint_hide_patch():
    return Patch('hint-hide', 'button help hides higher: Vietnamese descenders no longer peek in at the top edge', [
        Site(at, [(FADD_S1_S0_S8,)], (FADD_S1_S0_S0,),
             'help at right edge %d: slide up 2 x height, not height + 22' % edge)
        for at, edge in HINT_SLIDES])


# ---------------------------------------------------------------- ev-title-rows

def fmov_s(rd, value):
    """FMOV Srd, #value (one of the 256 immediates: +-n/16 * 2^r, n 16..31, r -3..4)."""
    for imm8 in range(256):
        b6 = (imm8 >> 6) & 1
        bits = ((imm8 >> 7) << 31 | ((b6 ^ 1) << 30) | ((0x1f if b6 else 0) << 25)
                | (((imm8 >> 4) & 3) << 23) | ((imm8 & 0xf) << 19))
        if struct.unpack('<f', struct.pack('<I', bits))[0] == value:
            return 0x1e201000 | (imm8 << 13) | rd
    raise ValueError('fmov cannot hold %r' % value)


EV_TEXT_SCALE = 0.875           # 80 px columns: words up to ~80 px at full size meet the next column


def _ev_patch():
    return Patch('ev-title-rows', 'scene replay list: one word per line at %g%%, title under the chapter'
                 % (EV_TEXT_SCALE * 100), [
        Site(0x863e8, [(0x910ba115,                         # add  x21, x8, #744       ; x8 = the new box
                        0xb00028c1, 0xaa1503e0, 0xf9401821,  # adrp x1; mov x0, x21; ldr x1, [x1, #48]
                        bl(0x863f8, 0x151bf8),               # bl   setTurnedChars
                        0xaa1503e0, 0x52800021,              # mov  x0, x21; mov w1, #1
                        bl(0x86404, 0x151bf0))],             # bl   setVertical
             (0x9109e100, 0x52800021,                        # add  x0, x8, #632; mov w1, #1
              bl(0x863f0, 0x14fa1c),                         # bl   setLineAlign        ; centre
              0xf85803a0, 0x91042000,                        # ldur x0, [x29, #-128]; add x0, x0, #264
              fmov_s(0, EV_TEXT_SCALE),                      # fmov s0, #0.875
              bl(0x86400, 0x150f3c),                         # bl   setTextScale
              NOP),
             'boxes created: horizontal, lines centred, text at %g' % EV_TEXT_SCALE),
        Site(0x8a0b4, [(0x52807018,)], (0x52806d98,),       # mov w24, #896 -> #876
             'first column x 896 -> 876'),
        Site(0x8a250, [adrp_add(0, 0x8a250, 0x395c94)], adrp_add(0, 0x8a250, flo_format()),
             'text built: "%ls\\n%ls" (chapter, title) instead of "%ls%ls"'),
        Site(0x8a2fc, [(bl(0x8a2fc, 0x14e448),)], (bl(0x8a2fc, ev_entry()),),
             'text shown: spaces become line breaks'),
        CAVE_SITE,
    ])


# ---------------------------------------------------------------- ev-route-split

ROUTE_CAVE = 0x2f1e88           # JP: zero; the 02/10 main: NOP padding between its two read-redirect caves
ROUTE_CAVE_WORDS = 18           # the routine; the 12 words after it to 0x2f1f00 are NAME_CAVE


def b_eq(pc, target):
    return 0x54000000 | ((((target - pc) >> 2) & 0x7ffff) << 5)


def route_cave(at=ROUTE_CAVE):
    """The routine 0x887d8 calls instead of std::wstring::find(L'【', 0) on the
    chosen entry's chapter (x0 = the string, x2 = 0): finds '(' instead and
    gives the length of the route name before it, spaces before the '('
    left out, or -1. "Cửu Quái (Tự Tiết)" -> 8, the length of "Cửu Quái",
    which is how the route-name table at .data 0x54f460 spells it."""
    w = [0xa9bf7be0,        #     stp  x0, x30, [sp, #-16]!
         0x52800501,        #     mov  w1, #'('
         bl(at + 8, 0x2f0b00),  # bl   find
         0xa8c17be9,        #     ldp  x9, x30, [sp], #16   ; x9 = the string
         0xb100041f,        #     cmn  x0, #1
         None,              #     b.eq L17
         0x3940012a,        #     ldrb w10, [x9]
         0x9100112b,        #     add  x11, x9, #4          ; short: chars
         None,              #     tbz  w10, #0, L10
         0xf940092b,        #     ldr  x11, [x9, #16]       ; long: chars
         None,              # L10: cbz x0, L17
         0xd100040c,        #     sub  x12, x0, #1
         0xb86c796d,        #     ldr  w13, [x11, x12, lsl #2]
         0x710081bf,        #     cmp  w13, #' '
         None,              #     b.ne L17
         0xaa0c03e0,        #     mov  x0, x12
         None,              #     b    L10
         0xd65f03c0]        # L17: ret
    pc = lambda i: at + 4 * i
    w[5] = b_eq(pc(5), pc(17))
    w[8] = tbz0_w(10, pc(8), pc(10))
    w[10] = cbz_x(0, pc(10), pc(17))
    w[14] = b_ne(pc(14), pc(17))
    w[16] = b(pc(16), pc(10))
    return w + [NOP] * (ROUTE_CAVE_WORDS - len(w))


def _ev_route_patch():
    y372, y392 = movz_w_hi(8, 0x43ba), movz_w_hi(8, 0x43c4)     # mov w8, #372.0 / #392.0
    return Patch('ev-route-split', 'scene replay list: route name off the list, into the title art', [
        Site(0x887d8, [(bl(0x887d8, 0x2f0b00),)], (bl(0x887d8, ROUTE_CAVE),),
             'chosen entry: route name = chapter before " (" (JP: before 【) -> title art'),
        Site(0x8a294, [(0x52860201,)], (0x52800501,),          # mov w1, #L'【' -> #'('
             'list text: from "(" on (JP: from 【 on)'),
        Site(0x8a2e0, [(y372,)], (y392,),
             'list text cut: y 372 -> 392, its first line clear of the paper over the list'),
        Site(0x8812c, [(y372,)], (y392,), 'scroll: pause at y 392, not 372'),
        Site(0x88144, [(y372,)], (y392,), 'scroll: pause at y 392, not 372 (2)'),
        Site(ROUTE_CAVE, [(0,) * ROUTE_CAVE_WORDS, (NOP,) * ROUTE_CAVE_WORDS], route_cave(),
             'routine at 0x%x' % ROUTE_CAVE),
    ])


# ---------------------------------------------------------------- default-name

NAME_CAVE = ROUTE_CAVE + 4 * ROUTE_CAVE_WORDS       # 0x2f1ed0, free up to the 02/10 cave at 0x2f1f00
NAME_CAVE_WORDS = (0x2f1f00 - NAME_CAVE) // 4       # 12
SYSDATA_LOADED = 0x164ee4       # memcpy(system data, system.sav as read, 0x199b4) in 0x164e40
MEMCPY = 0x2f07e0
SET_SYSTEMSTR = 0x1653e0        # (index, wchar_t *text, force): force writes a CONST too
DEFAULT_NAME_GOT = 0x59f448     # GOT entry -> .data 0x55a9c8, the pointer to the default first name
DEFAULT_FIRSTNAME = 8           # SYSTEMSTR_CONST_DefaultHeroineFirstName


def adrp_ldr(rd, pc, target):
    """ADRP Xrd, target page at pc; LDR Xrd, [Xrd, #page offset] at pc + 4."""
    page = adrp_add(rd, pc, target)[0]
    return page, 0xf9400000 | (((target & 0xfff) >> 3) << 10) | (rd << 5) | rd


def name_cave(at=NAME_CAVE):
    """The routine 0x164ee4 calls instead of memcpy once system.sav has been
    read: the memcpy, then SYSTEMSTR 8 := the program's default first name,
    as the game does only when it creates system.sav (0x164044)."""
    page, load = adrp_ldr(8, at + 8, DEFAULT_NAME_GOT)
    w = [0xa9bf7bfd,                            # stp  x29, x30, [sp, #-16]!
         bl(at + 4, MEMCPY),                    # bl   memcpy             ; what 0x164ee4 called
         page,                                  # adrp x8, GOT page
         load,                                  # ldr  x8, [x8, #0x448]   ; &default name pointer
         0xf9400101,                            # ldr  x1, [x8]           ; the default name
         0x52800000 | DEFAULT_FIRSTNAME << 5,   # mov  w0, #8
         0x52800022,                            # mov  w2, #1             ; force (it is a CONST)
         bl(at + 28, SET_SYSTEMSTR),            # bl   set SYSTEMSTR
         0xa8c17bfd,                            # ldp  x29, x30, [sp], #16
         0xd65f03c0]                            # ret
    return w + [NOP] * (NAME_CAVE_WORDS - len(w))


def _name_patch():
    return Patch('default-name', 'heroine default name: SYSTEMSTR_CONST_DefaultHeroineFirstName from the program', [
        Site(SYSDATA_LOADED, [(bl(SYSDATA_LOADED, MEMCPY),)], (bl(SYSDATA_LOADED, NAME_CAVE),),
             'system.sav read: then its default first name := the program\'s'),
        Site(NAME_CAVE, [(0,) * NAME_CAVE_WORDS, (NOP,) * NAME_CAVE_WORDS], name_cave(),
             'routine at 0x%x' % NAME_CAVE),
    ])


# ---------------------------------------------------------------- route-first

SAVE_TEXT = 0x1654d0            # builds a node's two lines: route name + ルート + "\n" + title
SAVE_INIT = 0x1654f0            # 24 words that give the name and title strings dummy text, up to 0x16554c
SAVE_STUB = 0x165500            # inside them: the stub that puts ルート before the name
SAVE_ADRP = 0x16552c            # adrp x21: the GOT page of the message table, kept where it is
SAVE_NEWLINE = 0x165568         # "\n".insert(0, ルート)
SAVE_ENDING = 0x165604          # cbz x0 (no 終節 in the node's kind): straight to the concatenation
SAVE_CONCAT = 0x165680          # name + "\n"-string, then + title
WSTRING_INSERT = 0x2f0b40       # std::wstring::insert(pos, const wchar_t *)


def route_first_init():
    """The 24 words from SAVE_INIT: x19 = the result slot, name and title
    made empty, a branch over the stub, the stub, NOPs where the dummy text
    was stored; the two instructions that load the message table stay."""
    adrp, ldr_table, ldr_route = 0xb00021d5, 0xf947f6b5, 0xf940aea2       # JP words at 0x16552c / 0x165544 / 0x165548
    w = [0xaa0803f3,                                    # mov  x19, x8
         0x381d03bf,                                    # sturb wzr, [x29, #-48]   ; name string: short, size 0
         0x381e83bf,                                    # sturb wzr, [x29, #-24]   ; title string: the same
         b(SAVE_INIT + 12, SAVE_ADRP),                  # b    over the stub
         0xd100c3a0,                                    # sub  x0, x29, #48        ; stub: the name string
         0xaa1f03e1,                                    # mov  x1, xzr             ; position 0
         ldr_route,                                     # ldr  x2, [x21, #344]     ; ルート
         bl(SAVE_STUB + 12, WSTRING_INSERT),            # bl   insert
         b(SAVE_STUB + 16, SAVE_CONCAT)]                # b    the concatenation
    w += [NOP] * ((SAVE_ADRP - SAVE_INIT) // 4 - len(w))
    w += [adrp] + [NOP] * 5 + [ldr_table, ldr_route, NOP]
    return w


def _route_first_patch():
    jp_init = (0x52800400, 0xaa0803f3, bl(0x1654f8, 0x2761b0), 0x52800128, 0x528000e9, 0xf81e83a8, 0xa93f03a9,
               0xd2861808, 0xd2861f89, 0xf2c61be8, 0xf2c617e9, 0xa9002408, 0xd2861489, 0xf2c61909, 0x52861d6a,
               0xb00021d5, 0xa9012809, 0x528000c9, 0x381d03a9, 0xf81d43a8, 0x52861f88, 0xf947f6b5, 0xf940aea2,
               0xf81dc3a8)
    return Patch('route-first', 'save slot text: ルート first, "Tuyến Fey" for "Fey Route"', [
        Site(SAVE_INIT, [jp_init], route_first_init(),
             'name/title strings start empty (not dummy text); stub: name.insert(0, ルート)'),
        Site(SAVE_NEWLINE, [(bl(SAVE_NEWLINE, WSTRING_INSERT),)], (NOP,),
             '"\\n" no longer gets ルート put in front'),
        Site(SAVE_ENDING, [(cbz_x(0, SAVE_ENDING, SAVE_CONCAT),)], (cbz_x(0, SAVE_ENDING, SAVE_STUB),),
             'not an ending: ルート goes before the name'),
    ])


PATCHES = [_flo_patch(), _flo_hint_patch(), _ev_patch(), _ev_route_patch(), _name_patch(),
           _route_first_patch(), _hint_hide_patch()]


# ---------------------------------------------------------------- program

class Main(object):
    def __init__(self, raw):
        self.raw = raw
        self.nso = Nso(raw)
        self.img = self.nso.image()
        self.text_size = len(self.nso.segs[0][1])

    def problem(self):
        """Why the patches cannot go into this main, or None."""
        if self.text_size not in (JP_TEXT_SIZE, TEXT_END) or self.nso.segs[1][0] != TEXT_END:
            return ('.text is 0x%x bytes and .rodata starts at 0x%x; the JP 1.0.0 program has 0x%x (0x%x once '
                    'patched) and 0x%x: another version of the game'
                    % (self.text_size, self.nso.segs[1][0], JP_TEXT_SIZE, TEXT_END, TEXT_END))
        return None

    def write(self, img):
        """The NSO of img. .text grows to TEXT_END when a routine was written
        past its end: the loader maps that page executable anyway, but only
        a segment's own bytes are loaded."""
        nso = Nso(self.raw)
        if any(img[self.text_size:TEXT_END]):
            nso.segs[0] = (0, bytes(img[:TEXT_END]))
        return nso.write(img, len(nso.segs[2][1]), nso.bss)


def changed(main, patches, revert=False):
    """The image with the patches written (or reverted), and what was done:
    [(patch, 'write' | 'keep' | 'refuse', note)]."""
    img = bytearray(main.img)
    done = []
    for p in patches:
        st = p.state(img)
        if st == 'other':
            bad = ['0x%x (%s)' % (s.at, s.why) for s in p.sites if s.state(img) == 'other']
            done.append((p, 'refuse', 'not the JP instructions at ' + ', '.join(bad)))
            continue
        if st == ('missing' if revert else 'applied'):
            done.append((p, 'keep', 'not applied' if revert else 'already applied'))
            continue
        for s in p.sites:
            words = s.old[-1] if revert else s.new          # revert: the cave goes back to NOPs
            struct.pack_into('<%dI' % len(words), img, s.at, *words)
        note = 'reverted' if revert else ('updated from an earlier version' if st == 'outdated' else 'applied')
        done.append((p, 'write', note))
    return img, done


def only_sites_differ(a, b, patches):
    """Do images a and b differ only inside the patches' sites?"""
    if len(a) != len(b):
        return False
    a, b = bytearray(a), bytearray(b)
    for p in patches:
        for s in p.sites:
            n = 4 * len(s.new)
            a[s.at:s.at + n] = b[s.at:s.at + n]
    return a == b


# ---------------------------------------------------------------- commands

def open_main(path):
    with open(path, 'rb') as f:
        main = Main(f.read())
    why = main.problem()
    if why:
        raise SystemExit('%s: %s' % (path, why))
    return main


def cmd_check(path):
    main = open_main(path)
    rc = 0
    for p in PATCHES:
        st = p.state(main.img)
        print('%-16s %s - %s' % (p.name, {'applied': 'APPLIED', 'missing': 'not applied', 'other': 'UNKNOWN',
                                          'outdated': 'OLDER VERSION (apply updates it)'}[st], p.title))
        for s in p.sites:
            print('    0x%06x %-9s %s' % (s.at, {'new': 'patched', 'old': 'JP', 'prev': 'older', 'other': 'other'}[
                s.state(main.img)], s.why))
        if st == 'other':
            rc = 1
    if rc:
        print('some places hold neither the JP instructions nor the patch: another game version, or edited by hand')
    return rc


def cmd_write(path, out, apply, revert):
    main = open_main(path)
    img, done = changed(main, PATCHES, revert)
    for p, what, note in done:
        print('%-16s %s - %s' % (p.name, note, p.title))
    if any(what == 'refuse' for _, what, _ in done):
        print('nothing written')
        return 1
    if not any(what == 'write' for _, what, _ in done):
        print('nothing to change')
        return 0
    raw = main.write(img)
    again = Main(raw)
    if not only_sites_differ(again.img, main.img, PATCHES):
        print('CHECK FAILED: the written program differs outside the patched places')
        return 1
    for p, what, _ in done:
        want = 'missing' if revert else 'applied'
        if what == 'write' and p.state(again.img) != want:
            print('CHECK FAILED: %s reads back as %s' % (p.name, p.state(again.img)))
            return 1
    print('check: OK - only the patched places changed; main %d -> %d bytes' % (len(main.raw), len(raw)))
    if not apply:
        say_replaced(out, ('main',))
        print('dry run - add --apply to write into %s' % out)
        return 0
    write_files(out, (('main', raw),))
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('cmd', choices=['check', 'apply', 'revert'])
    ap.add_argument('main', help='exefs/main of the mod (or the Japanese one)')
    ap.add_argument('--out', help='apply/revert: folder the new main goes to (exefs inside the mod)')
    ap.add_argument('--apply', action='store_true', help='apply/revert: write the file')
    a = ap.parse_args()
    if a.cmd == 'check':
        return cmd_check(a.main)
    if not a.out:
        ap.error('%s: needs --out' % a.cmd)
    return cmd_write(a.main, a.out, a.apply, a.cmd == 'revert')


if __name__ == '__main__':
    sys.exit(main())
