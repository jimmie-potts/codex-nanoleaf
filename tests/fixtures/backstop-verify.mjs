// #194: `npm run verify` with the wall plug-in's seed, serve and drive running beneath the test
// backstop, tests/fixtures/backstop_demo.py. The delivery evidence procedure captures
// control-paired-installed-port through this entry, so that even a boundary regression could not
// reach an installed service; each capture's log notes which demo entry served it.
//
//   node tests/fixtures/backstop-verify.mjs <operation> …
import {runCli} from '@jimmie-potts/app-verify';
import {createPlugin} from '../../scripts/verify/plugin.mjs';

process.exitCode = await runCli(createPlugin({demo: new URL('backstop_demo.py', import.meta.url).pathname}), process.argv.slice(2));
