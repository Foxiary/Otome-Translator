# Proposal

## Why

After editing a translation sheet, a translator still has to know which engine command to run and in what order. The Create patch wireframe gives them one path: hand the app the latest Excel file and get a patch back, with preparation and checks in between. That path exists only as a preview today.

## What Changes

- Add a Create patch flow for the active engine: choose an `.xlsx` sheet, prepare the translation, check for problems, then create the patch files.
- Accept only `.xlsx`. Reject any other file and tell the translator to download an online sheet as Excel first.
- Leave the original workbook unchanged. Ask before replacing an existing patch.
- Remember, separately for each engine, the chosen sheet, project folder, output folder, and last tool group. Switching engines does not mix them.
- Show three stages: choose the sheet, create the patch, try it in the game. Project setup (game files, font, and output location) is required the first time and is kept per engine.
- While a run is in progress, show prepare, check, and create, and allow stop. Block engine changes and opening other tools until the run stops or finishes. Changing the interface language stays available.
- Stopping does not undo steps that already finished. Temporary files may remain. No completed patch exists until the run finishes.
- If checks find blocking problems, do not create a patch. Show the rows that need attention and ask for the corrected Excel file. The wireframe does not define when a warning may be bypassed; this change must decide that rule.
- When the patch is ready, open its folder. Installing the patch, publishing it, and comparing it with a previous release stay outside this flow.
- Add an All tools browser for the active engine. It starts with no group selected, shows at most eight tools per page, searches the whole engine, and returns to the chosen group when search is cleared. Selecting a tool shows its purpose, cautions, original name, and command. Browsing does not run a tool or change files.
- Offer English and Vietnamese interface copy. Language changes the interface only, not the contents of the sheet.
- Show the cautions already known for specific tools: `translate-glossary` is not the normal way to apply a workbook; `build` is specific to the Virche Evermore project layout; Unity RomFS extraction does not support update NSPs; an unsuitable FFU font can crash the game; adding glyphs to a static TextMeshPro font requires verifying the atlas generator first.

## Capabilities

### New Capabilities

- `patch-from-sheet`: Guided run that turns the active engine's chosen `.xlsx` sheet into a patch, including preparation, blocking checks, stop, and opening the result without modifying the original workbook.
- `engine-workspace`: Per-engine sheet, project setup, output location, and last tool group, including the rule that a run in progress blocks switching engines or opening other tools.
- `interface-language`: English and Vietnamese interface copy that does not alter translation content, including while a run is in progress.
- `tool-browser`: Browse and search the active engine's catalog, page the results, and disclose purpose, cautions, and the original command only after a tool is selected, without executing it.

### Modified Capabilities

None. The project has no existing specs.

## Impact

- Desktop UI in `src/index.html`, `src/renderer.js`, and `src/styles.css`. The current UI is one form per tool.
- Tool lists in `src/catalog-otomate.js` and `src/catalog-unity.js`, and engine metadata in `src/engines.js`.
- The stages the translator sees are shared. The commands behind prepare, check, and create differ by engine and are not one shared sequence. Otomate tools live in the VE-ES submodule; Unity tools live in `engines/unity/`.
- Sheets, patches, and game data stay on the machine. This flow does not add network calls.
