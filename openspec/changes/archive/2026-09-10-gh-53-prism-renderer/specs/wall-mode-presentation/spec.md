## MODIFIED Requirements

### Requirement: Work shows an indicative pulse

In Work mode the wall map SHALL send one bright packet from each connector toward the center of every Line carrying a working, question, blocked or unread task. Packets SHALL meet in a brief center spark during a shared two-second UI cycle. Both ordered zones SHALL retain their app-resolved colors. Lines without a task SHALL stay steady. The animation SHALL be derived from task status alone and SHALL be described, on the page and in documentation, as an indicative status animation rather than a mirror of physical output. Covers issue #53 AC3–AC4 and retained issue #23 AC2 and AC5.

#### Scenario: Active Lines pulse in Work
- **WHEN** the mode is Work and a Line carries a working, question, blocked, or unread task
- **THEN** both zones flow inward on the two-second cycle and an idle Line does not

#### Scenario: Rebuilds keep the phase
- **WHEN** the page rebuilds the wall because a Line is selected or a poll changes state
- **THEN** each active Line resumes the page-wide phase within 50 ms instead of restarting
