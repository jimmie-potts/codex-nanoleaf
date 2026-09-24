## Purpose

Keep the Projects column relevant to retained map tasks while preserving saved preferences and uninterrupted editing.

## ADDED Requirements

### Requirement: Current projects follow retained task associations
The map SHALL derive current-project eligibility from the full task list for the selected device, before any compact inspector limit. Saved preferences and reservations alone SHALL NOT qualify a project. The UI SHALL use its selected source's task lifecycle without another expiration clock or guessed attribution. This covers issue #76 criteria 1, 2, and 4.

#### Scenario: Saved projects without associations
- **WHEN** twenty saved projects exist and no retained task has a known project association
- **THEN** no inactive project rows appear by default, the column explains that no current project is known, and a Show saved projects control offers access to all twenty

#### Scenario: Retired and recreated tasks
- **WHEN** the owner removes a project's last retained task, including an unread task
- **THEN** that project leaves the current list unless its editor is in use, and a newly retained task with a known association makes it current again

### Requirement: Activity determines stable project order
The map SHALL order current projects by descending combined working, blocked, and question task count, then descending retained unread count, then ascending name with a stable identity tie-breaker. Counts SHALL include waiting tasks and use the full selected-device map task list. This covers criteria 2 and 4.

#### Scenario: Busy projects and stable ties
- **WHEN** several projects have active and unread tasks, including tasks beyond a compact inspector limit
- **THEN** their rows follow the defined count order and unchanged polls do not change tied rows' order

#### Scenario: Layout and device context
- **WHEN** the map shows Classic or Project layout for a device
- **THEN** counts and in-use badges agree with that device's task list, Project reservation badges agree with its saved reservations, and Shared pool remains distinct

### Requirement: Saved settings and interactions survive presentation changes
The map SHALL retain all saved projects, colors, roots, and reservations through hide/show, restart, and source changes. Project color edits SHALL continue to save through the existing protected endpoint. Polling and task transitions SHALL preserve an open color control, its unsaved value, keyboard focus, Line selection, and pending edits; a focused project editor SHALL remain available until interaction ends. This retains the bridge guide's color editing contract and covers criteria 3 and 5.

#### Scenario: Editing during retirement and ranking changes
- **WHEN** a color control is open while its project loses its last task or changes rank
- **THEN** the same control stays attached with its unsaved color and focus, and the inactive row can disappear after the interaction ends

#### Scenario: Saved disclosure and read-only presentation
- **WHEN** a user expands or collapses saved projects on a narrow or wide viewport
- **THEN** saved preferences remain accessible, the control exposes its expanded state to keyboard and assistive technology users, and presentation itself sends no write, device command, or metadata update and exposes no credential

#### Scenario: Source switch and restart
- **WHEN** the input changes between legacy and shared tasks or the map restarts
- **THEN** current rows reflect the supplied associations while saved global project preferences remain intact, even when the new source has no attribution
