## Why

[Issue #26](https://github.com/jimmie-potts/codex-nanoleaf/issues/26) retains the compact-layout number collision reported during the original map review. The integrated Prism renderer supplies the final crystal and ring dimensions, so numbering can now adopt the approved luminous style and conditional visibility without losing physical identity.

## What Changes

- Place readable luminous numerals against final screen geometry, clearing neighbouring tubes, connector bodies, rings and other labels at the supported widths and transforms.
- Reveal numbers for selection, highlighting, hover or keyboard focus. Keep multiple reasons independent, including touch selection.
- Add a browser-local show-all preference, off by default, while keeping placements stable when visibility changes.
- Preserve all physical IDs, cross-view associations, modifiers, passive selection, assembly interruption and explicit Locate behavior.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `wall-line-identification`: luminous numeral visibility, readable screen-space clearance and the passive show-all preference.
- `wall-prism-rendering`: complete the existing number integration while retaining local interaction and geometry replacement contracts.

## Impact

Wall display code, a bounded label-placement module and its local asset inclusion, browser and pure geometry checks, and bridge documentation. The branch follows Prism PR #58; final acceptance uses the integrated candidate and does not waive that dependency's checks. Existing assembly and mode contracts stay in force. No physical renumbering, allocation, device, tray, service or installation changes. Hub PR #82 owns the linked guide update.
