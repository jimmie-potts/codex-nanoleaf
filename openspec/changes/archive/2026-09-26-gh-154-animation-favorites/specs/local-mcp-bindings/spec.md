## ADDED Requirements

### Requirement: Named favorite MCP controls

The host SHALL expose `nanoleaf_animation_save`, `nanoleaf_animation_rename`, and `nanoleaf_animation_forget` as control tools using the caller's current extension ticket and revision. Save SHALL accept supplied explicit animation fields or a preset and SHALL NOT infer currently playing content. The list tool SHALL report named favorites; the play tool SHALL accept a favorite name. Configuration tools SHALL return matched extension configuration receipts, preserve typed failures and original request identity after possible dispatch, and never retry automatically. Existing playback tools SHALL retain Free-mode guidance and transport receipt semantics. Maps to [issue #154](https://github.com/jimmie-potts/codex-nanoleaf/issues/154) MCP save/replay criteria and the approved atomic rename decision.

#### Scenario: Save and replay through MCP
- **WHEN** a control principal saves an explicit recipe and later plays its name using fresh listed ticket and revision values
- **THEN** MCP forwards one corresponding extension request for each operation and accepts only a receipt matching that request's ticket and outcome family

#### Scenario: Configuration without mode change
- **WHEN** MCP saves, renames or forgets a favorite while the Lines are in Work or Quiet
- **THEN** it performs no mode switch and reports configuration application separately from playback transmission
