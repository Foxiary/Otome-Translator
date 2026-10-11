# Spec Delta

## Purpose

Lets the translator find a tool in the active engine and read what it does, including known cautions, before using it.

## ADDED Requirements

### Requirement: The browser lists only the active engine
The system MUST show only tools that belong to the active engine.

#### Scenario: The active engine is Otomate
- **WHEN** the active engine is Otomate and the translator opens the tool browser
- **THEN** every listed tool belongs to Otomate

#### Scenario: The active engine is Unity
- **WHEN** the active engine is Unity and the translator opens the tool browser
- **THEN** every listed tool belongs to Unity

### Requirement: No group is selected until the translator chooses one
Until the translator chooses a tool group for an engine, the system MUST NOT preselect a group for that engine.

#### Scenario: First visit for an engine
- **WHEN** the translator opens the tool browser for an engine and has not chosen a group for that engine
- **THEN** no group is selected and the system offers a group choice or search

### Requirement: A group lists only its tools
The system SHALL list only the tools in the selected group of the active engine.

#### Scenario: The translator chooses a group
- **WHEN** the translator chooses a tool group
- **THEN** the list shows only tools in that group

### Requirement: The chosen group is remembered
The system MUST remember the last tool group chosen for each engine.

#### Scenario: The translator returns to the browser
- **WHEN** the translator has chosen a tool group for an engine and later opens the browser for that engine without choosing a new group
- **THEN** that group is selected

### Requirement: Results show at most eight tools per page
The system MUST show at most eight matching tools on a page and MUST provide the next and previous pages when more tools match.

#### Scenario: More than eight tools match
- **WHEN** the current group or search has more than eight matching tools
- **THEN** the system shows eight tools and a way to view the rest

#### Scenario: Eight or fewer tools match
- **WHEN** eight or fewer tools match
- **THEN** the system shows all of them on one page

### Requirement: Search covers the whole active engine
The system MUST search every tool in the active engine, not only the selected group. Clearing the search MUST restore the chosen group.

#### Scenario: Search matches a tool in another group
- **WHEN** the translator searches for text that matches a tool outside the selected group
- **THEN** that tool appears in the results and its group is shown

#### Scenario: Search is cleared after a group was chosen
- **WHEN** the translator clears the search and a group was chosen for this engine
- **THEN** the list returns to that group

#### Scenario: Search is cleared and no group was chosen
- **WHEN** the translator clears the search and no group was chosen for this engine
- **THEN** no group is selected

### Requirement: The patch page can open a group
The system SHALL offer shortcuts from the create-patch page into tool groups of the active engine.

#### Scenario: The translator uses a shortcut
- **WHEN** the translator chooses a tool-group shortcut on the create-patch page and no patch run is in progress
- **THEN** the tool browser opens with that group selected

### Requirement: Details appear only after selection
The system MUST NOT show a tool's purpose, cautions, original name, or command until the translator selects that tool. Selecting a tool MUST NOT run it or change files.

#### Scenario: The translator selects a tool
- **WHEN** the translator selects a tool in the list
- **THEN** the system shows its purpose, any caution, its original name, and its command, and does not run the tool

#### Scenario: The translator only browses
- **WHEN** the translator changes groups or search text without selecting a tool
- **THEN** no tool runs and no files change

### Requirement: Known cautions are shown on selection
When the translator selects a tool that has a known caution, the system MUST show that caution with the tool details.

#### Scenario: Demonstration glossary translations
- **WHEN** the translator selects the tool that applies built-in demonstration glossary translations
- **THEN** the system warns that this tool is not the normal way to apply the translator's workbook

#### Scenario: Otomate build is project-specific
- **WHEN** the translator selects the Otomate build tool
- **THEN** the system warns that the build follows the Virche Evermore project layout and is not a universal build for every Otomate game

#### Scenario: Unity RomFS extraction
- **WHEN** the translator selects Unity RomFS extraction
- **THEN** the system warns that an update NSP is not supported and the base game is required

#### Scenario: FFU font generation
- **WHEN** the translator selects FFU font generation
- **THEN** the system warns that an unsuitable font or cell height can crash the game and that the result must be tested in the game

#### Scenario: Adding glyphs to a static font
- **WHEN** the translator selects adding glyphs to a static TextMeshPro font
- **THEN** the system warns that the atlas generator must be verified on that font before characters are added
