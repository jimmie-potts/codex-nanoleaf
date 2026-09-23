## 1. Enrollment

- [ ] 1.1 Add `device-enroll` with verification before any write, the Free start, conflict refusal and repeat handling, dispatched from `bridge.py`. Evidence: focused red-then-green tests in `tests/test_enrollment.py`, using temporary Linux state and a fake NL22 transport. They cover enrollment beside Lines with unchanged Lines, tasks, reservations, mode, hooks and ports; a wrong model; an unusable layout; an unreachable device; the `wall` id, a shared address and a changed address; a repeat that replaces only the credential; and unchanged controller and MCP credentials.
- [ ] 1.2 Move the token reader into the runtime module, add `--pair`, and keep credentials out of output, errors and browser responses. Evidence: tests cover token-file, prompt and pairing intake, a refused pairing window, owner-only file modes, a Windows-mounted state refusal, the absence of the credential from captured output and from the wall map's state response, and the installer still reading its token file.
- [ ] 1.3 Show that an enrolled device stays dark until activated and that activation replays nothing. Evidence: a Panels worker run after enrollment sends no request to the fake transport; `status --device panels` reports Free with nothing pending; activation after earlier completions queues no Panels comet and sets the wave cutoff to the activation time; the saved layout loads while the device is unreachable.

## 2. Removal

- [ ] 2.1 Stop a non-Lines worker instance whose device is no longer registered. Evidence: red-then-green tests show a waiting Panels instance exiting after unregistration without sending, and the worker retry loop stopping instead of recording another error.
- [ ] 2.2 Add `device-remove` with the Free-and-applied requirement, `--force`, the worker-lock wait, cleanup, and the rerun that finishes pending cleanup. Evidence: tests cover removal after a Free handoff; refusal in Work and while Free is pending; forced removal; refusal for `wall` and unknown ids; unchanged Lines state; and cleanup completing on rerun after a busy lock.

## 3. Documentation and delivery evidence

- [ ] 3.1 Update the bridge guide and the development, Linux installation and controller API guides with enrollment, pairing, activation and removal. State that source checks are not installation or physical evidence. Evidence: inspect the rendered text and links.
- [ ] 3.2 Run the full Python suite, browser checks, MCP source checks and workflow checks. Synchronize and archive this change before final independent review, and record the results in the PR.
