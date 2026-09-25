## MODIFIED Requirements

### Requirement: Animation transport evidence
An animation receipt SHALL end as `sent` (prior effects `confirmed-transmission`), `failed` or `cancelled` (prior effects `none`), or `uncertain` (prior effects `possible`), always with `physicalOutcome` `unknown`. Identical duplicates SHALL join or replay the original receipt. Any explicit mode command, owner cancellation, credential revocation, controller disable and 30-second expiry SHALL retire a queued animation before it is sent. Admitting an animation SHALL clear a controller transport hold and authorize another attempt, like a fresh v1 control. The worker SHALL record the attempt before its single device write and SHALL NEVER send an attempted animation again. Maps to issue #92 scope 3.

#### Scenario: Mode command retires a queued animation
- **WHEN** a Work, Quiet or Free mode command commits while an animation is queued
- **THEN** the animation is cancelled with `stale-generation` and no device write

#### Scenario: Interrupted send
- **WHEN** the device write raises or the worker stops after recording the attempt
- **THEN** the receipt ends `uncertain` with possible prior effects and no later pass sends it again

#### Scenario: Animation after a held machine request
- **WHEN** an earlier machine request left the installation held and an animation is admitted in Free
- **THEN** the hold is cleared, the worker plays the animation, and the earlier uncertain request is not sent again
