## Context

See proposal.md. `drawTasks` currently rebuilds two lists from the same API tasks. `taskFocus` tracks waiting tasks but is cleared when they gain a Line; physical Line selection then loses task identity when placement changes. The detail editor defers refresh while its select is focused. These interaction decisions justify a design document.

## Goals / Non-Goals

Keep the existing full API projection and project-column counts. Do not change allocation, retention, names, attribution, or physical commands. Use the current single-file browser structure and existing synthetic harness without a new framework.

## Decisions

- One task list owns all rows; a compact waiting count replaces the second list. Existing Line placement and passive-selection contracts remain authoritative.
- Show up to the selected device’s Line count initially (zero Lines means zero compact tasks, with full-list access still available). A full-list button reveals status/waiting and text filters; text matches supplied title, ID, or known project name. Counts stay global and the shown summary names filtered matches.
- Sort selected tasks first, then blocked, question, working, unread, with ID ties. Include a keyboard-focused retained row within the compact Line-count limit even when its rank drops; keep it temporarily in filtered results with an explicit count note. A reveal-selected control resolves selection outside filters or a multiple-selection limit.
- Reuse rows by task ID and update changed contents with semantic focus restoration. Move siblings around the focused row without detaching it. Preserve inspector/page scroll during polling; natural clamping after a list shrinks is unavoidable.
- Selecting a title keeps task identity as placement changes. Clicking a physical Line or its badge retains physical selection semantics. An owner-retired task clears its task selection and any focused obsolete override; focus returns to the Tasks heading.

## Risks / Trade-offs

- Filtering can hide a selected task → explicit reveal-selected control and unchanged detail card while the task exists.
- Polled removal can leave a stale focused select → validate its task identity before deferring detail updates; never keep an editor for a retired task.
- Desktop task visibility → use two columns with single-line, ellipsized titles and full titles available through button names, tooltips and task details; keep status and placement in each tile. Put compact tasks before selection/details. Full-list mode restores selection/details above the list. Verify all 15 tiles fit without task scrolling at 1440×900 and 1280×800, including waiting and selected tasks. Narrow screens retain readable page flow rather than shrinking text to fit a whole wall. Larger Line counts remain uncapped by an arbitrary constant and may require scrolling when viewport space is insufficient.
- Owner expiration is independently delivered → fixtures consume missing/recreated rows; no installed lifecycle claim.

## Migration Plan

No data migration or deployment. A future authorized installation can replace the HTML; reverting the source restores the old presentation without changing saved state.
