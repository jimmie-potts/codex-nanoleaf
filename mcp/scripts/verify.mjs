import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { readFile } from 'node:fs/promises';
import { verifyArchiveChecksum, verifyInstalledMcpPackage } from '@jimmie-potts/device-mcp';
const root = resolve(dirname(fileURLToPath(import.meta.url)), '../..');
const receipt = JSON.parse(await readFile(resolve(root, 'vendor/device-mcp-1.0.1-receipt.json'), 'utf8'));
if (receipt.version !== '1.0.1' || receipt.sourceRevision !== '6b561baf3698415740184b702fc73107daec9022' || receipt.sha256 !== 'e6cd65600d02128f5c996e6e4940654d1a9a67b312f7d27148a2137d766a7e32')
    throw new Error('Unexpected release receipt');
await verifyArchiveChecksum(resolve(root, 'vendor/jimmie-potts-device-mcp-1.0.1.tgz'), receipt.sha256);
await verifyInstalledMcpPackage(resolve(dirname(fileURLToPath(import.meta.resolve('@jimmie-potts/device-mcp'))), '..'));
await verifyArchiveChecksum(resolve(root, 'bridge/vendor/device-contracts-1.0.0/jimmie-potts-device-contracts-1.0.0.tgz'), '5e0b30ac92e6e8e1e38d8249b740b565de66e3cc810a04bc6fac23e182e84e87');
// The direct runtime contract must have exactly the verified bundled files.
const direct = resolve(dirname(fileURLToPath(import.meta.resolve('@jimmie-potts/device-contracts'))), '..');
const bundled = resolve(dirname(fileURLToPath(import.meta.resolve('@jimmie-potts/device-mcp'))), '../node_modules/@jimmie-potts/device-contracts');
const manifest = JSON.parse(await readFile(resolve(bundled, 'manifest.json'), 'utf8'));
for (const file of Object.keys(manifest.files)) {
    const [a, b] = await Promise.all([readFile(resolve(direct, file)), readFile(resolve(bundled, file))]);
    if (!a.equals(b))
        throw new Error('Runtime contract mismatch');
}
console.log('Verified immutable MCP package and runtime contract.');
