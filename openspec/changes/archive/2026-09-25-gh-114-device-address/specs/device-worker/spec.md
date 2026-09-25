## ADDED Requirements

### Requirement: Address follows the registry
Each worker pass SHALL send to the address and credential currently registered for its device. A registered address change SHALL take effect on the running instance's next pass, or on its next retry after a failed pass, without a service restart. A pass SHALL keep its previous transport when the configuration cannot be read. Covers [#114](https://github.com/jimmie-potts/codex-nanoleaf/issues/114) AC3.

#### Scenario: Running worker follows a changed address
- **WHEN** a Panels worker instance is running in Work and the operator changes its registered address
- **THEN** its later light writes go to the new address and none go to the old one, without restarting the instance
