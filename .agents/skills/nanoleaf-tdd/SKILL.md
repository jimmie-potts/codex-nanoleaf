---
name: nanoleaf-tdd
description: Develop meaningful Nanoleaf behavior through focused red, green, and refactor cycles. Use for authorized bug fixes and new executable behavior; use inspection for documentation or cosmetic changes that need no behavioral regression test.
---

# Nanoleaf TDD

Read the relevant behavior owner and [the SDLC guide](../../../docs/sdlc.md).
This skill implements only behavior already authorized by the task. It does not
grant installation, device access, GitHub publication, or merge authority.

1. Identify the acceptance scenario and smallest observable boundary. For a bug,
   distinguish the existing contract from current broken behavior. For a feature,
   read its issue and applicable OPSX scenario first.
2. Choose the closest useful test level. Reuse deterministic clocks, isolated
   SQLite state, and fake controller behavior where appropriate. Test the contract
   rather than private helper structure or incidental call order.
3. Write one focused test and run it before changing production behavior. Confirm
   it fails for the intended missing or broken behavior. A setup/import failure
   is not the required red signal. If the test already passes, investigate before
   claiming a reproduction.
4. Implement the smallest useful change that satisfies the scenario. Run the
   same test and confirm it passes. Refactor code and tests while keeping it green.
   Repeat this cycle for the next scenario; do not batch every test ahead of the
   entire implementation.
5. Run relevant adjacent checks and the repository's required validation. Keep
   the actual red command, failure reason, green command, and outcomes for PR
   evidence. A test added afterward is regression coverage, not proof of a red
   result, unless an isolated earlier revision actually demonstrates it.

If a deterministic automated reproduction is impractical, explain why before
editing production code and choose a focused executable check, browser scenario,
or other observable substitute within the authorized scope. Do not build a broad
harness, depend on real credentials/lights, or add brittle timing tests just to
claim TDD. Lack of physical access does not authorize contacting the device.

Do not weaken assertions to accept incorrect behavior. A changed contract needs
explicit scope support and corresponding scenario updates. Keep unrelated
cleanup and new requirements out of the fix. A required unresolved decision
returns to planning; it does not become an invented test expectation.

Return the actual before/after evidence, remaining limitations, and nearby checks
to the coordinating task. Apply `unslop` to the explanation without changing
commands, failure text, identifiers, or results.
