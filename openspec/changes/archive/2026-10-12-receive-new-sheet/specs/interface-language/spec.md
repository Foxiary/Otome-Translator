# Spec Delta

## Purpose

Lets the translator use the app in English or Vietnamese without changing the words in the translation sheet.

## ADDED Requirements

### Requirement: The interface is English or Vietnamese
The system SHALL present interface copy in the translator's chosen language, English or Vietnamese.

#### Scenario: The translator chooses Vietnamese
- **WHEN** the translator sets the interface language to Vietnamese
- **THEN** interface labels are shown in Vietnamese

#### Scenario: The translator chooses English
- **WHEN** the translator sets the interface language to English
- **THEN** interface labels are shown in English

### Requirement: Language does not change the sheet
The system MUST NOT alter the chosen workbook or its translation text when the interface language changes.

#### Scenario: Language changes while a sheet is selected
- **WHEN** a sheet is selected and the translator changes the interface language
- **THEN** the workbook contents stay the same

### Requirement: Language stays available during a run
The system MUST allow an interface-language change while a patch run is in progress.

#### Scenario: Language changes during a run
- **WHEN** a patch run is in progress and the translator changes the interface language
- **THEN** the interface updates to that language and the run continues
