## ADDED Requirements

### Requirement: Named animation presets
The controller SHALL advertise the ten curated moods from issue #153 as `presets` in the animation options route, with each `id`, pattern, colors, speed and applicable direction. An `animation.play` command SHALL accept either existing explicit parameters or only `preset` with an advertised name. The server SHALL resolve a preset to the same encoded frames as the equivalent explicit request, retain the original request for replay, and preserve Free-only admission, frame and byte limits, receipts and the integration snapshot shape.

#### Scenario: Inspect and play a mood
- **WHEN** a caller lists options then submits a preset-only request while in Free
- **THEN** the existing worker sends the same effect as the listed explicit fields, within the existing bounds
- **AND** replay uses the unchanged original request and receipt

#### Scenario: Reject ambiguous or unavailable preset requests
- **WHEN** the name is unknown, explicit fields accompany the name, mode is Work or Quiet, or the layout cannot encode the effect
- **THEN** the existing validation or typed admission failure rejects the request before a light write
