## Context

See proposal.md. The page is one HTML file whose toolbar already uses a native `details` menu for playback preferences, and whose browser suites click Rotate, Flip, Replay, Show all numbers and the playback checkboxes directly. The presentation suite requires the readout to say "released" in Free and "pending" for a pending edit, to fit a 60 px toolbar between 1050 and 1499 px, and it forbids writes from passive use. The compact task grid from #77 must still fit fifteen tiles at 1440×900 and 1280×800.

## Goals / Non-Goals

Keep every existing control, its identity, accessible name, saved preference and request behavior. Keep mode, connection, pending edits and alerts visible without opening a menu. Do not add a device selector (#44), a new dashboard, or any new request.

## Decisions

- One native `details` element with a button-styled `summary` labelled Options holds three `role="group"` sections. Native disclosure gives keyboard toggling and exposed expanded state; Escape closes it and returns focus to the summary; a pointer press outside closes it. The menu does not close on focus loss, so a keyboard user can move between the menu and the wall while it is open.
- Interaction inside the Options menu does not end a running assembly. Rotate and Flip still end it through the existing action path, and every other map interaction keeps its current behavior.
- The readout is built from state only: mode note with its explanatory tooltip, then "pending edit" or "mode change pending", then blocked and question counts when present, otherwise "no alerts". Its text is compared before replacing children so unchanged polls do not churn.
- Line and task totals each have one home: the wall heading and the Tasks heading. The task summary reads "N shown" (plus "M match filter" and the focused-exception note) because the heading already states the total.
- The inspector column narrows from 480 to 440 px; the two task columns keep single-line titles, so the #77 fit checks still hold, and the wall gains width.
- Existing suites open the menu through a shared test helper that clicks the summary, the way a user would, rather than setting `open` directly.

## Risks / Trade-offs

- The open menu overlays the top-right of the wall. Tests close it before raw pointer clicks on Line numbers, and users can press Escape.
- Counts no longer sit in one strip. The status breakdown remains in the task card; the readout keeps the alerts that need attention.
- Draft PR #116 changes one detail-card line in the same file; whichever merges second refreshes its comparison.
