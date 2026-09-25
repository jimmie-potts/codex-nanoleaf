## 1. Context card and layout controls

- [x] 1.1 Add a context-card browser check that expects a Mode-only header, a Layout group in Options, one context card without repeated title or project, Project-only reservation and override controls, Escape and empty-canvas clearing, and the Free-only Locate hint. Observe it fail on the current page.
- [x] 1.2 Move Layout and Coverage into Options, merge the cards, show a Reserved for select that applies on change and Swap halves only in Project layout, remove the map's task override, replace Clear selection with Escape and empty-canvas clearing, and show the Locate hint only in Free. Observe the new check and the updated existing suites pass.

## 2. Documentation and delivery

- [x] 2.1 Update the bridge guide and add ADR 0013; synchronize and archive this change; run the full browser, Python and workflow suites.
- [x] 2.2 Publish the PR with the comparison and evidence. Independent reviews, current-head CI and explicit human UI approval remain merge gates.
