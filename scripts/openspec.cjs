// Run the repository's pinned CLI without changing the user's global settings.
const { spawnSync } = require('node:child_process');
const { existsSync } = require('node:fs');
const path = require('node:path');

const cli = path.join(__dirname, '..', 'node_modules', '@fission-ai', 'openspec', 'bin', 'openspec.js');
if (!existsSync(cli)) {
  process.stderr.write('OpenSpec is not installed. Run npm ci in the repository root.\n');
  process.exit(1);
}

const result = spawnSync(process.execPath, [cli, ...process.argv.slice(2)], {
  stdio: 'inherit',
  env: {
    ...process.env,
    OPENSPEC_TELEMETRY: '0',
    DO_NOT_TRACK: '1',
    OPENSPEC_NO_COMPLETIONS: '1',
    OPENSPEC_NO_ANIMATION: '1',
  },
});
if (result.error) process.stderr.write(`${result.error.message}\n`);
if (result.signal) process.stderr.write(`OpenSpec stopped by ${result.signal}.\n`);
process.exitCode = result.status ?? 1;
