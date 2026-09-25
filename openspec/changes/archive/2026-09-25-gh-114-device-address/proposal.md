## Why

[Issue #114](https://github.com/jimmie-potts/codex-nanoleaf/issues/114) asks for a way to change a registered Nanoleaf device's address, for example after the NL22 Light Panels get a new DHCP lease. `device-enroll` ([#45](https://github.com/jimmie-potts/codex-nanoleaf/issues/45)) deliberately refuses an existing id at a new address. The only workaround today is `device-remove` followed by `device-enroll`, and removal clears the device's reservations, mode, layout entry and saved scene.

## What Changes

- Add `device-address --device <id> --ip <new>`. It changes only the registered address of one Panels device. The id, credential reference, reservations, mode, layout entry and saved scene stay as they are.
- Before any write, the command checks that the new address is a private IPv4 address that no other registered device uses. It then asks the device at that address, with the stored credential, to report model NL22 and a triangle layout equal to the saved one: the same triangles, positions and neighbors. The command changes nothing when a check fails or the device is unreachable. It sends no light write. Credentials never appear in its output or errors.
- Refuse the Lines device (`wall`). Lines have no model check to reuse for the "same kind" verification, so Lines stay out of scope, as the issue allows.
- Make each worker pass read its device's address and credential from the registry. A running worker then uses the new address on its next pass, and a failing one picks it up on retry, with no service restart.
- Replace the remove-and-re-enroll workaround in the Linux installation guide and bridge guide with the new command.

Unchanged baseline: enrollment still never redirects an identity, and removal, the Free start, the worker's locking, the protected controller and MCP contracts, and the wall map are unchanged.

A design document is omitted: the change reuses the enrollment verification and the existing registry lock, and adds no state, migration or concurrency model. The `spec-driven` schema's design criteria do not apply.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `device-enrollment`: adds verified address change for a registered Panels device.
- `device-worker`: each pass follows the registered address and credential of its device.

## Impact

- `bridge/enrollment.py`: the `device-address` command and its verification.
- `bridge/bridge.py`: the worker refreshes its device's transport from the registry on each pass.
- Tests in `tests/test_enrollment.py` and `tests/test_device_worker.py` use temporary Linux state and fake Lines and NL22 transports. No personal device is contacted.
- Documentation: `docs/linux-install.md` and `bridge/README.md`.

Source delivery does not change the installed runtime. Changing the installed Panels address is a separate operator action.
