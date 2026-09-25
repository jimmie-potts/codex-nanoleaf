## Why

Independent review of [issue #92](https://github.com/jimmie-potts/codex-nanoleaf/issues/92)'s delivery found two specification gaps. The device-worker spec still says a device receives no requests after a Free handoff, which contradicts the Free-only scene and animation writes. The animation receipt requirement did not say that admitting an animation clears a transport hold, as a fresh v1 control does. Without that, a held worker never played the animation.

## What Changes

- `device-worker`: the Free handoff sentence now allows the single write of an explicit native control, scene or animation command, and still forbids polling and task writes.
- `integration-settings-api`: admitting an animation clears a controller transport hold and authorizes another attempt, like a fresh v1 control. An animation whose launch fails or that expires unsent restores the hold, like unsent v1 work. A new scenario covers the clear.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `device-worker`: Per-device modes and scene restoration.
- `integration-settings-api`: Animation transport evidence.

## Impact

Specification wording, plus the hold-clearing behavior and its test in `bridge/integration_api.py` and `tests/test_controller_animations.py`, delivered in the same PR as #92.

No design document: this is specification wording plus a one-line hold clear that follows the existing v1 control rule.
