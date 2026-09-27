// The wall's verification adapter: `npm run verify -- <operation> …`.
// The shared core (@jimmie-potts/app-verify) runs the lifecycle; scripts/verify/plugin.mjs supplies the wall.
import {runCli} from '@jimmie-potts/app-verify';
import plugin from './verify/plugin.mjs';

process.exitCode = await runCli(plugin, process.argv.slice(2));
