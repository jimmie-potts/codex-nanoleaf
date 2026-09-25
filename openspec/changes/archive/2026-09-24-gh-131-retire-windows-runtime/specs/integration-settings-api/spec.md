## MODIFIED Requirements

### Requirement: Portable bounded delivery
The extension SHALL support current Lines on the native Linux installation. Documentation SHALL specify versioning and rollback that preserve current databases. Source fixtures SHALL remain separate from installed-client and physical acceptance. This requirement also maps to [issue #131](https://github.com/jimmie-potts/codex-nanoleaf/issues/131) AC6.

#### Scenario: Version rollback
- **WHEN** an operator returns to source without the extension
- **THEN** existing v1 operations remain compatible, and documented cancellation and listener shutdown prevent stale extension work from replaying on later upgrade
