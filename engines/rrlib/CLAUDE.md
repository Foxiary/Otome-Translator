# CLAUDE.md

Format notes for **Matsurika no Kei -kEi- Tenmei Iniden** (`0100EA001A626000`,
JP v1.0.0), reverse-engineered from the shipped files and checked in game on
Astrid (a Ryujinx build). The engine names its own index format `rrlib/memfs`,
hence the folder name; no other game has been tried.

The repository holds no game content. Everything below was found on the JP NSP
and on the Vietnamese patch of 02/10/2026 that this engine was built to repair.

## Where the text is

```
romfs/common/script.memfs      index (RSON)            11 406 B
romfs/common/script.membody    130 scripts, compressed 2.08 MB JP
romfs/spec_win/font/*.font.memfs   fonts, see "Fonts" (font.py)
romfs/spec_win/ssdata/*.memfs  UI art: menu labels and buttons are pixels, see "UI art"
exefs/main                     system text as UTF-32 (see "Text in the program");
                               the VI patch ships a modified one, see "The exe hook"
```

`tools/nsp.py` takes single files out of the NSP; the RomFS is 12 842 files and
5.7 GB, almost all voice, so never unpack it whole.

## script.membody

Chunks back to back, no padding, no alignment (`alignBytes` is 1):

```
'RZ'   u32 BIG-endian uncompressed size   zlib stream
```

The JP file mixes compressor settings (`78 da` and `78 9c` headers, some not
reproducible by zlib at any level). Untouched chunks are copied verbatim; a
changed one is recompressed with zlib 9. The game does not care which.

## script.memfs (RSON)

```
'RSON'  u32 file size  u32 root offset  u32 1
0xe8  map    count, 1 byte, 2*count u16 offsets (values, then keys), count u16 hashes
0xc8  array  count, element type (0x20 = u32, 0x30 = u16), elements
0x88  string byte length, UTF-16LE, 00 00
0x41  int 1      0x21  true      0x48 xx  int8
```

**Map offsets point backwards from the map's own tag byte**: target = tag - offset.
The hashes are sorted ascending (binary search); the offsets follow hash order.

Root: `alignBytes` = 1, `hasSeparateBody` = true, `@fileType` = "rrlib/memfs",
`@version` = 0x66, and `path`: a map from `/_bytecode/EV00/EV00_0001_01.tatc`
to `[offset, size]` in membody, size including the 6-byte RZ header.

Layout is depth first - a map's values, then its keys, then the map node - with
NUL padding before an array or map tag so the payload after its 3-byte header
is aligned: 4 for a map and a u32 array, **2 for a u16 array**. `tools/rson.py`
writes exactly that; parse-then-write reproduces the JP and the VI file and all
51 image archives under `spec_win` byte for byte, which is the evidence the
layout is right. (It padded u16 arrays to 4 until the image archives showed
otherwise; in script.memfs both rules happen to give the same bytes.)

### The seven u16 entries

Each `[offset, size]` array is stored with the narrowest element type that fit
when the file was written. In the JP build the first seven scripts in membody
(`common`, `cg_look_back`, `EV00_0000`, `EV00_0001_01`, `EV00_0001_02`,
`EV00_0002_01`, `EV00_0002_02`) are u16, so none of them may start past 65535.
The Vietnamese scripts are 35-45% larger uncompressed, and three of them no
longer fit.

**Widening an entry to u32 works** - the game reads both element types; 123 of
the 130 entries are u32 already. It adds 4 bytes, so every backward offset of
every map after it, the root offset and the file size all change. Rewriting the
whole RSON is safe (done, plays in game). Patching an entry in place is not,
and is the likely cause of the "u32 gives a black screen" the earlier patch
author reported: a memfs that does not parse loads no script at all.

## UI art (sprite.py)

Menu labels, buttons and help lines are **pixels**: the title menu's
新しく始める / ロード / 戻る and its vertical help lines are nowhere in
script.membody or any .rson. Each screen is a memfs/membody pair under
`romfs/spec_win/ssdata/` (`ttlm_nam` is the title menu, 13 files), the same
RSON index with `alignBytes` 1 and the files raw and back to back in the body -
no RZ wrapper around the file itself.

```
.rtex   'RTEX' u32 0 | u16 w, h, padded w, padded h | u32 0x20 (header size),
        payload size, flags, row stride | payload: 'RZ' u32 BE size + zlib, or raw
        flags low byte: 0x02 RGBA8 (straight alpha), 0x14 RGB8, 0x28 8-bit,
        0x33 16-bit; 0x80000 = block-compressed (4 bpp with 0x1000, 8 bpp with
        0x4000), never RZ-wrapped rows then. 0x200000 / 0x400000 seen, meaning
        unknown. Padding rows/columns past w x h are zero and kept.
.ssdata 'SSAD1.03' | u32 header size H | u32 16 | u32 pack offsets, 0-terminated
        part states from H, 40 bytes: u32 flags, u16 part, u16 x, y, w, h
            (source rectangle in pixels), i16 x, y position, then the fields
            the flags add (see "Resizing a cell")
        pack: ff ff ff ff 'ABSS' u32 3, 0, parts, frames, textures | u16 parts,
            frames, fps (60)
          textures: 0-terminated u32 pointers to names ('mat_ttlm.png' = the
              entry '/mat_ttlm.rtex')
          parts: 16 bytes - u32 name pointer, u16 index, parent, texture, is_null, u32
          frames: 12 bytes - u32 pointer to u16 state indices, u32 0, u32 count
```

A cell is a distinct (texture, rectangle) any frame draws; its parts name it.
Export writes it to `<texture>/<part>.png`, `<part>_<x>_<y>.png` when the part draws
several cells, `<part>_<x>_<y>_<w>x<h>.png` when those share a corner (advwin's
`mat_adwin_win`: ten widths from 0,0, which once overwrote one file).
On the title menu `mat_ttlm_com0N_off` / `_on` are the five labels unselected
/ selected (1 新しく始める, 2 ロード, 3 古の調べ, 4 鑑賞, 5 設定),
`mat_ttlm_com0N_setu` their vertical help lines, `mat_nam_bodoru_txt` is 戻る,
`omk_txt` おまけ. Pasting into a cell changes only that rectangle; the game
cuts exactly it, so text drawn past the edge is lost.

Every UI atlas is RGBA8; the title menu's five character backgrounds
(`mat_ttlm_bg_chr0N`, BC 4 bpp), the event CG loops and the transition masks
are not, and sprite.py skips them. Checked in game (Astrid, 2026-11-07): a
ttlm_nam rebuilt by sprite.py with 17 cells redrawn in Vietnamese (the five
labels off and on, the five help lines, 戻る, おまけ; texture recompressed
with zlib 6, membody shorter than JP) loads and shows them as drawn.

### Resizing a cell

A part is drawn **centred on its position**; the origin is the screen centre,
y down. On ttlm_nam the 2020x1180 background sits at (0,0), line_u at y -472,
line_d at +486. Positions are absolute: a child and its null both carry the
same offsets. So a cell can get another size without touching any position,
and it grows evenly to both sides. The rectangle lives only in the states,
not in a cell table, and the .rson holds pattern names only.

`sprite.py import` does it when a cell PNG has another size than its
rectangle:
- It finds empty space in the same texture with `free_spots`. The space must
  not hold any cell rectangle or any pixel with alpha above 0, and keeps
  `CELL_GAP` px clear around it. It is searched on power-of-two blocks so the
  atlas is at most 512 blocks wide.
- It pastes the PNG there and rewrites x/y/w/h of every state that drew the
  old (texture, rectangle), under every part.
- The old pixels stay.
- `verify` re-reads the result: the .ssdata may differ only in those 8 bytes
  of drawn states (`rects_only`).

Which state flags qualify was read from values across all 48 ssdata screens:
- Flags 0x40 (float in degrees), 0x80 / 0x100 (floats near 1) and 0x200
  (0..255) only turn, scale or fade the part round its position
  (`ROUND_CENTRE`).
- 0x10 / 0x20 add an i16 each (mat_kagee, log, losa), maybe a pivot or a
  size in pixels. 0x1, 0x2 and 0x4000 are unknown too.
- A cell drawn by any state with such a flag is refused.
- A state drawn under two textures by different packs is refused as well.

Checked in game (Astrid, 2026-11-08):
- ttlm_nam with eight labels grown, com02-05 off/on, e.g. 178x52 → 276x72;
  their states have flags 0 / 0x200.
- That build is the one `sprite.py import` makes from the same PNGs: every
  one of the 2 787 drawn states cuts the same pixels.
- The labels show centred where the JP ones were.
- 戻る at 266x68 ran off the right screen edge (centre x 1806). Growing does
  not move a part, so a big cell near an edge can leave the screen.

## The exe hook in the 02/10 patch

That patch did not widen anything. It appended the three Vietnamese scripts at
the end of membody, left their memfs entries at the **JP offset with the VI
size**, and hooked the read in `exefs/main`: three call sites (`.text`
0x1c37fc, 0x1c3f5c, 0x2a0fe0) branch into code caves at 0x2f1e00 / 0x2f1f00:

```
if (w3 == 9232  && w2 == 19937) w3 = 2562405;   // EV00_0001_02
if (w3 == 44823 && w2 == 22485) w3 = 2582342;   // EV00_0002_01
if (w3 == 26788 && w2 == 20046) w3 = 2604827;   // EV00_0002_02
```

`main.disabled` in the patch is an older build of the same hook. `tools/exehook.py`
finds these pairs by instruction pattern. Consequences:

- **What the game loads cannot be read off memfs alone.** Looking only at memfs,
  those three scenes appear to load the JP chunks; in game they are Vietnamese.
  That wrong conclusion was reached once - always run with the exe.
- A rebuild must not leave any entry equal to one of the `(offset, size)` pairs,
  or the hook moves it. `tools/patch.py` points entries straight at their
  chunks (u32 where needed) and refuses a collision, so the hook stays installed
  but never fires.

## Text in the program (exetext.py)

Dialog prompts, quick save/load messages, the settings screen's questions,
button help (`{L}{R} タブ切替　{B} 戻る`), glossary entries (`#R(おう,りゅう)応龍`),
chapter and song titles (`幾千の花が咲いて￥ｎ枯れた果てに`) and the script
compiler's error messages live in `main`'s .rodata as **UTF-32LE**,
NUL-terminated. Searches for UTF-8 or UTF-16 find nothing, and nothing at all
is visible until the NSO's LZ4 segments are unpacked. The name-entry prompt is
two strings from one message table, `前回と同じ名前を使用します｡` (0x35f218)
and `\nよろしいですか？` (0x38b8ac). The 02/10 patch left all of them Japanese,
so they draw as Vietnamese letters wherever a kana code carries one.

How the program reaches them, on the JP 1.0.0 main: 783 Japanese strings are
pointed at - 717 `R_AARCH64_RELATIVE` relocations (their in-place value is 0;
the address is the addend), 154 `ADRP`+`ADD` pairs and one `ADR`. 7 runs of
UTF-32-looking Japanese have no pointer; all are binary data. The linker
merges string tails, so a pointer may land inside a longer string.

Only .rodata counts. The glossary table at 0x5557d0 (.data, 124 entries of
32 bytes: u32 heading kana, 0, term pointer, description pointer, ...) starts
with `あ` + 0, which reads as a one-letter string, and both the code
(`ADRP`+`ADD` at 0x10ccb0) and a relocation (0x335528) point at it. The
2026-11-08 14:53 main had it "translated" as `a`: the game then walked the
moved copy, read a NULL term pointer and crashed in `wcslen` (LR main:0x10cd8c)
right after the prologue text when it looked a glossary term up. The tool now
ignores anything outside .rodata.

The glossary is found by text. A script opens an entry with `Mov
GAMESTR_DictWords, <key>` (131 Movs, 124 keys, never shown); the code at
0x10ccb0.. walks the table and calls `std::wstring::compare` on each term,
so a key works only if it equals the term, `#R(...)` taken off, character
for character and after the font encoding. JP: 124/124 equal. The 02/10
build had 82 of 131 keys different from its terms; the 09/11 sheet 71.
`applysheet.py` therefore writes each key from the term `exetext.plan`
produces from the exe tab (`exetext.glossary` reads the table), not from
the key's own cell.

Not all of it is text: 13 strings are names the game looks up and stay
Japanese (`Exe.keys`, left out of the sheet, a filled row skipped as 'key'),
so 770 remain to translate.
- File names. The transition-mask table at .data 0x55ad30 pairs the name a
  caller asks for with the file loaded: `イメージマスクα.png` →
  `imagemask_a.png`, `のぞき見.png` → `window.png`, `風車.png` →
  `windmill.png` (11 pairs). The code at 0x1b90b0.. also matches the request
  with `wmemcmp(name, L"…", JP length)`. The 18:46 main had the left column
  "translated" (`nozokimi.png`, `imagemask_a.png`...), so no request matched.
- Strings handed straight to `wcscmp`/`wmemcmp`/`wcsncmp`/`wcsstr`: `振り子`
  (0x16d488, translated `Con lắc` in that main) and `角度維持`. Found by
  following the first `BL` after the string's `ADD` to a PLT stub (`imports()`
  reads DT_JMPREL + .dynsym); 357 stubs.
Who asks for those masks was not found: no script string pool nor romfs file
holds the names in UTF-8/16/32 or SJIS. That main crashed twice
(2026-11-08, PC main:0x15e5ac, LR 0x1626a0) after many switches between the
settings screen and the main screen: the SpriteStudio player read pack 330 /
339 of opt.ssdata (372 packs, both valid) through its cached data pointer
(player+336, from resource+32) and found other data (pack table values
0xff360026 / 0xe800000a, which read like i16 positions of a smaller ssdata's
states). The JP game without the mod ran 1 min 52 s of that without a crash;
the mod's crashes came after 3:26 and 4:25, and one mod session ran 10+ min
clean. A main with those 12 back in Japanese was installed 20:22; not yet
known whether it ends the crash.

Space: VI is about twice as long, so nothing is rewritten in place. The
module image ends at 0x6a6000 (.data 0x549000 + 0x5f6f8, .bss 0xfd908);
MOD0's bss_end is 0x6a5d70. `exetext.py import` turns .bss into zero-filled
.data (rtld clears that range anyway), appends the translations after
0x6a6000, and repoints: a relocation gets a new addend, an `ADD` (or `ADR`)
becomes `ADRP Xd, page` - exact only for a page-aligned target, so a string
the code reaches starts a page; strings only pointers reach fill the gaps.
The original `ADRP` stays, harmless if another `ADD` shares it. A table at
the start of the new area keeps every changed value and a trailer
`RRLBTEXT` + its address closes .data, so the tool undoes its own earlier run
before writing a new one. Segments are written uncompressed with their
SHA-256 recomputed; Ryujinx and Atmosphere take either.

Font: same mapping as the scripts (`applysheet.py --map`), plus `ĩ`/`ũ`, which
the mod's scripts write at their own code (5 961 times) so the learnt map does
not list them. `、` is the font's `ừ`. A `%d`/`%ls` that differs from JP is
refused: printf would read the wrong arguments.

Seen in game on Astrid (2026-11-08): a main with only the name prompt
translated (`~/Documents/Game/matsurika-exetext-test-2026-11-08`) boots and
shows both halves in Vietnamese. That proves the uncompressed NSO, the
.bss-to-.data area and repointed relocations; both strings are reached through
relocations, so a translation the code reaches with ADRP (`refs` "code") has
not been seen in game yet.

## .tat scripts ("KUV ")

```
[0] c0deabc1  [1] 'KUV '  [2] 0x64  [3] 0xc4 header size
[4] string count   [8] label count
[10] string table: (u32 offset in pool, u32 byte length) per string
[16] pool: UTF-16LE strings, each NUL-terminated
[17] end of pool + padding   [18] code start   [19] code length
0x60 script name (UTF-16)    0xa0 build date
```

Code addresses strings **by index only**: `0e` + big-endian u32 pushes string N,
`2b 2c argc 00` calls the function whose name was pushed last, with the argc
pushes before it as arguments. Other opcodes exist (flags, branches) but no
string is ever reached by offset, so strings can change length freely and the
code is copied byte for byte. Every VI script keeps code identical to JP.

The 02/10 build wrote `[19]` as code length + pool growth in 10 files
(`EV03_0008_01`, seven `EV05_*` scripts, `EV06_0005_01`, `EV06_0007_02`). The game tolerated it;
JP never has it; `kuv.build()` always writes the true length.

Message calls: `NameMess(name, text)`, `GuideMess(text)` (narration), then `KW`
(wait for a click). `WinClear` empties the window; `WinFrame(ON/OFF, mode)`
switches the frame. **GuideMess text accumulates until `WinClear`** - several
narration lines share one screen by design.

## Inline tags

| tag | meaning | lost by the 02/10 translation |
|---|---|---|
| `#P(x,y)` | draw from (x, y), 1920x1080 screen | 1 294 strings |
| `#T1…#T2…#T0…` | text for heroine "Naya" / for `${FirstName}` / both | 140 - both versions show at once |
| `#KW` | wait for a click mid-message | 33 |
| `#C(TR,0xRRGGBBAA)…#C(TR,prev)` | colour | mostly kept |
| `#R(reading,…)base` | ruby | dropped on purpose |

Without `#P` a narration line falls back to the default spot at the bottom,
and since GuideMess accumulates, the next line follows right under it - "two
boxes shown as one", which is what the bug report was.

### Putting #P back (tags.py)

Copying the JP tag in front of the VI line is wrong in four cases, all real:

1. **Several tags in one string** are usually one paragraph wrapped by hand
   (same x, one line lower each time), text continued along one line (same
   y), or #T variants at one spot (same x and y). Fold those into one block.
   Only 45 strings really need splitting; split at the boundary closest to the
   JP proportions, sentence ends first.
2. **VI has more lines than JP.** Positions on one screen (messages between
   `WinClear`s) are stacked: push a block down until it clears the one above,
   pull the screen up if it then runs past the bottom.
3. **Line pitch differs by screen.** 60 px on most (817 of 1 273 stacked JP
   pairs sit exactly one 60 px line apart), ~75 px on the black-screen
   monologue (measured off a screenshot: two lines 72 screen px apart at a
   0.957 scale). JP never overlaps, so its tightest gap on a screen bounds that
   screen's pitch; clamp to 60–80.
4. **Off-screen on purpose.** 27 JP strings sit at y = 1200, below the screen:
   poems and narration whose text is already painted on the art (the opening
   scroll shows 天地長不没 / 山川無改時). The backlog still logs them. A
   translation must be visible, so these stay **untagged** - restoring the tag
   hid the poem in game once. The 02/10 build had kept that tag on 6 lines,
   hiding them; `strip_offscreen` removes it.

Widths: the VI builder wraps at **62 visible characters**; one character is
**~18.4 px** (59 characters spanned 1 099 px from x = 497 on screen). A line may
run to **x = 1800**; JP goes as far right as x = 850 + 24 full-width chars. A
screen's last line should end by **y = 1000** unless JP itself goes lower.
These are measurements, not engine constants; nothing clips, text simply
draws over the art.

## Line widths (overflow.py)

The engine never wraps and never clips: a line breaks only at a `\n`, and a
line too wide for its box draws past it. Measured 2026-11-08 on three
screenshots of the installed build (2000x1115 window, so x scale 2000/1920),
by fitting word starts against the font's advances:

| where | font | scale | text from | stops at | source |
|---|---|---|---|---|---|
| story line with `#P(x,y)` | settings choice | 1.05 | x | 1920 (screen edge) | EV00_0001_01 #352 at #P(520,200): fit 1.047 / 1.048, offset 517 / 521 |
| backlog | settings choice | 0.90 | 240 | 1258 (cyan name strip) | same lines in the backlog, correlation 0.84 at 0.900 |
| glossary popup (advjisyo) | **extra2** always | 1.05 | 576 | 1362 (paper edge) | the Huỳnh Thanh entry, fit 1.053, while the story behind it used standard |
| message window (no `#P`) | settings choice | 1.05 | 170 | 1374 | **estimate**: advwin `text_atari` 48x48 at x 167..215; the face picture `mat_adwin_facepic` covers x 1243..2063, the page arrow `mat_adwin_okuri` 1374..1474 |
| choice button | settings choice | 1.05 | centred | 760 wide | **estimate**: `mat_advsen_texbase` is 840 wide |

The story draws the 40 px fonts at about 42 px and the backlog at 36 px. The
window art (`mat_adwin_win`) is a translucent band across the whole screen;
nothing in it stops a line, so its limit is where the face picture starts to
matter. JP's widest window line ends at 170 + 1134. A screenshot of a long
window line and of a long choice would turn the two estimates into
measurements (`--window-right`).

The glossary table (see "Text in the program") gives each description's
string; exetext's undo table gives the VI one. JP wraps descriptions by hand
at 17 characters; the 2026-11-08 VI main has most as one long line.

What the installed build showed: with `standard` (FertigoPro) at 20.8 px a
character, a 62-character line is ~1290 px and the backlog holds ~1131, so
about 22 000 strings run under the name strip; `extra` at 18.2 px is right
at the limit (6 750 lines over), `extra2`/`extra3` fit. That is a font size
question (`font.py gen --px-standard`), not one of translation. At 20:17
standard (+ outline) was rebuilt at 34 px from the same sources and map
(`font.py gen` reproduced the 43 px file byte for byte first): 17.0 px a
character, backlog lines over 33 808 -> 303, most of them the junk below or
strings the builder never wrapped (EV01_0006_01 #539). 36 px left 3 413, 35
px 793. Not yet seen in game. A rebuild of all ten fonts at 20:10 (not this
session) had made extra2 17.9 and extra3 17.3 px a character.

One translation serves all four settings fonts, so the fonts have to agree:
a string should run out in every font (the line's fault) or in none.
`overflow.py` reports both kinds (`kieu tran`, CSV column `fonts`). With
the 20:10 fonts + standard 34: 296 strings in every font, 5 972 in only
some (extra 5 969). Shrinking alone, standard 32 / extra 38 / extra2 34 /
extra3 36 leaves 121 and 17. Simulated (advances x 0.9, not built): the
user's plan of -10% width at the fitted sizes brings extra / extra2 / extra3
to 138 / 116 / 114 strings, 111 of them shared, but standard needs 37 px on
top of it (14 469 -> 136). The ~111-125 strings over in every font are the
EV04 junk, strings never wrapped and #P lines placed too far right. The same run
found 44 over-wide strings in EV04_0008_02 that read "JP text,Speaker,VI
text" - a CSV row pasted whole. That script has 112 such strings and 75 that
end in ",,,,,", and the sheet holds them too (see "Pasted CSV rows").

`font.py gen --width PCT` (and `--width-<family>`) draws every glyph PCT% as
wide at the same height: the glyph is drawn as before, then the drawing is
resized horizontally round the pen with BOX (area averaging), and the
advance is the source advance times the factor. LANCZOS was tried first: its
ringing left a faint halo that tracking() counted as ink, so UVN La Xanh at
90% "touched" and got +2 px, ending wider than at 100%. Width 100 rebuilds
the installed fonts byte for byte. Built and measured (overflow.py, 4 fonts):
standard 80% at 40 px, extra 85%, extra2 90%, extra3 90% (fitted sizes 45 /
39 / 41) gives 16.1-16.4 px a character for all four and 125 strings over in
every font, 21 in only some - the most even set tried. extra2/extra3 keep
their +1/+3 tracking at 90%. Installed into the Astris mod 2026-11-08 21:29 with
font.py gen (older files kept as .bak8/.bak9); overflow.py on the mod then
reports the same 125 + 21. Not seen in game yet. UVN La Xanh's tilde is a
flat stroke that reads close to an acute at game size, at 100% as at 85%.

2026-11-10 the user swapped extra / extra2 / extra3 for LF Nghich Thuy Han
(45 px, width 82%), LF Rancho (44 px, 103%, +1 tracking) and LF
Brainstroke Condensed (52 px, 100%, space 14 px, see "Spacing"): 16.2 /
15.2 / 16.0 px a character against standard's 16.1. At their fitted sizes
and full width they were 19.2 / 12.8 / 12.9. extra2 stays a little narrower
because it is also the glossary font: at 104% (15.8 px) five descriptions,
wrapped by then for the old extra2, ran up to 25 px past the paper; at 103%
none. A narrower font only ever overflows a subset of the others' lines, so
the translation is still fixed against one width. Rancho at 48 px cut the
outline of the stacked capitals (Ằ Ắ Ẳ Ấ Ẩ Ệ Ộ Ỳ). overflow.py on the mod
afterwards: 11 strings over in every font, 23 in only some (none in
extra2), glossary 0. Installed with font.py gen (previous at .bak9, extra3
at .bak10); not seen in game yet.

The same day extra3 became LF Oregano Regular at 48 px, width 98% (fitted
41 px gave 13.6 px a character; 50 px cuts the outline of Ệ Ộ). Its average
is 15.8 px, but at 100% it ran out on more window lines than standard
(19 against 15): compare the per-font line counts, not only the average.
At 98% it is 14 window / 24 backlog lines against standard's 15 / 27.
Its own space is 9 px, so the median word gap is 10 px against 14-16 in the
other three: about 2 px clear between the outlines, words still apart in
the preview. overflow.py on the mod: 11 strings over in every font, 26 in
only some. Brainstroke is at .bak11, the 100% Oregano at .bak12.

Then extra2 went to 50 px, first at width 91%, then 100%: the user found the glossary text small
for its line pitch (in game screenshot, Rancho at 44 px; its x-height is low).
The 60x62 cell caps the size. Every glyph keeps its whole outline up to 46 px.
At 47-50 px the outline is thinned at the top or under the dot of the
capitals with two marks (50 px: Ằ Ắ Ẳ Ầ Ấ Ẩ Ậ Ề Ế Ể Ệ Ố Ổ Ộ Ợ Ự Ỳ Ý Ỷ),
hardly visible at 2x zoom. From 52 px nearly every accented capital loses
some (À Á É ...). Width and tracking interact: at 50 px Rancho's letters
clear each other at 100% and get no tracking (15.7 px a character), while
96% and 91% fall under TRACK_GAP and get +1 px on every advance (16.0 /
15.4). So 100% is narrower than 96%, and narrower than 44 px at 103% with
its +1 (five glossary descriptions over at 104%). At 50 px / 100% the
glossary has 0 overflow and no line within 30 px of the paper. The 44 px
build is at .bak10, the 91% one at .bak11.

## The translation sheet

Google Sheet, one tab per script, columns `record_id, command, script,
const_index, jp_text, vi_text, …`. `const_index` is the KUV string index, so a
row maps to the game by it. Two traps:

- The sheet writes `\n\n` where the game has `\r\n`; 12 796 rows compared
  unequal until line breaks were ignored.
- One game string can have two rows (the same line in two branches) - twice
  with different translations, of which a build can use only one.

The sheet is newer than any build: compare against it, not against strings
pulled out of a patch.

`tools/extractsheet.py` rebuilds the sheet from the JP scripts. Its rules,
read off the team's sheet and reproduced cell for cell on its first
download (31 100 rows, every non-translation column):
- one row per call of NameMess (argc 2), GuideMess (1), SltAdd (3) and
  `Mov GAMESTR_DictWords, key`, in code order; record_id runs across
  scripts in script.memfs map order (= block_index), not membody order;
- a call is left out when neither its text nor its speaker has a letter,
  kana or kanji once tags and `${FirstName}` go: the heroine's 「……！」
  (and ？？？'s), narration of dots - 86 calls;
- jp_text writes `\r\n` as `\n\n`; all_args_json joins each `\n` plus
  the newlines/spaces after it into one space and keeps `\r`;
- rz_kind is the top 16 bits of the chunk's uncompressed size, offsets are
  in the uncompressed .tat (const_offset = pool + string offset).
The later downloads differ only in 522 jp_text cells that lost `――` to a
find-and-replace (see applysheet's dash rule).

## VI text inside the patch

The Vietnamese font maps accented letters onto kana code points
(`ệ` → `る`, `đ` → `コ`, …), so patch strings read like garbled Japanese. Search
them by their ASCII fragments. Tags, spaces and ASCII punctuation are
untouched and one VI letter is one code unit, so every tool but
`applysheet.py` works without the mapping.

## Fonts (font.py)

Ten files under `romfs/spec_win/font`: `standard` (rounded gothic, the
dialogue), `extra` (bold gothic), `extra2` (brush), `extra3` (serif, old-style
figures), `ui` (1 903 glyphs, 2 textures), each with an `_outline` twin that is
the border drawn under the text. The 02/10 patch redrew texture 0 of all ten
(VI letters painted over kana cells) and changed only the advance of those 97
cells in `standard`; it added no glyph, so the `ui` font has no cell at all
for codes such as ヰ or ㈶ that the encoding uses.

The exe (JP `main`, data at 0x549138) lists them in a table of 24-byte entries
{u64 id, path pointer (UTF-32 string, RELATIVE reloc), u64 flag}: ids 1-10 =
standard, standard_outline, extra, extra_outline, extra2, extra2_outline,
extra3, extra3_outline, ui, ui_outline; flag 1 on standard, standard_outline
and ui. The four フォント choices of the settings screen (一 二 三 四) follow
that order (一/三/四 = standard/extra2/extra3 read off the order; `ui` is not
one of the four).

The sample line under them is NOT drawn with the font: it is four pictures
in `ssdata/opt` (texture mat_opt), cells `mat_opt_win_txt01`..`04`, the
prologue line 「人々を救うって……」 (EV00_0001_01 string 560) pre-rendered
once per font. A screenshot of 二 matched `extra` glyph for glyph only because
the art was made with the same font. So the settings screen stays Japanese
and never shows a rebuilt font, whatever font.py writes (user, 2026-11-08,
extra3 installed, sample still JP). Judge fonts on story text, or redraw those
four cells with sprite.py.

A font is an rrlib/memfs with its body inside (`hasSeparateBody` false), and
uses more of RSON than `script.memfs`, so font.py has its own reader/writer
(rson.py untouched). Found on these files and checked by byte-exact round trip
of all 20 fonts (JP + mod) and 56 other memfs of the game:

```
tag    kind (top 3 bits) | size code (low 5)
size   0-7 the value; 8-15 +1 byte, 16-23 +2, 24 +4; code's low 3 bits are the
       top bits; BIG-endian. Lengths and counts use at least the 1-byte form.
0x20/21  false / true
0x40   int: codes 0..7 = 0,1,-1,2,-2,3,-3,4; 1/2/4-byte forms are 11/19/32-bit
       two's complement (offsetY -19 = 4f ed, 2048 = 50 08 00)
0x80   UTF-16LE string, byte length, + 2 NULs; text 2-aligned
0xa0   binary blob, data aligned to alignBytes (4)
0xc0   array: count, element byte. 0x40/0x30/0x20: u8/u16/u32 LE values,
       narrowest that fits (negatives as u32). 0..3: node offsets of 1..4
       bytes - 2-byte ones LITTLE-endian, 3-byte ones BIG-endian (ui has the
       first, the others the second). Payload 4-aligned for node arrays, to
       the element size for typed ones.
0xe0   map: count, h, value offsets (u16 LE; u32 LE when h=1, used when one
       does not fit), key offsets u16 LE, key hashes u16 LE = CRC-16/CCITT-FALSE
       (init 0xffff) of the UTF-16LE key, sorted by hash ('alignBytes' and
       'paddingBottom' collide at 4064). Payload 4-aligned.
       Children first (values, keys, then the map), offsets back from the tag.
```

Not handled: map h=3 (`spec_switch/sound/voice.memfs`) and an unknown tag 0x00
in `spec_win/effect.memfs` - neither is a font.

`/fontdata.rson` (`rrlib/rfnt2`): `baseInfo` - charWidth/charHeight 40,
renderMarginX/Y 20/22, offsetX/Y -8/-19, packMarginX/Y 1, paddingBottom 8,
2048² textures, `rgb` FFFFFF, `bTrimGryph` false, `charaCount`; `gryphInfo` -
per glyph [texture, x, y, w, h, advance, dx, dy]; `charToIndex` - one-character
key → glyph. Cells are 60x62 on a 62x64 grid, packed column by column (33x32 =
1 056 per texture). In a cell the pen sits at x 8 (-offsetX) and the baseline at
row 53 (52 in extra/extra3/ui); 'H' is 32 px tall in standard.

dx/dy (usually 0/7) move a glyph whose ink would leave the cell. The JP 'p'
sits 3 px higher in its cell than 'o' with dy 10, 'g' 2 px with dy 9, 'î' 3 px
to the right with dx -3; so the engine draws a cell (dy-7) lower and dx further
left. Inferred from the cell contents (the bowls of p/q/g line up with o once
moved back). dx seen on screen 2026-11-08: an extra3 line in game (T and s
with dx -3, Đ -2) matches the same line laid out with dx as a left shift
(IoU 0.291) better than with dx ignored (0.276) or reversed (0.248). dy not
yet confirmed on screen.

The JP fonts keep only the text in the cell: their g/p/y end on row 59, and
the outline under them (4-5 px wider) is cut flat on row 61 in all four
settings fonts. A VI g's round tail made the cut show (user, 2026-11-08).
font.py gen (`place()`) keeps ink right of x 7 and above row 59 as JP does,
and also leaves the family's outline width (`outline_room`: 5 px for
standard/extra/extra2, 4 for extra3/ui) clear on every side, the same in the
font and its _outline. With the user's fonts at their fitted sizes no glyph
loses any outline (before: 58 in standard, 54 extra, 54 extra2, 10 extra3,
9 ui). That puts g at dy 13 and moves the stacked capitals of
standard/extra (Ằ Ẳ Ẩ Ể Ổ...) DOWN, dy 5-6: the JP fonts never go below dy 7.
Neither was seen in game yet. A glyph too tall for its room keeps the text
whole and is reported (`vien bi cat`).

### Spacing

The game lays a line out by advance alone (scaled: 1.05 in the story, 0.9 in
the backlog, see "Line widths"):
- no kerning, no contextual forms;
- every letter gets its `_outline` drawn under it.

The JP Latin was never meant for running text. Median clear space between
neighbouring letters' ink, VI sample laid out by the JP advances: standard
+1.5, extra +2.8, extra2 +0.4, extra3 -1.8 px. extra3's space is 7 px, the
others' 12-14.

A joining script keeps its overlap by design: each letter reaches past its
advance into the next, which the font's own kerning and alternates join up.
- VL Ricca Script (the user's extra3) measures -3 px at 30 px, and so does VL
  Kathya (extra2).
- In game the black-screen narration in extra3 ran into one outlined blob
  (user's screenshot, 2026-11-08):
  - 11.8 px per character, exactly what `preview` draws from the same font;
  - word gaps of 3 px, less than the 4 px outline.
- It was not the size: H is fitted to the template's 29 px and the advances
  come from the same drawing.

`gen` measures that median on SAMPLE as it draws (`tracking`). Under
`TRACK_GAP` (1 px), it adds the difference to every advance it writes and to
the space's:
- Ricca and Kathya +4, DL Thu Phap (ui) +2;
- FertigoPro and UVN La Xanh measure +2 and get nothing; standard and extra
  come out byte-identical to the build before.
- Glyphs, dx/dy and textures do not change. The rebuilt extra3 differs from
  the installed one only in 229 advances (+4).

The space keeps the template's advance unless the new font's own space, at
its size and width, is wider. LF Brainstroke Condensed's is 14 px at 52 px
against extra3's JP 7; with 7 its word gaps were half the letters' width
and barely wider than the 4 px outline. The fonts installed before all have
a narrower own space (FertigoPro 7, UVN La Xanh 10, SignLanguage 8,
Andalusia 5 px), and the 2026-11-08 set rebuilds byte for byte with the rule.

The dry run's "too wide" warning compares against the wider of the template's
Latin and `LINE_CHAR_PX` (18.4 px, what the scripts are wrapped for).
extra3's own 12 px Latin would flag every readable font.

Not yet seen in game.

Textures: RTEX flags 0x84002 = BC3 (DXT5), LINEAR block order (no Switch
swizzle), payload RZ + zlib. Alpha is the glyph; RGB a white mask 1 px wider
than the ink (in an _outline font the same as its alpha's extent). The
_outline glyph is the text glyph widened by a radius that best fits each pair:
standard 4.7, extra 5.0, extra2 4.3, extra3 4.0, ui 3.2 px. An empty block is
`00 05` + 14 zero bytes. gen re-encodes only the blocks of cells it draws (no
block straddles two cells: the 2 px gaps line up with 4x4 blocks), so every
other glyph keeps its exact bytes.

Adding a character = a new cell in a free grid slot of the last texture, a
gryphInfo entry, a charToIndex key inserted in hash order and charaCount + 1.
The last textures have room (standard 972 free cells, ui 209). Whether the
game finds an added character has not been seen on screen yet.

## Writing the sheet in (applysheet.py)

The original VI builder is not available; its rules were read off the 02/10
patch by putting each sheet cell next to the string the patch carries for it.
Where the cell's text is still the patch's, these rules reproduce 93.6% of
the strings byte for byte (23 776 of 25 410):

- NFC, then `「」『』“”` and U+200B dropped, `"` written as `'`, U+3000 as a
  space. No translated 02/10 string carries any of them; the font most likely
  has no glyph for them.
- The sheet's doubled line breaks folded to one (it shows the game's `\r\n`
  as two), each paragraph wrapped at 62 visible characters
  (`tags.builder_wrap`), lines joined with `\n` - the patch never has `\r\n`.
- Letters encoded for the font. Latin-1 letters (`à á â ô ý …`) keep their
  code; the other Vietnamese letters, capitals included, sit on kana or
  enclosed CJK codes (`ư` → `ゔ`, `Ừ` → `ガ`, `ỳ` → `㈹`), and `Đ` on U+00D0.
  The table is learnt from the mod each run: a row counts when cell and mod
  string are as long once tags and whitespace go and every ASCII letter and
  digit lines up; a code is taken at 80% of its sightings. 68 letters come
  out of the installed build. A capital the mod never used falls back to its
  small letter and is reported.

The remaining 7% is where the builder was wrong and the sheet is not: it lost
#P (642 strings) and #KW (24), and it flattened cells with several #P or #T
parts into one wrapped paragraph - the #T2 text then breaks mid-sentence,
because the #T1 text it never shows is counted into the line. applysheet
keeps the cell's tags and lines, which follow JP.

**Wrapping by width (2026-11-10).** 62 characters is a count, not a width:
with the 2026-11-10 fonts, 37 strings still ran out (lines full of `……`,
whose `…` is a 40 px JP glyph, and #P lines placed far right, which got the
same 62 as a line from x 170), while most lines left room unused. And a
**backlog entry holds 3 lines**: JP has no message string over 3 (30 417
counted), and the 2026-11-10 screenshot of EV01_0007_03 #474 in the backlog
shows its 4th line drawn over the entry's bottom edge. The VI build had
1 100 strings of 4-5 lines.

applysheet now wraps the ENCODED text with `overflow.fit_wrap` (the encoding
is one code per letter and keeps spaces and tags, so the mod's fonts measure
it directly). Default rules:
- every paragraph is filled up to the room of its boxes in the widest of
  the four settings fonts: the window (or the screen from its #P x) and the
  backlog (1131 font px, the tightest for window lines) - no character
  count (`--chars N` adds one; `--chars 62` keeps a paragraph that fits as
  builder_wrap had it, byte for byte);
- a #P block that would grow is first refilled as one paragraph. A placed
  block has a fixed height on its screen: EV01_0007_01 #97 wrapped
  paragraph by paragraph got a fourth line on the row of the #P(230,880)
  block under it;
- a string still over 3 lines gets the paragraphs of a block (the cell's
  own line breaks) refilled as one, block by block, where that saves lines
  (`--max-lines 0` keeps them); a blank line is kept as spacing;
- #T variants are wrapped one at a time and every break of either goes in.
  A break inside a #T1/#T2 part exists in that variant only; one in a
  shared part in both, which can only shorten the other variant's lines.
  Wrapping the tagged text as one (the old builder, and the first version
  of this) left EV01_0009_01 #251's #T1 text one line 779 px wide - its
  break sat in the #T2 part - and could not break EV06_0009_01 #158, whose
  #T1 and #T2 parts are whole sentences on lines of their own.
On the 10/11 sheet with the installed fonts: 20 312 strings wrapped
differently, 4 590 with fewer lines, 9 with more (no #P block), 28 cells
had their breaks joined; overflow.py finds no line past the screen, the
window or the backlog (2 choices left, which the sheet does not carry), and
384 strings still over 3 lines: 361 too long to fit in 3 even filled (the
translation must get shorter), 20 with several #P blocks, 3 with #T. The
report names each. `--fonts` measures another folder, `--chars-only` is the
old rule. Rebuild the scripts after changing fonts. overflow.py reports
strings over 3 lines (`qua 3 dong`, CSV box "backlog N dòng").

**Tags are the translator's call.** applysheet writes every tag as the cell
has it and puts no lost #P back (`patch.build(restore=False,
untag_offscreen=False)`, `patch.verify(..., check_tags=False)`). Whether a
line should carry a tag is decided by whoever edits the translation;
`audit.py` on the build and `sheetfix.py` on the sheet report what is missing
or hidden. Two faults are mended in `fix_tags` (and reported), since the
line is broken in game either way - the 09/11 sheet carried 27 and 4:
- every #P of the cell off the screen (`tags.all_offscreen`): tags dropped.
  JP hides the poems the art already shows (`#P(520,1200)`); a translation
  kept there is readable only in the backlog (the user hit it 2026-11-07).
- `#P(1110220),` - a CSV round trip moved the comma out of the tag: the JP
  string's tag whose x and y read so is put back.

Rows it leaves to the mod's string: `jp_text` not matching the game, a cell
that is still the JP line, a cell with kana other than `っ`/`ッ` (the font
gives those codes to Vietnamese letters; the gasp `っ` is kept on purpose and
drawn, the patch has it in 228 strings) or a kanji outside brackets (a kanji
in brackets is a gloss, `tộc Hoa (嬅)`, and no letter sits on a kanji code -
`exetext.japanese_left`, shared by both tools), and a second row for a string with
another translation (first row wins). The sheet has no rows for speaker
names and choices - 1 196 translated strings in the 02/10 patch - so a build
needs the mod as its base, never JP alone.

### Pasted CSV rows

Tab EV04_0008_02 (and nothing else in the 07/11 sheet) has 188 cells that
are not a translation:
- 113 hold a whole row of an older CSV export: `JP,Speaker,VI` on NameMess
  lines (`…,Ko Ouyo,「…」`) and `JP,VI,,,,,` on narration.
  - The JP part is jp_text without ruby, with 、。 as `,.` and line breaks as
    spaces, and once a typo (`余エに` for 余計に).
  - The translators edited the VI inside it, so the VI part is current.
- 75 hold the VI followed by the empty columns `,,,,,`.
- The 02/10 patch carries the same strings, and so did every build from the
  sheet. Before the guard, applysheet skipped 108 of them for their kana and
  kept the mod's equally broken string. It wrote the other 79 with the junk
  in, because their JP part has no kana (`「――……」`) or there is no JP part.

`csv_row` now takes the VI part:
- The JP part is the cell before a comma that matches jp_text at 85% as the
  export wrote it (`csv_jp`), scanning only while no Latin letter has
  appeared.
- On a NameMess line the next field is the speaker; trailing empty columns
  are dropped.
- The report and the summary line name each such row, so the cell can be
  cleaned in the sheet. That includes a second row of the same string that
  cleans to the same text (string 101), reported as 'same'.
- The same export left two more kinds of junk, which `cleanup` also takes
  off (2026-11-08):
  - 207 NameMess cells in 9 other tabs open with the speaker's name,
    `Fey,「Dừng lại……!」`, often an older spelling than speaker_vi
    (`Kỷ Uyển` / `Quý Uyển`). The installed mod showed it in the line.
    The rule applies only when the JP opens with a quote; a name may have up
    to 40 characters.
  - 5 cells open with a comma; it is kept where the JP line opens with 、.
  - With all four kinds, 393 strings change against the committed tool, all
    from cleaned cells.
- String 124's JP has #T1/#T2 variants; its CSV text has no #T, so the
  heroine is called Naya whatever her name. The cleaned cell keeps that until
  a translator adds the tags.

## Verified

- `rson.py check` on the JP and the VI memfs: byte-identical.
- `kuv.py check` on all 128 scripts: identical except the 10 bad length fields.
- `patch.py` on the 02/10 patch + JP reproduces, byte for byte, the build that
  was installed and played (positions in the black-screen monologue confirmed
  on screen at (500,130) and (500,280)).
- `exehook.py`: 3 pairs in the patched `main`, 0 in the JP `main`.
- `sheetfix.py` reproduces the correction workbook cell for cell.
- `applysheet.py` on the 07/11 sheet and the installed build: 30 470 strings
  written, check OK, no translated string turned back to JP, 0 #T / #KW lost
  against JP (the translators had fixed them). Not yet tried in game.
  With the pasted-row guard (2026-11-08), same sheet: 30 578 written. The 188
  rows are found in EV04_0008_02 only, and their VI matches a hand-made
  cleanup. The only strings that change are 187 of EV04_0008_02, none of
  which keeps `,,,,,`, `,Ko …,` or a kanji.
- `font.py check`: all 20 fonts (JP + 02/10 mod) byte-identical. `gen` with
  the 70-letter map learnt from the mod: only the drawn cells' blocks change.
  Not yet tried in game.
- In game: EV00_0001_01 with restored #P, and the u32-widened memfs, load and
  play. The off-screen untagging and the three widened scenes were not yet
  re-checked in game when this was written.
