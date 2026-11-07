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
romfs/spec_win/font/*.font.memfs   fonts - not covered here
romfs/spec_win/ssdata/*.memfs  UI art: menu labels and buttons are pixels, see "UI art"
exefs/main                     the VI patch ships a modified one, see "The exe hook"
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
        part states from H, 40 bytes: u32 ?, u16 part, u16 x, y, w, h (source
            rectangle in pixels), i16 position, rest zero here
        pack: ff ff ff ff 'ABSS' u32 3, 0, parts, frames, textures | u16 parts,
            frames, fps (60)
          textures: 0-terminated u32 pointers to names ('mat_ttlm.png' = the
              entry '/mat_ttlm.rtex')
          parts: 16 bytes - u32 name pointer, u16 index, parent, texture, is_null, u32
          frames: 12 bytes - u32 pointer to u16 state indices, u32 0, u32 count
```

A cell is a distinct (texture, rectangle) any frame draws; its parts name it.
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

## VI text inside the patch

The Vietnamese font maps accented letters onto kana code points
(`ệ` → `る`, `đ` → `コ`, …), so patch strings read like garbled Japanese. Search
them by their ASCII fragments. Tags, spaces and ASCII punctuation are
untouched and one VI letter is one code unit, so every tool but
`applysheet.py` works without the mapping.

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

Rows it leaves to the mod's string: `jp_text` not matching the game, a cell
that is still the JP line, a cell with kana other than `っ`/`ッ` (the font
gives those codes to Vietnamese letters; the gasp `っ` is kept on purpose and
drawn, the patch has it in 228 strings), and a second row for a string with
another translation (first row wins). The sheet has no rows for speaker
names and choices - 1 196 translated strings in the 02/10 patch - so a build
needs the mod as its base, never JP alone.

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
- In game: EV00_0001_01 with restored #P, and the u32-widened memfs, load and
  play. The off-screen untagging and the three widened scenes were not yet
  re-checked in game when this was written.
