## ADDED Requirements

### Requirement: Circular directions and faster requested animation
Spatial requested patterns SHALL support `clockwise` and `counterclockwise` around the centroid of the saved Line positions using positive Y upwards, with a full circular phase starting at positive X. A Line at the centroid SHALL use phase zero. The `faster` speed SHALL use a one-decisecond base keyframe step and shorten each pattern's cycle relative to `fast`. All existing direction and speed combinations SHALL preserve encoded payload bytes. Frame and request byte limits, Free-only playback, receipts and single-writer ownership SHALL remain unchanged. Maps to [issue #151](https://github.com/jimmie-potts/codex-nanoleaf/issues/151) encoder acceptance and retained protections.

#### Scenario: Rotating crests on both fixture layouts
- **WHEN** wave or gradient renders a clockwise or counterclockwise rotation on the 15-Line or two-Line fixture
- **THEN** the crest follows the corresponding centroid angle within keyframe quantization, both zones agree, and the existing frame and byte limits hold

#### Scenario: Faster cycle with legacy compatibility
- **WHEN** each pattern uses `faster`
- **THEN** its cycle is shorter than `fast` without zero-duration frames
- **AND** rendering any old direction and speed combination produces the original bytes
