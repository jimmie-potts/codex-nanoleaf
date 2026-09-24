## Why

The wall map's default screen spends its first rows on secondary controls and repeats the same counts in the header readout, the wall heading and the task card. [Issue #78](https://github.com/jimmie-potts/codex-nanoleaf/issues/78) asks for one information hierarchy in which the wall, the current mode, live status, alerts and the selected item lead, and the rest stays available without crowding.

## What Changes

- Group Show all numbers, Rotate, Flip H, Flip V, Replay assembly and the two assembly playback preferences under one labelled **Options** menu above the wall, with labelled Numbers, Orientation and Assembly groups. Keyboard, Escape and outside-press closing, pressed states and saved preferences retain their current behavior.
- Turn the toolbar readout into a live status strip: the mode note that sat beside the wall, a pending-edit flag, and blocked and question alert counts. The Line total lives only in the wall heading and the task total only in the Tasks heading.
- Remove the repeated selection hints from the wall heading and the Projects heading; the selection card keeps the single instruction, including the multi-select modifier. The task card puts its full-list control beside its heading and its counts on two short lines.
- Give the wall more width on desktop by narrowing the inspector column, keeping the #77 two-column grid.

## Capabilities

### New Capabilities

- `wall-map-hierarchy`: the default screen's hierarchy, the labelled Options menu for secondary controls, and single primary locations for counts and hints.

### Modified Capabilities

- `wall-mode-presentation`: the "Mode readout" requirement changes from a count mirror to a live status readout; Line and task totals move to their headings.

## Impact

`bridge/wall.html` markup, styles and the readout, options and task-summary logic; browser checks that use the moved controls; a new hierarchy browser check; the bridge guide. No API, Python, state, database or device change. Presentation, menu use and preference toggles remain passive; orientation changes keep sending only the existing settings request. Draft PR #116 edits one unrelated detail-card line in the same file.
