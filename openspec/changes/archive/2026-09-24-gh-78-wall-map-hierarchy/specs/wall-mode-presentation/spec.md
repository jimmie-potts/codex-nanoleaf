## MODIFIED Requirements

### Requirement: Mode readout

The toolbar SHALL show a live status readout, refreshed with every poll, that names the current mode with its short explanation, states whether an edit or mode change is pending, and names the counts of blocked and question tasks when either is above zero, otherwise that there are no alerts. The Line total SHALL appear once, at the wall heading, and the task total once, at the Tasks heading, rather than in the readout. Covers issue #23 AC7 and issue #78 AC3.

#### Scenario: Readout follows state
- **WHEN** a poll reports Work, 15 Lines, 5 tasks of which 1 is blocked and 1 is a question, and a pending edit
- **THEN** the readout names Work with its explanation, the pending edit, 1 blocked and 1 question
- **AND** the wall heading names 15 Lines and the Tasks heading names 5

#### Scenario: Quiet without alerts
- **WHEN** a poll reports Quiet with no blocked or question tasks and no pending edit
- **THEN** the readout names Quiet with its explanation and says there are no alerts, without repeating the Line or task totals
