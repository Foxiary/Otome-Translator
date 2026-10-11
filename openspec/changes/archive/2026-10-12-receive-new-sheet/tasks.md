# Tasks

## 1. Settings and interface language

- [x] 1.1 Add a settings normalizer that sets missing `language` to `en` and, per engine, an empty sheet path, output folder, and last tool group, leaving `workspaces` and saved form values unchanged. Verify with a node assertion on a fixture that omits the new keys and a fixture that already has an Otomate workspace path.
- [x] 1.2 Add `src/i18n.js` with English and Vietnamese copy for Create patch, the tool browser, engine switching, and stop. Verify a node assertion that every key has a non-empty `en` and `vi` string and that the module exports no file path.

## 2. Tool browser

- [x] 2.1 Add pure helpers for the active engine's catalog: no group until one is chosen, a group lists only its tools, at most eight tools per page, and search matches title, description, id, and command across the whole engine with Vietnamese diacritics ignored. Verify node assertions for a nine-tool page split, a diacritic-free query hitting a Vietnamese title, a match outside the selected group, and clear-search restoring that group.
- [x] 2.2 Render All tools from those helpers, remember the chosen group per engine, and open a group from a Create patch shortcut. Verify `node --check` on the new renderer code and a node assertion that an Otomate tool id is absent when the active engine is Unity.
- [x] 2.3 On selection, show the tool's purpose, its catalog `note` when present, and its script plus prefix, without starting a process. An explicit "Use this tool" opens the existing form. Verify a node assertion that `translate-glossary`, `build`, Unity RomFS extraction, `ffugen`, and `unity-tmpfont-add` expose a non-empty note, and that the select action's return value does not include a run request.

## 3. Patch recipe

- [x] 3.1 Define the Otomate recipe as `filltitles-fill`, then `quarong`, then `applyvi`, and the Unity recipe as the empty-cell scan, then the read-only layout check, then `jsonsheet.py apply`. Leave `build`, `release`, and `translate-glossary` out of both. Verify a node assertion of that order and of those three ids being absent.
- [x] 3.2 Copy the chosen `.xlsx` into a run directory under the engine output folder before any tool, and pass only that copy into later steps. Verify a node assertion that planned arguments never use the original path as an output, and that a failed copy does not produce a tool command.
- [x] 3.3 Add a read-only Python scanner that reports empty column-C cells as sheet and row. Verify it on a temporary workbook: the workbook hash is unchanged and the empty row is reported.
- [x] 3.4 Add a read-only Unity layout check beside `tmp.py` that flags a sheet row whose translation does not fit the project's text box. Verify on a fixture that the overflowing row is reported and the bundle and workbook hashes are unchanged.
- [x] 3.5 Stop the recipe before the create step when a finding exists, a check exits non-zero, or the `quarong` report cannot be read. The result has no skip action. Verify with a fake step runner that records the create step was not called in each of those three cases.
- [x] 3.6 When the output folder already contains patch files, ask before the create step. Declining leaves those files in place and does not mark the run complete. Verify a node assertion for confirm (create runs) and decline (create does not run and the completion flag stays false).
- [x] 3.7 Cancel aborts the current process, does not start the next step, and does not delete the run directory. Verify a node assertion that cancel after prepare leaves the run directory and skips create.
- [x] 3.8 Refuse to create patch files when the active engine has no project folder, no output folder, or is missing game files or fonts. Verify the runner returns a setup error and does not call the create tool id.

## 4. Create patch page

- [x] 4.1 Show the stages choose the sheet, create the patch, and try it in the game, with prepare, check, and create tasks. Reject a file whose name does not end in `.xlsx`, and keep patch creation unavailable until an `.xlsx` sheet is chosen. Verify a node assertion that `.csv` is rejected and `.xlsx` is accepted, then `node --check` the page module.
- [x] 4.2 Connect the page to the recipe runner. Blocking findings list the sheet and row and ask for a corrected `.xlsx`, with no skip control. Success offers opening the output folder and choosing another file, and does not install, publish, or compare the patch. Verify a node assertion that the success actions are only open-folder and choose-another-file.
- [x] 4.3 While a run is in progress, refuse engine changes and opening the tool browser or tool form, and still allow a language change to re-render labels only. Verify a node assertion that engine switching is refused while running and that a language change carries no workbook path.
- [x] 4.4 Keep the chosen sheet, output folder, and last tool group separate per engine. Verify a node assertion that setting Otomate's sheet path leaves Unity's sheet path unchanged.

## 5. Integration

- [x] 5.1 Add any new `src` files to the `check` script and verify `npm run check` exits 0. Confirm the recipe module still excludes `build`, `release`, and `translate-glossary`.

## Workflow follow-up

- Implement with `/opsx-apply` after this task list is accepted.
- Archive with `/opsx-archive` once implementation and any tracked work are complete.
