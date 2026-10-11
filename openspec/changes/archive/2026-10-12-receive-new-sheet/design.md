# Design

## Context

The app is an Electron shell over two Python engines. `src/main.js` runs one catalog tool at a time and can cancel that process. `settings.json` already stores the active engine, one workspace folder per engine, and saved form values. The window is a tool list plus a form (`src/index.html`, `src/renderer.js`). Tool cautions already live on each catalog entry's `note`. See proposal.md for why the guided flow exists. Behavior is fixed in the four delta specs.

## Goals / Non-Goals

**Goals:**

- Drive Create patch by sequencing existing catalog tools, with one shared runner and a different recipe per engine.
- Keep the translator's chosen `.xlsx` out of every tool output path.
- Reuse the current single-process run and cancel path so a patch run and a manual tool run cannot overlap.
- Add the Create patch page, the tool browser, and English/Vietnamese interface strings without a second settings store.

**Non-Goals:**

- A new Python orchestration entry point inside VE-ES or `engines/unity`.
- Installing a patch, publishing it, or comparing it with a previous release.
- The wireframe's sample runs.
- A control that continues creation while a blocking finding remains.
- Removing the existing per-tool form.

## Decisions

### Sequence catalog tools instead of adding an engine entry point

Create patch is a recipe in this repo: an ordered list of steps tagged `prepare`, `check`, or `create`, each naming an existing tool id and how its arguments are filled. The main process walks the recipe with the same spawn and cancel path as `window.vees.run`.

Otomate, on a working copy of the sheet: `filltitles-fill` (chapter titles), then `quarong` (lines wider than their window), then `applyvi` into the output folder. Unity, on a working copy of the sheet: a read-only empty-translation scan, then a read-only layout check against the project's text boxes, then `jsonsheet.py apply` writing only under the output folder. `build.py`, `release.py`, and `translate-glossary` are not steps of this recipe.

Alternative considered: one new shell script per engine. Rejected because stop, logging, and the one-run lock already live in the Electron runner, and a script in the Otomate submodule would have to be versioned apart from this UI.

### Never pass the original workbook as an output

The first recipe action copies the chosen `.xlsx` into a run directory under the engine's output folder. Later steps receive that copy. No step is given the original path as a file it may write. If the copy cannot be made, the run stops before any tool starts.

Alternative considered: telling each tool to write beside the original and then restoring it. Rejected because a crash between write and restore would change the translator's file.

### Blocking findings stop the recipe before create

`quarong` writes its report only inside the run directory. A small read-only scanner, run with the app's Python and openpyxl, lists empty translation cells (column C) as `{sheet, row}`. Unity layout uses the box data `tmp.py list` already knows how to read, pointed at the project workspace, and flags a sheet row whose translation does not fit that box. Any empty or overflow finding ends the recipe before the create step. The UI lists those locations and asks for a corrected `.xlsx`. It has no skip or continue control. A non-zero check exit, or a report the app cannot read, is also blocking: the patch is not created.

Alternative considered: parsing only human log text. Rejected because a log wording change would hide a real overflow and the create step would still run.

### Ask before the create step writes over an existing patch

When checks have passed and the output folder already contains patch files from an earlier run, the UI asks before the create step starts. Declining leaves those files in place and does not mark the run complete. Confirmation is not asked for the working copy in the run directory.

### One run flag covers both the recipe and the tool form

While a recipe step or a manual tool is running, engine switching and opening the tool browser or the tool form are refused. Cancel aborts the current process and does not start the next recipe step. Files that finished steps already wrote, including the run directory, stay on disk. Interface language can still change: it only re-renders labels.

The tool browser lists the active engine's catalog, eight tools per page, with no group selected until one is chosen for that engine. Search matches title, description, id, and command across the whole engine and ignores Vietnamese diacritics; clearing it restores the group. Selecting a tool opens a dialog with its description, its `note` when present, and its script plus prefix. That dialog does not start a process. An explicit "Use this tool" opens the existing form.

### Store the new fields on the existing settings object

`settings.json` gains `language` (`en` or `vi`, default `en`) and, per engine, the chosen sheet path, output folder, and last tool group. The project folder stays `settings.workspaces[engineId]`. Sheet and output paths are strings, not file contents. Missing keys on an older file use those defaults; existing workspaces and form values are left as they are.

## Risks / Trade-offs

- [Otomate `filltitles-fill` or `quarong` expects a merged project workbook and game files, not an arbitrary spreadsheet] → A failing prepare or check step is blocking and create does not start. The UI names the failed step instead of showing a generic success.
- [Unity has no current "too wide" command, so the layout check is new read-only code next to `tmp.py`] → It must not write the bundle or the sheet. A doubtful measurement fails closed and is listed as overflow, with no bypass.
- [`quarong`'s report shape may change] → An unreadable report blocks creation rather than being treated as clean.
- [The run directory can accumulate after stop] → The recipe does not delete it on cancel, matching the spec. The UI says there is no completed patch.
- [Diacritic-insensitive search can match more than a literal compare] → It still searches only the active engine's catalog, and clearing search returns to the selected group.

## Migration Plan

Ship the UI and recipe in the app. On startup, fill missing `language` and per-engine patch fields without rewriting unrelated settings. Rollback is reverting the app build: old builds ignore the new keys, and the existing tool-run IPC is unchanged. No engine submodule bump is required for the Otomate steps, because they call tools that submodule already contains. The Unity layout check lands in `engines/unity`, which is part of this repo.

## Open Questions

None. The choices above are enough to write the task breakdown without changing the specs.
