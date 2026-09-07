import { bindServiceTools, createDeviceRegistry, type ServiceExtension, type Request, type Snapshot, type Receipt } from '@jimmie-potts/device-mcp';
import { schema, validate } from '@jimmie-potts/device-contracts';
import type { Config, CredentialStore } from './config.js';
import { exchange, TransportFailure, type ExchangeResult, type Operation } from './transport.js';
type Transport = (config: Config, operation: Operation, token: string, request?: unknown) => Promise<ExchangeResult>;
const ref = (name: string) => ({ $ref: `#/$defs/${name}` });
const outputSchema = { type: 'object' as const, additionalProperties: false, $defs: schema.$defs, properties: { kind: { enum: ['snapshot', 'receipt', 'failure'] }, snapshot: ref('snapshot'), receipt: ref('receipt'), code: ref('failureCode'), priorEffects: { enum: ['none', 'possible'] }, requestId: ref('ticket'), retry: { const: 'never-automatically' } }, required: ['kind'], oneOf: [{ properties: { kind: { const: 'snapshot' }, snapshot: ref('snapshot') }, required: ['snapshot'] }, { properties: { kind: { const: 'receipt' }, receipt: ref('receipt') }, required: ['receipt'] }, { properties: { kind: { const: 'failure' }, code: ref('failureCode'), priorEffects: { enum: ['none', 'possible'] }, retry: { const: 'never-automatically' } }, required: ['code', 'priorEffects', 'retry'] }] };
const failures: Record<number, string[]> = { 400: ['invalid-request'], 401: ['unauthenticated'], 403: ['forbidden'], 404: ['unknown-device'], 409: ['revision-conflict', 'stale-generation', 'request-conflict', 'request-order'], 410: ['request-expired'], 422: ['unsupported-capability'], 429: ['capacity'], 503: ['transport-failure'] };
export function bindings(config: Config, store: Pick<CredentialStore, 'forDispatch'>, transport: Transport = exchange) {
    const failure = (code: string, possible: boolean, request?: Request) => ({ data: { kind: 'failure', code, priorEffects: possible ? 'possible' : 'none', retry: 'never-automatically', ...(request ? { requestId: request.requestId } : {}) }, isError: true });
    const extension = (write: boolean): ServiceExtension => ({
        description: write ? 'Request Work, Quiet or Free through the Windows controller. Preserve the snapshot request identity; queued or sent is not visible-light confirmation.' : 'Read the Windows controller snapshot without refreshing tasks or sending light commands.',
        scope: write ? 'control' : 'read', annotations: { readOnlyHint: !write, destructiveHint: write, idempotentHint: !write, openWorldHint: true },
        inputSchema: { type: 'object', additionalProperties: false, $defs: schema.$defs, properties: write ? { requestId: ref('ticket'), expectedConfigurationRevision: ref('counter'), expectedGeneration: ref('ticket'), mode: { enum: ['Work', 'Quiet', 'Free'] } } : {}, required: write ? ['requestId', 'expectedConfigurationRevision', 'expectedGeneration', 'mode'] : [] }, outputSchema,
        async invoke(args, context) {
            const request: Request | undefined = write ? { apiVersion: '1.0', controllerId: config.controllerId, deviceId: config.deviceId, requestId: args.requestId as Request['requestId'], expectedConfigurationRevision: args.expectedConfigurationRevision as number, expectedGeneration: args.expectedGeneration as Request['expectedGeneration'], command: { kind: 'mode.set', mode: args.mode as 'Work' | 'Quiet' | 'Free' } } : undefined;
            if (request && !validate('request', request))
                return failure('invalid-request', false, request);
            let credential;
            try {
                credential = await store.forDispatch(context.principalId, write ? 'control' : 'read');
            }
            catch {
                return failure('forbidden', false, request);
            }
            let result: ExchangeResult;
            try {
                result = await transport(config, write ? 'command' : 'snapshot', credential.upstreamToken, request);
            }
            catch (error) {
                return failure(write && (!(error instanceof TransportFailure) || error.possible) ? 'uncertain-result' : 'transport-failure', write && (!(error instanceof TransportFailure) || error.possible), request);
            }
            const value = result.body;
            if (!write && result.status === 200 && validate('snapshot', value)) {
                const snapshot = value as Snapshot;
                if (snapshot.identity.controllerId === config.controllerId && snapshot.identity.deviceId === config.deviceId)
                    return { data: { kind: 'snapshot', snapshot } };
            }
            if (write && validate('receipt', value)) {
                const receipt = value as Receipt;
                const receiptStatus = [200, 202].includes(result.status) || ([409, 422, 503].includes(result.status) && receipt.outcome === 'failed' && failures[result.status]?.includes(receipt.failure?.code ?? ''));
                if (receiptStatus && receipt.controllerId === config.controllerId && receipt.deviceId === config.deviceId && receipt.requestId.epoch === request!.requestId.epoch && receipt.requestId.sequence === request!.requestId.sequence)
                    return { data: { kind: 'receipt', receipt }, isError: ['failed', 'partially-applied', 'uncertain'].includes(receipt.outcome) };
            }
            if (value && typeof value === 'object' && !Array.isArray(value) && Object.keys(value).join(',') === 'failure') {
                const inner = (value as {
                    failure: unknown;
                }).failure;
                if (inner && typeof inner === 'object' && !Array.isArray(inner) && Object.keys(inner).join(',') === 'code') {
                    const code = (inner as {
                        code: unknown;
                    }).code;
                    if (typeof code === 'string' && failures[result.status]?.includes(code))
                        return failure(code, false, request);
                }
            }
            return failure(write ? 'uncertain-result' : 'transport-failure', write, request);
        }
    });
    const registry = createDeviceRegistry([{ controllerId: config.controllerId, deviceId: config.deviceId, extensions: { status: extension(false), mode: extension(true) } }]);
    const tools = bindServiceTools(registry, { deviceId: config.deviceId, bindings: [{ extension: 'status', name: 'nanoleaf_status' }, { extension: 'mode', name: 'nanoleaf_mode_set' }] });
    return { registry, tools };
}
