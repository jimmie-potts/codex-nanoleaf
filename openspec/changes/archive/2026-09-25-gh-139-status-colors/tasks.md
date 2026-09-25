## 1. Stored palette and settings write

- [x] 1.1 Add failing tests for the palette defaults, partial updates, reset, restart persistence and upgrade preservation of project colors, reservations, map settings, mode and scene; implement the `palette` table and readers; observe them pass.
- [x] 1.2 Add failing API tests for valid, invalid-hex, unknown-role, mixed valid and invalid, and missing-token palette requests and for the palette in `/api/state`; extend `/api/settings` and the state response; observe them pass.

## 2. Worker frames

- [x] 2.1 Add failing fake-clock frame tests for Work base, pulses, waves, the unread pulse and the comet tail, Quiet at 10%, Free, Project halves under both coverage settings, Base set to Off with scene restoration, swapped-hue priority and the Panels triangles; make `pixel_color`, `comet_color`, `zone_color` and the preview read the palette; observe them pass.
- [x] 2.2 Add a failing worker test that changes and resets the palette mid-pulse and mid-comet and checks epochs, comet source and start, slots and a redraw; add the palette to the display cache key and keep the no-scene fallback blue; observe it pass.

## 3. Wall map

- [x] 3.1 Replace the fixed status tokens with the effective palette, draw unused Lines in Base, derive readable status label colors, and update the legend and Project halves sample.
- [x] 3.2 Add the Colors group with swatches, custom colors, Reset colors and the similar-color warning; show the owner a screenshot of the design before the browser tests are finished.
- [x] 3.3 Add a browser check for the Colors group, its request boundary, persistence, warning, legend and wall colors and readable labels; run the full browser suite.

## 4. Documentation and delivery

- [x] 4.1 Move the color contract from the bridge guide to the new spec with links; synchronize and archive this change; run the Python, browser and workflow suites.
- [x] 4.2 Publish the PR with the comparison and evidence. Independent reviews, current-head CI and explicit human UI approval remain merge gates.
