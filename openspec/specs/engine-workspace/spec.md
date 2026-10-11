# engine-workspace Specification

## Purpose

Keeps each engine's sheet, project, output, and last tool group separate, and holds the active engine still while a patch run is in progress.

## Requirements

### Requirement: Each engine keeps its own workspace
The system MUST store the chosen sheet, project folder, output folder, and last tool group separately for each engine.

#### Scenario: The translator switches engines
- **WHEN** the translator switches from one engine to the other while no patch run is in progress
- **THEN** the system shows the sheet, project folder, output folder, and last tool group stored for the newly active engine

#### Scenario: The translator returns to an engine
- **WHEN** the translator switches back to an engine they already used
- **THEN** the system restores that engine's sheet, project folder, output folder, and last tool group, and the other engine's values are unchanged

### Requirement: A run blocks engine changes and other tools
While a patch run is in progress, the system MUST keep the current engine and MUST NOT open the tool browser or another tool. The system MUST still allow an interface-language change.

#### Scenario: The translator tries to switch engines during a run
- **WHEN** a patch run is in progress and the translator tries to switch engines
- **THEN** the system stays on the current engine and tells the translator to stop or finish the run first

#### Scenario: The translator tries to open tools during a run
- **WHEN** a patch run is in progress and the translator tries to open the tool browser
- **THEN** the system does not open the tool browser

#### Scenario: The translator changes language during a run
- **WHEN** a patch run is in progress and the translator changes the interface language
- **THEN** the interface language changes and the run continues on the same engine
