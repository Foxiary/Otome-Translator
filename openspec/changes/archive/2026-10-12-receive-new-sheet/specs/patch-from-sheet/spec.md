# Spec Delta

## Purpose

Turns the translator's latest Excel sheet into a patch for the active engine, and stops when the sheet still needs fixes.

## ADDED Requirements

### Requirement: Patch creation waits for a sheet
The system MUST keep patch creation unavailable until the active engine has a chosen `.xlsx` sheet.

#### Scenario: No sheet is chosen
- **WHEN** the active engine has no chosen sheet
- **THEN** the translator cannot start a patch run

#### Scenario: An xlsx sheet is chosen
- **WHEN** the translator chooses a file whose name ends in `.xlsx`
- **THEN** the system stores that file as the sheet for the active engine and enables patch creation

### Requirement: Only an Excel workbook is accepted
The system MUST reject a chosen file whose name does not end in `.xlsx` and MUST NOT start a patch from it.

#### Scenario: The file is not an xlsx workbook
- **WHEN** the translator chooses a file whose name does not end in `.xlsx`
- **THEN** the system does not keep that file as the sheet and tells the translator to download an online sheet as Excel first

### Requirement: The original workbook stays unchanged
The system MUST NOT modify the chosen Excel workbook while preparing, checking, creating, or stopping a patch.

#### Scenario: A run finishes
- **WHEN** a patch run finishes
- **THEN** the chosen Excel workbook has the same contents as when the translator selected it

#### Scenario: A run stops or finds problems
- **WHEN** the translator stops a run, or checks find blocking problems
- **THEN** the chosen Excel workbook is unchanged

### Requirement: Project setup is required before patch files are created
The system MUST NOT create patch files until the active engine has a project folder and an output folder. The system MUST NOT create patch files while required game files or fonts are missing.

#### Scenario: Project folder or output folder is missing
- **WHEN** the translator starts a patch and the active engine has no project folder or no output folder
- **THEN** the system does not create patch files and asks for the missing setup

#### Scenario: Game files or fonts are missing
- **WHEN** a real build needs game files or fonts that are not present
- **THEN** the system does not create the patch and reports what is missing

### Requirement: An existing patch is not replaced without confirmation
The system MUST ask the translator before replacing patch files that already exist, and MUST NOT replace them if the translator declines.

#### Scenario: The output already contains a patch
- **WHEN** creating the patch would replace files that already exist
- **THEN** the system does not replace those files until the translator confirms

#### Scenario: The translator declines replacement
- **WHEN** the translator declines to replace an existing patch
- **THEN** the existing patch files remain in place

### Requirement: The translator sees one shared journey
The system SHALL show the stages choose the sheet, create the patch, and try it in the game. During creation the system SHALL show three tasks: prepare the translation, check for problems, and create the patch files.

#### Scenario: A run starts
- **WHEN** the translator starts a patch from a chosen `.xlsx` sheet
- **THEN** the system shows the create-patch stage and shows preparation as in progress

#### Scenario: A run finishes with no blocking problems
- **WHEN** preparation and checks finish with no blocking problems and the patch files are created
- **THEN** the system shows the try-it-in-the-game stage

### Requirement: Preparation follows the active engine
The system SHALL prepare the active engine's translation before checks. Otomate preparation includes the translation sheet and chapter titles. Unity preparation includes the translation and text-box layout.

#### Scenario: The active engine is Otomate
- **WHEN** the active engine is Otomate and a patch run starts
- **THEN** the system prepares the translation sheet and chapter titles before checks

#### Scenario: The active engine is Unity
- **WHEN** the active engine is Unity and a patch run starts
- **THEN** the system prepares the Unity translation and checks text against its boxes before creating patch files

### Requirement: Blocking problems prevent patch creation
The system MUST NOT create patch files when a check finds a blocking problem. An empty translation and text that does not fit its box are blocking problems. The system MUST NOT provide a control that creates the patch while a blocking problem remains.

#### Scenario: A translation is empty
- **WHEN** a check finds an empty translation
- **THEN** the system does not create a patch, identifies the sheet location, and asks the translator to choose the corrected Excel file

#### Scenario: Text does not fit its box
- **WHEN** a check finds text that is too long for its dialogue box or text box
- **THEN** the system does not create a patch, identifies the sheet location, and asks the translator to choose the corrected Excel file

#### Scenario: The translator chooses a corrected file
- **WHEN** the translator chooses a corrected `.xlsx` file after blocking problems
- **THEN** the system treats that file as the sheet for a new run

### Requirement: The translator can stop a run
The system MUST let the translator stop a run that is in progress. Stopping MUST NOT undo steps that already finished. The system MUST NOT present a completed patch unless the create step finished.

#### Scenario: The translator stops before create finishes
- **WHEN** the translator stops a run before the create step finishes
- **THEN** the system does no further work and reports that there is no completed patch

#### Scenario: Finished steps wrote temporary files
- **WHEN** a stopped run already wrote temporary files
- **THEN** the system leaves those files in place and does not report that they were removed

### Requirement: A finished patch folder can be opened
The system SHALL let the translator open the folder that contains the new patch after a successful run.

#### Scenario: The translator opens the patch folder
- **WHEN** the translator asks to open the patch folder after a successful run
- **THEN** the system opens the output folder that contains the new patch

### Requirement: Install and publish stay outside this flow
The system MUST NOT install the patch into the game, publish it, or compare it with a previous release as part of creating the patch.

#### Scenario: Patch files are created
- **WHEN** a patch run creates patch files
- **THEN** the translator can open the patch folder, and the system has not installed, published, or compared the patch
