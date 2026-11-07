# How to use Otome Translator

This guide is for the app window. You choose a tool, fill in its form, and press **Run tool**. You do not type the engine's commands.

## Start with a game

The first screen asks for the game you are translating.

Drop an `.nsp` or `.xci` onto the window, or choose the file. The app reads the names of the files inside and selects the engine:

- **Otomate**, for Otomate and Idea Factory games: `.cpk` archives, STCM2L scripts, `.ffu` fonts.
- **Unity**, for Unity games: bundles and `.assets`, TextMeshPro fonts, IL2CPP code.
- **rrlib**, for Matsurika no Kei -kEi- Tenmei Iniden: `script.memfs` and `.tat` scripts.

If you already know the engine, open **Choose the engine yourself** and pick it. That list also shows every tool the engine has.

## The project folder

A project is a folder on your computer. It holds the original game files, your mod in a folder of its own (`romfs` and `exefs`, ready to share), and that engine's tools.

- **Start from scratch** takes the whole game out into a new folder.
- **Carry on an existing mod** copies your mod into the mod folder of a new project, with the original game beside it.
- **Open a project I made** uses a project folder you created before.

If you have no `.nsp` or `.xci`, take the game out with Ryujinx. Right-click the game, choose **Extract Data → RomFS**, and pick an empty folder. For text that lives in the program, extract **ExeFS** as well. When Ryujinx finishes, choose that folder here.

Taking files out of an `.nsp` or `.xci` needs your `prod.keys`. The app looks in the usual places, including Ryujinx's system folder. An update file is not the base game; choose the base game.

The app does not contain game files, fonts, your translation, or Nintendo keys. It copies the engine's scripts into the project, and it leaves files you have already edited alone.

**Workspace** in the sidebar is the project you are in. **Open folder** shows it in the file manager. **Change** picks another folder. Each engine remembers its own folder.

## Python

The tools need Python packages. Open **Settings**, the gear at the bottom of the sidebar, and choose **Python environment**.

If packages are missing, choose **Install the packages**. That needs the internet and takes a few minutes. The run log shows the progress. A red dot on the gear means this step is still waiting.

You can instead choose a Python that already has the packages.

## Run a tool

The sidebar lists the **tool groups** of the engine you selected. Open a group, then a tool. Search looks through every tool of that engine.

The tool's page says what it does. Fill in the form. A path can be a full path, or a path starting from the project folder. A mark shows the fields the tool cannot run without.

**Run tool** starts the job. **Stop** ends it. The log at the bottom is what the tool printed. Only one tool runs at a time, and the engine cannot be switched until that run finishes.

Drag the right edge of the sidebar when a name is cut off.

## Patch the translation

**Patch dialogue** (Otomate) and **Patch game text** (Unity) are the short path for the last write. They are not the whole translation. The sheet has to be made, merged, and checked first. The steps for each engine are below. **Advanced** stays folded. **Dry run**, inside it, only reports what would change.

## Measure a text box

On Otomate, **Measure text boxes** sits with the groups. The width check uses it to learn how wide a box is.

Choose a screenshot taken in the game while a long line is on screen, after the Vietnamese font is installed. Type that line exactly as it appears, from the first character to the last. Click the start of the line, the end of the line, and the edge of the box. The size of the screenshot does not matter.

There is no byte limit on a dialogue line. What limits it is the box. The backlog is the narrow place to design for, because every spoken line is shown there again. **Find lines too wide** measures with the fonts from the latest **Patch interface**, so run that before trusting the list. Measure with the font you will ship, not the stock font.

## Settings and language

The gear opens **Settings**:

- **Python environment**
- **Check updates**. The app tells you when a newer release exists. It does not download or install that release.
- **Dark theme**

The globe beside the gear sets the app to English or Vietnamese. That changes the app's own words. It does not change the workbook or the translation in it.

The book opens this guide. The info button plays the short tour again.

## Otomate: three separate branches

Dialogue, the interface, and the program file do not depend on each other. Pack each one into the mod when it is ready. Keep a copy of the last `.cpk` that ran before you replace it. **Check story scripts** can pass and the game can still hang: a clean check is not the same as playing it.

### Dialogue, STORY.cpk

1. **Sheets → Create translation sheet.** This reads the story and the menus into one workbook. Do not reorder the columns. English stays in column B and Vietnamese in column C. The tools find those columns by position. Japanese is column D.
2. Translate column C. A cell that is only a space and `#n` is padding, not a line to translate.
3. When translators send a workbook back, run **Create translation sheet** again with that file as the merge, and tick **Relink**. A Japanese-based sheet's ID column steps over empty English cells, so later rows land on the wrong line. Relink throws that column away and matches the rows from the Japanese and English games. **Relink sheet to the game** is the same match on its own.
4. Translate the line that is in the game you are patching. A Japanese column taken from an older cartridge does not match an English build made from a later update. Where they disagree, follow the game.
5. **Find untranslated lines** lists game lines that still have no translation, including lines the sheet has no row for, with where to insert each one and the whole box around it. Read the box. The English in one cell often belongs to the Japanese line next door, because the two builds break lines differently. To insert a row, column A may stay empty, and the Japanese cell must be copied from the game, not retyped.
6. **Export chapter labels**, translate those short prefixes, then **Fill chapter titles**. Do this after a merge and before writing the dialogue. The filled titles are derived: merging again drops them, and running **Fill chapter titles** again brings them back. Excel drops a space at the end of a cell; the tool puts that space back from the original.
7. **Find broken text codes** whenever a new sheet arrives. A mistyped command, such as a color tag missing its closing bracket, is written into the game if this is skipped. The write itself only counts commands that are spelled correctly.
8. On menu rows, do not edit the English in column B, not even a typo. That English is how the menu writer finds the cell. In dialogue, `#Color` and `#NAME` may move to another line of the same version. They may not move into a different version. `#n` may be removed. It may not be added.
9. **Patch dialogue.** Choose the finished sheet and a folder for the result. The app copies the sheet, fills the chapter titles, checks it, and writes the scripts into that folder. The sheet you picked and the game files you started from are not edited. Open **Advanced** for a dry run.
10. **Archives → Repack CPK.** Give it the original `STORY.cpk`, a new file name, and the folder from the patch. Every other file in the archive stays as it was. The new file is much larger, because replacements are stored uncompressed. Copy it into the mod's `romfs`.

### Interface, SYSTEM.cpk

The fonts and the menu text ship in one file, so they are packed once.

1. **Fonts → Make game font**, starting from one of the game's original `.ffu` files. Judge the result at the size the game draws, not at the size of the file. A gap of one or two rows between a tone mark and a circumflex disappears on screen and the letter looks clipped. The mark-lift field is what opens that gap again.
2. **Build → Patch interface**, with the translation sheet chosen. That writes the menu, Options, and Glossary text and packs `SYSTEM.cpk`. Do not run it with no sheet and expect a separate menu write to remain: with no sheet it keeps the data files it already has. **Sample glossary translation** is only a preview of the font. It replaces real glossary text with samples.
3. Do not edit column B of the interface rows. A menu line may use a different number of line breaks than the original. `#NAME`, `#Color`, and `#PosX` have to stay.
4. Copy `SYSTEM.cpk` into the mod's `romfs`. On Windows, **Install** on **Patch interface** can copy it into Ryujinx for you.

### The program file

The title screen shows a quote from the ending you last cleared. Those lines are not in any archive.

1. **Executable → Take out the game's program**, then **Unpack the program file**, then **Create sheet from the program**.
2. The line break in these rows is a real line break, not `#n`.
3. **Write program translation.** A longer line is allowed until the spare room runs out. The tool refuses instead of cutting the line. The result belongs in `exefs`, not in `romfs`.

## Unity

Work on a copy. Keep one dump that you never edit. A tool that writes files runs as a dry run first: if it finds no problem, the app shows where it will write and asks before writing. The package tool still waits for **Build**. Saving over the file you opened keeps a `.bak`.

1. **Dump → Extract game files** for the data, and **Take out the game's program** when you need text that lives in code. An update's RomFS is not read; use the base game.
2. **Inspect → See what's inside a file.** Text is usually a TextAsset, a TextMeshPro box, a string baked into code, or pixels painted into a picture. There is no general tool yet for text painted into pictures.
3. **Text → Export text to sheet.** The workbook has an ID, the source, and an empty Translation column. Translate that column. If a choice list is stored as text inside text, tick **Nested** on the export. The apply step refuses a row whose source no longer matches the file.
4. **Patch game text** writes the sheet back. You can also use **Import edited text files** or **Replace a word** for a small fix.
5. **Layout → Find text boxes**, then **Adjust text box**: size, wrapping, and shrink-to-fit. This does not change a line break the game's code does itself. That case needs **Build code patch**.
6. **Fonts → Check fonts for missing letters.** A font that draws new letters from a file can be swapped with **Replace font**; replace every copy of that font. A font whose letters are already painted into an atlas needs **Test the letter maker** once, then **Add letters to font**. Adding letters only uses empty space in the atlas. A full atlas has to be rebuilt in the Unity editor.
7. **Executable → Find text in the game code**, then **Change text in the game code**. The new text cannot be longer than the old, and an accented letter takes more room. **Build code patch** is for a machine-code change. Leave both until a line really lives in the code.
8. **Release → Package release.** It only prints the plan until you tick **Build**. The zips are for Ryujinx and for Atmosphere.

## rrlib, Matsurika no Kei

The script is not a CPK. It is `common/script.memfs` plus `common/script.membody`. Do not unpack the whole game: almost all of it is voice. The tools are in the app. Try the rebuilt patch in the game before you share it. Fonts in `romfs/spec_win/font` are not handled.

1. **Dump → Take files out of the game**, with the paths `common/script.memfs` and `common/script.membody`. **Take out the game's program** as well. Keep this Japanese copy. A later patch redirects three prologue scripts from the program, so the index alone does not say which bytes the game loads.
2. **Patch → Check a patch** against that Japanese copy. It reports lost position, name, and pause tags, lines hidden off screen, and a bad length, and it changes nothing.
3. **Patch → Rebuild the patch.** The dry run prints a report; say yes when the app asks and it writes `script.memfs` and `script.membody`. Then copy those two files into the mod's `romfs/common/`. Do not copy a Japanese `#P` tag onto a Vietnamese line. Several tags in one Japanese string are usually one paragraph. A longer translation is moved down so lines do not overlap. Twenty-seven Japanese lines sit off screen on purpose, because the words are already painted on the art: those stay without a position tag, or the translation disappears and only the backlog keeps it. Lost `#T` and `#KW` tags are listed for you to fix by hand.
4. **Sheets → Tag fixes for the sheet.** Copy the suggested lines into the translation column. The sheet also says which lines must stay untagged. Fix the sheet so the next rebuild does not drop the tags again.
5. Pack the mod like the original zip: `exefs/` and `romfs/` at the top of the zip, not inside another folder.

The project folder also contains the engine's own notes, such as `README.md` and `DICH.md`. Those describe the scripts and the file formats. This guide is the one for the app.
