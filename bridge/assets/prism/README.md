# Prism components

These SVG components come from the same material factories as the animated wall in `bridge/prism.js`. Run `node scripts/export-prism.cjs` from the repository root to reproduce them. The renderer changes each Line's two colors and animates tubes and connector rim sections independently; the exported files are useful for composition and inspection, while the live UI calls the factories directly.

The owner-provided Prism finish kit is the art source. Its archive SHA-256 is `ceef5c07993fa3aba77daae02521747fbb55d1c8595002231a378d06105f8fb0`. The detailed tube shell, front facets, light packet, diffuse spill, connector pane and permanent rim functions retain that source. The application adapts timing, roots, input handling and lifecycle for issue #53. No tray assets are included.

Canonical tube coordinates span x = −128…128 and y = −16…16. Runtime tube width is 78% of that height. A connector has radius 25 and flat-face distance `25 × cos(30°)`. Zone 0 belongs to endpoint `a`, zone 1 to endpoint `b`, even when deployment starts at `b`. Six quadrilateral rim pieces remain the connector's final border.

The only served component paths are `/assets/prism.js` and `/assets/prism-adapters.js`; these SVG exports are not an arbitrary browser file route. Ship both JavaScript files beside `wall.html` and `wall_server.py`. The existing source inclusion lists contain them. The separately owned Linux installation #54 must retain these files with the wall source. No runtime path points to the original personal art folder, and no remote assets are required.
