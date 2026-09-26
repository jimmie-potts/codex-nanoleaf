# 0017. Animation favorites are private, immutable named recipes

Status: Accepted for source implementation of [#154](https://github.com/jimmie-potts/codex-nanoleaf/issues/154).

## Context

A named favorite must survive source upgrades without changing its colors, timing or direction. The existing integration extension already owns configuration requests, a bounded queue and atomic receipts. Its snapshot shape is consumed by the Hub and must remain unchanged.

## Decision

- The owner chose create-only save and an explicit atomic rename. Saving an occupied name or renaming onto any occupied name rejects with `revision-conflict`, preserving both recipes. Changing a recipe requires an explicit delete and new save; those separate commands are not presented as an atomic replacement.
- Save takes supplied validated animation fields or a curated preset. The worker freezes the complete explicit recipe, including applicable defaults, when it applies the save. It does not inspect or infer currently playing output. Replaying a favorite uses that stored recipe rather than a future preset definition.
- Private installation SQLite owns at most 32 favorites. Names are case-sensitive, 1–80 Unicode characters, nonblank and without control/format characters. Names are preserved exactly, including surrounding spaces; there is no normalization or silent trimming.
- Save, rename and forget use the existing configuration queue and `applied` receipts in every mode. They do not mark the display dirty, clear a transport hold or write lights. Playback remains Free-only and uses the existing writer and current frame/byte bounds.
- The authenticated animation-options route and MCP expose favorites. Their data enters the revision digest privately but adds no snapshot capability or browser/Hub field. Separate MCP and Hub principals retain the existing request-history privacy boundary.

## Consequences and recovery

The table is added by normal idempotent database initialization; repeated initialization preserves recipes and existing state. Rolling source back keeps the database, and older source ignores the table. Do not reset state, run fresh setup, or restore an older database over current favorites. No installation or live-state migration is part of source delivery.

A collision or capacity rejection changes nothing and consumes no ticket. Configuration and its receipt commit in the same worker transaction. After a lost response, use the original ticket for receipt lookup or exact replay; never allocate a fresh ticket automatically. Layout changes can make an old recipe unplayable under the current encoder bounds, but do not delete it. Sharing favorites, capturing current output and editing recipes in the browser remain outside this decision.
