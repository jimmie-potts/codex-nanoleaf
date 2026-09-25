import { constants } from 'node:fs';
import { open } from 'node:fs/promises';
import { createHash, timingSafeEqual } from 'node:crypto';
import { isAbsolute } from 'node:path';
import type { MachinePrincipal } from '@jimmie-potts/device-mcp';
export type Config = {
    enabled: boolean;
    port: number;
    controllerPort: number;
    controllerId: string;
    deviceId: string;
    credentialsFile: string;
    transport: 'loopback-http';
};
// The installed Linux configuration may still name the transport by its earlier identifier.
const transportAliases: Record<string, Config['transport']> = { 'loopback-http': 'loopback-http', 'windows-http': 'loopback-http' };
export type Principal = {
    id: string;
    tokenSha256: string;
    scopes: ('read' | 'control')[];
    upstreamToken: string;
};
const idPattern = /^[A-Za-z0-9._-]{1,128}$/;
export function object(value: unknown, required: string[], optional: string[] = []): asserts value is Record<string, unknown> {
    if (!value || typeof value !== 'object' || Array.isArray(value) || Object.keys(value).some(k => ![...required, ...optional].includes(k)) || required.some(k => !Object.hasOwn(value, k)))
        throw new Error('Invalid configuration');
}
export async function boundedFile(path: string, max = 65536): Promise<string> {
    const handle = await open(path, constants.O_RDONLY | (constants.O_NONBLOCK ?? 0));
    try {
        if (!(await handle.stat()).isFile())
            throw new Error('Configuration must be a regular file');
        const bytes = Buffer.alloc(max + 1);
        let count = 0;
        while (count < bytes.length) {
            const result = await handle.read(bytes, count, bytes.length - count, null);
            if (!result.bytesRead)
                break;
            count += result.bytesRead;
        }
        if (count > max)
            throw new Error('Configuration exceeds limit');
        return new TextDecoder('utf-8', { fatal: true }).decode(bytes.subarray(0, count));
    }
    finally {
        await handle.close();
    }
}
export async function loadConfig(path: string): Promise<Config> {
    const value: unknown = JSON.parse(await boundedFile(path));
    object(value, ['enabled', 'port', 'controllerPort', 'controllerId', 'deviceId', 'credentialsFile', 'transport']);
    if (typeof value.enabled !== 'boolean' || ![value.port, value.controllerPort].every(p => Number.isInteger(p) && Number(p) >= 1024 && Number(p) <= 65535) || ![value.controllerId, value.deviceId].every(v => typeof v === 'string' && idPattern.test(v)) || typeof value.credentialsFile !== 'string' || !isAbsolute(value.credentialsFile) || value.credentialsFile.length > 4096)
        throw new Error('Invalid configuration');
    if (typeof value.transport !== 'string' || !Object.hasOwn(transportAliases, value.transport))
        throw new Error('Invalid transport configuration');
    return { ...value, transport: transportAliases[value.transport] } as Config;
}
export class CredentialStore {
    constructor(private readonly config: Config) { }
    private async rows(): Promise<Principal[]> {
        const value: unknown = JSON.parse(await boundedFile(this.config.credentialsFile));
        object(value, ['principals']);
        if (!Array.isArray(value.principals) || value.principals.length > 32)
            throw new Error('Invalid credentials');
        const ids = new Set(), hashes = new Set(), upstream = new Set();
        for (const row of value.principals) {
            object(row, ['id', 'tokenSha256', 'scopes', 'upstreamToken']);
            if (typeof row.id !== 'string' || !idPattern.test(row.id) || typeof row.tokenSha256 !== 'string' || !(/^[0-9a-f]{64}$/.test(row.tokenSha256)) || !Array.isArray(row.scopes) || row.scopes.length < 1 || row.scopes.length > 2 || new Set(row.scopes).size !== row.scopes.length || row.scopes.some(s => s !== 'read' && s !== 'control') || typeof row.upstreamToken !== 'string' || !(/^[A-Za-z0-9_-]{43,512}$/.test(row.upstreamToken)) || ids.has(row.id) || hashes.has(row.tokenSha256) || upstream.has(row.upstreamToken))
                throw new Error('Invalid credentials');
            ids.add(row.id);
            hashes.add(row.tokenSha256);
            upstream.add(row.upstreamToken);
        }
        return value.principals as Principal[];
    }
    async authenticate(token: string): Promise<MachinePrincipal | null> {
        if (!(/^[A-Za-z0-9_-]{43,512}$/.test(token)))
            return null;
        try {
            const digest = createHash('sha256').update(token).digest();
            const row = (await this.rows()).find(p => timingSafeEqual(digest, Buffer.from(p.tokenSha256, 'hex')));
            return row ? { id: row.id, credential: { kind: 'machine', status: 'active', declared: true, devices: [this.config.deviceId], scopes: row.scopes } } : null;
        }
        catch {
            return null;
        }
    }
    async forDispatch(id: string, scope: 'read' | 'control'): Promise<Principal> { const row = (await this.rows()).find(p => p.id === id); if (!row || !row.scopes.includes(scope))
        throw new Error('Authorization unavailable'); return row; }
}
