## 1. Paired seed and boundary

- [x] 1.1 Seed `hub-paired` from the `hub-feed` origin and the two credential files: the controller identity and the Hub's credential by its digest, shared input following the paired feed, no local tasks or projects, and every refusal before a write (TDD). Evidence: against `796c6ea`, `PairedSeedTest` errors with `module 'demo' has no attribute 'FEED_TOKEN'` and `'PairingError'`; after the change it passes, including the token scan of every state file.
- [x] 1.2 Allow only TCP connections to `127.0.0.1` on the paired port in a paired `serve` and `drive`, record each as `allowed`, and never allow an installed port (TDD). Evidence: against `796c6ea`, `PairedBoundaryTest` fails with `install_boundary() takes 1 positional argument but 2 were given`; after the change the paired listener alone accepts a connection and the test backstop records nothing.

## 2. Serve, writer and verification state

- [x] 2.1 Serve the real controller listener in a thread with `--controller-port`, announce it as the `controller` endpoint, and keep it on the recorded port in every later scenario. Evidence: `PairedServeTest` and the Node relaunch test answer on the same port; a standalone relaunch refuses the Hub's token.
- [x] 2.2 Run the paired writer: the real Poller and the integration settings queue about once per second, woken by the map and the controller without running in their threads. Evidence: an admitted `settings.set` is applied within about a second and the page shows it; a Hub that refuses and then accepts leaves the run serving and then current.
- [x] 2.3 Serve `GET /verify/state` with feed freshness and integration counts, without a token or token path. Evidence: the Python and Node tests read its exact shape and scan it for the credentials.

## 3. Plug-in, checks and steps

- [x] 3.1 Declare the `hub-feed` input and `hub-paired`'s required input, parse the ready line's endpoint, probe the controller listener and name the new failure causes. Evidence: the plug-in surface tests in `tests/verify_checks.mjs`.
- [x] 3.2 Accept only allowed paired connections in the paired `device-boundary` check, and add `paired-feed`: skipped until the first snapshot, then current at the Hub's revision. Evidence: the synthetic log cases, and a stand-in Hub that refuses, accepts, changes owner and goes away.
- [x] 3.3 Add `hub-lifecycle-painted` with an oracle written from the shared-input guide, and the two paired controls. Evidence: through `runCaptureStep`, the step passes with a screenshot and video, each control fails only at "only the paired Hub feed was contacted during the step", and neither the backstop log nor any capture log holds a credential.
- [x] 3.4 Supervised lifecycle: pair a real run with a stand-in Hub, capture, reseed standalone, and reseed without credential files. Evidence: `npm run test:verify:lifecycle` on a host with a user manager.

## 4. Dependencies, documentation and delivery

- [ ] 4.1 Vendor the released app-verify 1.1.0 archive, and install the controller dependencies in the browser CI job. Evidence: `npm ci` from the lockfile and the checksum file; CI's browser job.
- [x] 4.2 Document the pairing convention, order, checks, route and deferrals in the development guide, with cross-links from the shared-input and controller guides. Evidence: the guide's Hub-paired runs section and feature-map rows.
- [ ] 4.3 Run the Python suite on 3.12 and 3.14, the browser, verification, lifecycle and workflow checks, make the delivery evidence run at the final head, and record the results in the PR.
