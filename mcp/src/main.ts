import { loadConfig } from './config.js';
import { startHost } from './server.js';
async function main() {
    const args = process.argv.slice(2);
    if (args.length !== 2 || args[0] !== '--config')
        throw new Error('Usage: npm start -- --config <private absolute JSON path>');
    await import(new URL('../scripts/verify.mjs', import.meta.url).href);
    const config = await loadConfig(args[1]);
    const host = await startHost(config);
    process.stdout.write(`Nanoleaf MCP listening at ${host.url}\n`);
    let stopping = false;
    const stop = () => { if (stopping)
        return; stopping = true; void host.close().then(() => { process.exitCode = 0; }); };
    process.once('SIGINT', stop);
    process.once('SIGTERM', stop);
}
main().catch((error: NodeJS.ErrnoException) => {
    process.stderr.write(error?.code === 'EADDRINUSE'
        ? 'Nanoleaf MCP port is already in use. Stop its owner or choose another port in the private configuration.\n'
        : 'Nanoleaf MCP could not start. Check private configuration, dependencies and the selected local port.\n');
    process.exitCode = 1;
});
