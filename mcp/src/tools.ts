import { bindServiceTools, createDeviceRegistry, type ServiceExtension, type Request, type Snapshot, type Receipt } from '@jimmie-potts/device-mcp';
import { schema, validate, type Command } from '@jimmie-potts/device-contracts';
import type { Config, CredentialStore } from './config.js';
import { exchange, TransportFailure, type ExchangeResult, type Operation } from './transport.js';
type Transport = (config: Config, operation: Operation, token: string, request?: unknown) => Promise<ExchangeResult>;
const ref = (name: string) => ({ $ref: `#/$defs/${name}` });
const outputSchema = { type: 'object' as const, additionalProperties: false, $defs: schema.$defs, properties: { kind: { enum: ['snapshot', 'receipt', 'failure'] }, snapshot: ref('snapshot'), receipt: ref('receipt'), code: ref('failureCode'), priorEffects: { enum: ['none', 'possible'] }, requestId: ref('ticket'), retry: { const: 'never-automatically' } }, required: ['kind'], oneOf: [{ properties: { kind: { const: 'snapshot' }, snapshot: ref('snapshot') }, required: ['snapshot'] }, { properties: { kind: { const: 'receipt' }, receipt: ref('receipt') }, required: ['receipt'] }, { properties: { kind: { const: 'failure' }, code: ref('failureCode'), priorEffects: { enum: ['none', 'possible'] }, retry: { const: 'never-automatically' } }, required: ['code', 'priorEffects', 'retry'] }] };
const sceneItemSchema = { type: 'object' as const, additionalProperties: false, properties: { id: { type: 'string', pattern: '^scene-[a-f0-9]{64}$' }, name: { type: 'string', minLength: 1, maxLength: 80 } }, required: ['id'] };
const scenesOutputSchema = { type: 'object' as const, additionalProperties: false, $defs: schema.$defs, properties: { kind: { enum: ['scenes', 'failure'] }, scenes: { type: 'array', maxItems: 256, items: sceneItemSchema }, code: ref('failureCode'), priorEffects: { enum: ['none', 'possible'] }, retry: { const: 'never-automatically' } }, required: ['kind'], oneOf: [{ properties: { kind: { const: 'scenes' }, scenes: { type: 'array', maxItems: 256, items: sceneItemSchema } }, required: ['scenes'] }, { properties: { kind: { const: 'failure' }, code: ref('failureCode'), priorEffects: { enum: ['none', 'possible'] }, retry: { const: 'never-automatically' } }, required: ['code', 'priorEffects', 'retry'] }] };
const SCENE_ID = /^scene-[a-f0-9]{64}$/;
type SceneEntry = { id: string; name?: string };
const failures: Record<number, string[]> = { 400: ['invalid-request'], 401: ['unauthenticated'], 403: ['forbidden'], 404: ['unknown-device'], 409: ['revision-conflict', 'stale-generation', 'request-conflict', 'request-order'], 410: ['request-expired'], 422: ['unsupported-capability'], 429: ['capacity'], 503: ['transport-failure'] };
function validScenes(value: unknown, config: Config): value is { scenes: SceneEntry[] } {
    if (!value || typeof value !== 'object' || Array.isArray(value))
        return false;
    const view = value as Record<string, unknown>;
    if (view.apiVersion !== 'nanoleaf.integration/1.0')
        return false;
    const identity = view.identity;
    if (!identity || typeof identity !== 'object' || Array.isArray(identity))
        return false;
    const id = identity as Record<string, unknown>;
    if (id.controllerId !== config.controllerId || id.deviceId !== config.deviceId)
        return false;
    const scenes = view.scenes;
    if (!Array.isArray(scenes) || scenes.length > 256)
        return false;
    return scenes.every(entry => entry && typeof entry === 'object' && !Array.isArray(entry)
        && Object.keys(entry).every(key => key === 'id' || key === 'name')
        && typeof (entry as SceneEntry).id === 'string' && SCENE_ID.test((entry as SceneEntry).id)
        && (!('name' in entry) || (typeof (entry as SceneEntry).name === 'string' && (entry as SceneEntry).name!.length >= 1 && (entry as SceneEntry).name!.length <= 80)));
}
export function bindings(config: Config, store: Pick<CredentialStore, 'forDispatch'>, transport: Transport = exchange) {
    const failure = (code: string, possible: boolean, request?: Request) => ({ data: { kind: 'failure', code, priorEffects: possible ? 'possible' : 'none', retry: 'never-automatically', ...(request ? { requestId: request.requestId } : {}) }, isError: true });
    const genericFailure = (value: unknown, status: number) => {
        if (value && typeof value === 'object' && !Array.isArray(value) && Object.keys(value).join(',') === 'failure') {
            const inner = (value as { failure: unknown }).failure;
            if (inner && typeof inner === 'object' && !Array.isArray(inner) && Object.keys(inner).join(',') === 'code') {
                const code = (inner as { code: unknown }).code;
                if (typeof code === 'string' && failures[status]?.includes(code))
                    return code;
            }
        }
        return undefined;
    };
    const extension = (write: boolean): ServiceExtension => ({
        description: write ? 'Request Work, Quiet or Free through the Nanoleaf controller. Preserve the snapshot request identity; queued or sent is not visible-light confirmation.' : 'Read the Nanoleaf controller snapshot without refreshing tasks or sending light commands.',
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
            const code = genericFailure(value, result.status);
            if (code)
                return failure(code, false, request);
            return failure(write ? 'uncertain-result' : 'transport-failure', write, request);
        }
    });
    const sceneActivate: ServiceExtension = {
        description: 'Activate a saved Nanoleaf scene through the controller. Free mode only; the tool never switches mode itself. Preserve the request identity; queued or sent is not visible-light confirmation.',
        scope: 'control', annotations: { readOnlyHint: false, destructiveHint: true, idempotentHint: false, openWorldHint: true },
        inputSchema: { type: 'object', additionalProperties: false, $defs: schema.$defs, properties: { requestId: ref('ticket'), expectedConfigurationRevision: ref('counter'), expectedGeneration: ref('ticket'), sceneId: ref('id') }, required: ['requestId', 'expectedConfigurationRevision', 'expectedGeneration', 'sceneId'] }, outputSchema,
        async invoke(args, context) {
            const command: Command = { kind: 'scene.activate', sceneId: args.sceneId as string };
            const request: Request = { apiVersion: '1.0', controllerId: config.controllerId, deviceId: config.deviceId, requestId: args.requestId as Request['requestId'], expectedConfigurationRevision: args.expectedConfigurationRevision as number, expectedGeneration: args.expectedGeneration as Request['expectedGeneration'], command };
            if (!validate('request', request))
                return failure('invalid-request', false, request);
            let credential;
            try {
                credential = await store.forDispatch(context.principalId, 'control');
            }
            catch {
                return failure('forbidden', false, request);
            }
            let result: ExchangeResult;
            try {
                result = await transport(config, 'command', credential.upstreamToken, request);
            }
            catch (error) {
                return failure(!(error instanceof TransportFailure) || error.possible ? 'uncertain-result' : 'transport-failure', !(error instanceof TransportFailure) || error.possible, request);
            }
            const value = result.body;
            if (validate('receipt', value)) {
                const receipt = value as Receipt;
                const receiptStatus = [200, 202].includes(result.status) || ([409, 422, 503].includes(result.status) && receipt.outcome === 'failed' && failures[result.status]?.includes(receipt.failure?.code ?? ''));
                if (receiptStatus && receipt.controllerId === config.controllerId && receipt.deviceId === config.deviceId && receipt.requestId.epoch === request.requestId.epoch && receipt.requestId.sequence === request.requestId.sequence)
                    return { data: { kind: 'receipt', receipt }, isError: ['failed', 'partially-applied', 'uncertain'].includes(receipt.outcome) };
            }
            const code = genericFailure(value, result.status);
            if (code)
                return failure(code, false, request);
            return failure('uncertain-result', true, request);
        }
    };
    const scenesList: ServiceExtension = {
        description: 'List the Nanoleaf controller\'s advertised saved scenes with their opaque IDs and Nanoleaf app names, without refreshing tasks or sending light commands.',
        scope: 'read', annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: true },
        inputSchema: { type: 'object', additionalProperties: false, $defs: schema.$defs, properties: {}, required: [] }, outputSchema: scenesOutputSchema,
        async invoke(_args, context) {
            let credential;
            try {
                credential = await store.forDispatch(context.principalId, 'read');
            }
            catch {
                return failure('forbidden', false);
            }
            let result: ExchangeResult;
            try {
                result = await transport(config, 'scenes', credential.upstreamToken);
            }
            catch {
                return failure('transport-failure', false);
            }
            const value = result.body;
            if (result.status === 200 && validScenes(value, config))
                return { data: { kind: 'scenes', scenes: value.scenes } };
            const code = genericFailure(value, result.status);
            if (code)
                return failure(code, false);
            return failure('transport-failure', false);
        }
    };
    const registry = createDeviceRegistry([{ controllerId: config.controllerId, deviceId: config.deviceId, extensions: { status: extension(false), mode: extension(true), scenes: scenesList, sceneActivate } }]);
    const tools = bindServiceTools(registry, { deviceId: config.deviceId, bindings: [{ extension: 'status', name: 'nanoleaf_status' }, { extension: 'mode', name: 'nanoleaf_mode_set' }, { extension: 'scenes', name: 'nanoleaf_scenes_list' }, { extension: 'sceneActivate', name: 'nanoleaf_scene_activate' }] });
    return { registry, tools };
}
