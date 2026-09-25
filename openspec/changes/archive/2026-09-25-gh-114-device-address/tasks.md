## 1. Address change

- [x] 1.1 Add `device-address` with its checks before any write, dispatched from `bridge.py`. Evidence: focused red-then-green tests in `tests/test_enrollment.py` with temporary Linux state and fake Lines and NL22 transports. They cover a successful change that keeps the mode, reservation, layout and scene; the Lines address, another device's address and a public address; a different model and mismatched triangles; an unreachable address; `wall` and unknown ids; and a credential absent from output and errors.
- [x] 1.2 Make each worker pass use the registered address and credential. Evidence: a red-then-green test in `tests/test_device_worker.py` in which a running Panels instance sends to the new address after the change, and none of its later writes go to the old one.

## 2. Documentation and delivery evidence

- [x] 2.1 Replace the remove-and-re-enroll workaround in `docs/linux-install.md` and describe the command in `bridge/README.md`. Evidence: inspect the text and links.
- [x] 2.2 Run the full Python suite and workflow checks locally; browser and MCP checks run in CI because the map, its API and MCP are unchanged. Synchronize and archive this change before final independent review, and record the results in the PR.
