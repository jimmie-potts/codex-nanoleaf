import { bindServiceTools, createDeviceRegistry, type ServiceExtension, type Request, type Snapshot, type Receipt } from '@jimmie-potts/device-mcp';
import { schema, validate, type Command } from '@jimmie-potts/device-contracts';
import type { Config, CredentialStore } from './config.js';
import { exchange, TransportFailure, type ExchangeResult, type Operation } from './transport.js';
type Transport = (config: Config, operation: Operation, token: string, request?: unknown) => Promise<ExchangeResult>;
const ref = (name: string) => ({ $ref: `#/$defs/${name}` });
const outputSchema = { type: 'object' as const, additionalProperties: false, $defs: schema.$defs, properties: { kind: { enum: ['snapshot', 'receipt', 'failure'] }, snapshot: ref('snapshot'), receipt: ref('receipt'), code: ref('failureCode'), priorEffects: { enum: ['none', 'possible'] }, requestId: ref('ticket'), retry: { const: 'never-automatically' } }, required: ['kind'], oneOf: [{ properties: { kind: { const: 'snapshot' }, snapshot: ref('snapshot') }, required: ['snapshot'] }, { properties: { kind: { const: 'receipt' }, receipt: ref('receipt') }, required: ['receipt'] }, { properties: { kind: { const: 'failure' }, code: ref('failureCode'), priorEffects: { enum: ['none', 'possible'] }, retry: { const: 'never-automatically' } }, required: ['code', 'priorEffects', 'retry'] }] };
const SCENE_ID_PATTERN = 'scene-[a-f0-9]{64}', SCENE_NAME_MAX = 80;
const SCENE_ID = new RegExp(`^${SCENE_ID_PATTERN}$`);
const sceneItemSchema = { type: 'object' as const, additionalProperties: false, properties: { id: { type: 'string', pattern: `^${SCENE_ID_PATTERN}$` }, name: { type: 'string', minLength: 1, maxLength: SCENE_NAME_MAX } }, required: ['id'] };
const scenesOutputSchema = { type: 'object' as const, additionalProperties: false, $defs: schema.$defs, properties: { kind: { enum: ['scenes', 'failure'] }, scenes: { type: 'array', maxItems: 256, items: sceneItemSchema }, code: ref('failureCode'), priorEffects: { enum: ['none', 'possible'] }, retry: { const: 'never-automatically' } }, required: ['kind'], oneOf: [{ properties: { kind: { const: 'scenes' }, scenes: { type: 'array', maxItems: 256, items: sceneItemSchema } }, required: ['scenes'] }, { properties: { kind: { const: 'failure' }, code: ref('failureCode'), priorEffects: { enum: ['none', 'possible'] }, retry: { const: 'never-automatically' } }, required: ['code', 'priorEffects', 'retry'] }] };
type SceneEntry = { id: string; name?: string };
const EXTENSION = 'nanoleaf.integration/1.0', MAX_SEQUENCE = 9007199254740991;
const PATTERNS = ['wave', 'gradient', 'pulse', 'breathe', 'sparkle'], SPATIAL = ['wave', 'gradient'];
const SPEEDS = ['slow', 'medium', 'fast', 'faster'], DIRECTIONS = ['left', 'right', 'up', 'down', 'outward', 'inward', 'clockwise', 'counterclockwise'];
const OUTCOMES = ['queued', 'sent', 'failed', 'uncertain', 'cancelled'], PRIOR_EFFECTS = ['none', 'confirmed-transmission', 'possible'];
const FREE_FIRST = 'Animations play only in Free. If nanoleaf_animations_list reports Work or Quiet, switch to Free with nanoleaf_mode_set, then list again for a fresh requestId and expectedRevision. If it already reports Free, refresh the list to check the favorite name and saved layout; choose a non-spatial pattern if positions are unavailable.';
const HEX = (length: number) => new RegExp(`^[a-f0-9]{${length}}$`);
const extensionTicket = { type: 'object' as const, additionalProperties: false, properties: { epoch: { type: 'string', pattern: '^[a-f0-9]{32}$' }, sequence: { type: 'integer', minimum: 0, maximum: MAX_SEQUENCE } }, required: ['epoch', 'sequence'] };
const word = { type: 'string', pattern: '^[a-z]{1,32}$' }, count = { type: 'integer', minimum: 0, maximum: MAX_SEQUENCE };
const colorsSchema = { type: 'array', minItems: 1, maxItems: 8, items: { type: 'string', pattern: '^#[0-9a-fA-F]{6}$' } };
const favoriteName = { type: 'string', minLength: 1, maxLength: 80 };
const recipeProperties = { pattern: { enum: PATTERNS }, colors: colorsSchema, speed: { enum: SPEEDS }, direction: { enum: DIRECTIONS }, loop: { type: 'boolean' } };
const recipeSchema = { type: 'object', additionalProperties: false, properties: { ...recipeProperties, preset: word },
    oneOf: [{ properties: { preset: word, pattern: false, colors: false, speed: false, direction: false, loop: false }, required: ['preset'] },
        { properties: { preset: false }, required: ['pattern', 'colors'] }] };
const savedRecipeSchema = { type: 'object', additionalProperties: false, properties: recipeProperties, required: ['pattern', 'colors', 'speed', 'loop'] };
const favoriteSchema = { type: 'object', additionalProperties: false, properties: { name: favoriteName, animation: savedRecipeSchema }, required: ['name', 'animation'] };
const presetSchema = { type: 'object', additionalProperties: false, properties: { id: word, pattern: { enum: PATTERNS }, colors: colorsSchema, speed: { enum: SPEEDS }, direction: { enum: DIRECTIONS } }, required: ['id', 'pattern', 'colors', 'speed'] };
const animationsViewSchema = { type: 'object' as const, additionalProperties: false, properties: { apiVersion: { const: EXTENSION }, identity: ref('identity'), mode: { enum: ['Work', 'Quiet', 'Free'] }, revision: { type: 'string', pattern: '^[a-f0-9]{64}$' }, nextRequestId: extensionTicket, rememberedSceneId: { anyOf: [{ type: 'null' }, { type: 'string', pattern: `^${SCENE_ID_PATTERN}$` }] },
    presets: { type: 'array', maxItems: 32, items: presetSchema }, favorites: { type: 'array', maxItems: 32, items: favoriteSchema },
    patterns: { type: 'array', maxItems: 16, items: { type: 'object', additionalProperties: false, properties: { id: word, spatial: { type: 'boolean' } }, required: ['id', 'spatial'] } }, speeds: { type: 'array', maxItems: 16, items: word }, directions: { type: 'array', maxItems: 16, items: word },
    defaults: { type: 'object', additionalProperties: false, properties: { speed: word, direction: word, loop: { type: 'boolean' } }, required: ['speed', 'direction', 'loop'] },
    limits: { type: 'object', additionalProperties: false, properties: { minColors: count, maxColors: count, maxFramesPerZone: count, maxEffectBytes: count, maxFavorites: { const: 32 }, maxFavoriteName: { const: 80 } }, required: ['minColors', 'maxColors', 'maxFramesPerZone', 'maxEffectBytes', 'maxFavorites', 'maxFavoriteName'] } },
    required: ['apiVersion', 'identity', 'mode', 'revision', 'nextRequestId', 'rememberedSceneId', 'presets', 'favorites', 'patterns', 'speeds', 'directions', 'defaults', 'limits'] };
const animationReceiptSchema = { type: 'object' as const, additionalProperties: false, properties: { apiVersion: { const: EXTENSION }, requestId: extensionTicket, outcome: { enum: OUTCOMES }, priorEffects: { enum: PRIOR_EFFECTS }, physicalOutcome: { const: 'unknown' }, failure: { type: 'object', additionalProperties: false, properties: { code: ref('failureCode') }, required: ['code'] } }, required: ['apiVersion', 'requestId', 'outcome', 'priorEffects', 'physicalOutcome'] };
const failureVariant = { properties: { kind: { const: 'failure' }, code: ref('failureCode'), priorEffects: { enum: ['none', 'possible'] }, retry: { const: 'never-automatically' }, requestId: extensionTicket, message: { type: 'string', maxLength: 512 } }, required: ['code', 'priorEffects', 'retry'] };
const animationsOutputSchema = { type: 'object' as const, additionalProperties: false, $defs: schema.$defs, properties: { ...failureVariant.properties, kind: { enum: ['animations', 'failure'] }, animations: animationsViewSchema }, required: ['kind'], oneOf: [{ properties: { kind: { const: 'animations' }, animations: animationsViewSchema }, required: ['animations'] }, failureVariant] };
const animationPlayOutputSchema = { type: 'object' as const, additionalProperties: false, $defs: schema.$defs, properties: { ...failureVariant.properties, kind: { enum: ['receipt', 'failure'] }, receipt: animationReceiptSchema }, required: ['kind'], oneOf: [{ properties: { kind: { const: 'receipt' }, receipt: animationReceiptSchema }, required: ['receipt'] }, failureVariant] };
const configurationReceiptSchema = { ...animationReceiptSchema, properties: { ...animationReceiptSchema.properties,
    outcome: { enum: ['queued', 'applied', 'failed', 'cancelled'] }, priorEffects: { enum: ['none', 'configuration'] } } };
const configurationOutputSchema = { ...animationPlayOutputSchema, properties: { ...animationPlayOutputSchema.properties, receipt: configurationReceiptSchema },
    oneOf: [{ properties: { kind: { const: 'receipt' }, receipt: configurationReceiptSchema }, required: ['receipt'] }, failureVariant] };
const record = (value: unknown): value is Record<string, unknown> => !!value && typeof value === 'object' && !Array.isArray(value);
const exactKeys = (value: Record<string, unknown>, required: string[], optional: string[] = []) => required.every(key => key in value) && Object.keys(value).every(key => required.includes(key) || optional.includes(key));
const words = (value: unknown) => Array.isArray(value) && value.length <= 16 && value.every(item => typeof item === 'string' && /^[a-z]{1,32}$/.test(item));
const counter = (value: unknown) => Number.isSafeInteger(value) && (value as number) >= 0;
function validTicket(value: unknown): value is { epoch: string; sequence: number } {
    return record(value) && exactKeys(value, ['epoch', 'sequence']) && typeof value.epoch === 'string' && HEX(32).test(value.epoch) && counter(value.sequence);
}
const validName = (value: unknown): value is string => typeof value === 'string' && [...value].length >= 1 && [...value].length <= 80 && value.trim().length > 0 && !/\p{C}/u.test(value);
function validRecipe(value: unknown, complete = false): boolean {
    if (!record(value)) return false;
    if ('preset' in value) return !complete && exactKeys(value, ['preset']) && words([value.preset]);
    return exactKeys(value, complete ? ['pattern', 'colors', 'speed', 'loop'] : ['pattern', 'colors'], complete ? ['direction'] : ['speed', 'direction', 'loop'])
        && PATTERNS.includes(value.pattern as string) && Array.isArray(value.colors) && value.colors.length >= 1 && value.colors.length <= 8
        && value.colors.every(color => typeof color === 'string' && /^#[0-9a-fA-F]{6}$/.test(color))
        && (!('speed' in value) || SPEEDS.includes(value.speed as string)) && (!('loop' in value) || typeof value.loop === 'boolean')
        && (!('direction' in value) || SPATIAL.includes(value.pattern as string) && DIRECTIONS.includes(value.direction as string))
        && (!complete || !SPATIAL.includes(value.pattern as string) || 'direction' in value);
}
function validAnimations(value: unknown, config: Config): boolean {
    if (!record(value) || !exactKeys(value, ['apiVersion', 'identity', 'mode', 'revision', 'nextRequestId', 'rememberedSceneId', 'presets', 'favorites', 'patterns', 'speeds', 'directions', 'defaults', 'limits']) || value.apiVersion !== EXTENSION)
        return false;
    if (!validate('identity', value.identity) || (value.identity as { controllerId: string }).controllerId !== config.controllerId || (value.identity as { deviceId: string }).deviceId !== config.deviceId)
        return false;
    const { defaults, limits, patterns } = value;
    return ['Work', 'Quiet', 'Free'].includes(value.mode as string) && typeof value.revision === 'string' && HEX(64).test(value.revision) && validTicket(value.nextRequestId)
        && Array.isArray(patterns) && patterns.length <= 16 && patterns.every(item => record(item) && exactKeys(item, ['id', 'spatial']) && words([item.id]) && typeof item.spatial === 'boolean')
        && (value.rememberedSceneId === null || (typeof value.rememberedSceneId === 'string' && SCENE_ID.test(value.rememberedSceneId)))
        && Array.isArray(value.presets) && value.presets.length <= 32 && value.presets.every(item =>
            record(item) && exactKeys(item, ['id', 'pattern', 'colors', 'speed'], ['direction'])
            && words([item.id]) && PATTERNS.includes(item.pattern as string) && SPEEDS.includes(item.speed as string)
            && Array.isArray(item.colors) && item.colors.length >= 1 && item.colors.length <= 8
            && item.colors.every(color => typeof color === 'string' && /^#[0-9a-fA-F]{6}$/.test(color))
            && (!('direction' in item) || (SPATIAL.includes(item.pattern as string) && DIRECTIONS.includes(item.direction as string))))
        && new Set(value.presets.map(item => item.id)).size === value.presets.length
        && Array.isArray(value.favorites) && value.favorites.length <= 32 && value.favorites.every(item => record(item) && exactKeys(item, ['name', 'animation']) && validName(item.name) && validRecipe(item.animation, true))
        && new Set(value.favorites.map(item => item.name)).size === value.favorites.length
        && words(value.speeds) && words(value.directions)
        && record(defaults) && exactKeys(defaults, ['speed', 'direction', 'loop']) && words([defaults.speed, defaults.direction]) && typeof defaults.loop === 'boolean'
        && record(limits) && exactKeys(limits, ['minColors', 'maxColors', 'maxFramesPerZone', 'maxEffectBytes', 'maxFavorites', 'maxFavoriteName']) && Object.values(limits).every(counter) && limits.maxFavorites === 32 && limits.maxFavoriteName === 80;
}
/** Only a receipt for exactly this extension ticket; sent is transport evidence, never visible output. */
function animationReceipt(value: unknown, status: number, ticket: { epoch: string; sequence: number }, configuration = false): Record<string, unknown> | undefined {
    if (!record(value) || !exactKeys(value, ['apiVersion', 'requestId', 'outcome', 'priorEffects', 'physicalOutcome'], ['failure']) || value.apiVersion !== EXTENSION
        || !validTicket(value.requestId) || value.requestId.epoch !== ticket.epoch || value.requestId.sequence !== ticket.sequence
        || !(configuration ? ['queued', 'applied', 'failed', 'cancelled'] : OUTCOMES).includes(value.outcome as string) || !(configuration ? ['none', 'configuration'] : PRIOR_EFFECTS).includes(value.priorEffects as string) || value.physicalOutcome !== 'unknown'
        || ('failure' in value && !(record(value.failure) && exactKeys(value.failure, ['code']) && validate('failureCode', value.failure.code))))
        return undefined;
    if (configuration && (value.priorEffects !== (value.outcome === 'applied' ? 'configuration' : 'none') || ['queued', 'applied'].includes(value.outcome as string) && 'failure' in value)) return undefined;
    return [200, 202].includes(status) || (status === 503 && value.outcome === 'failed') ? value : undefined;
}
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
        && (!('name' in entry) || (typeof (entry as SceneEntry).name === 'string' && (entry as SceneEntry).name!.length >= 1 && (entry as SceneEntry).name!.length <= SCENE_NAME_MAX)));
}
/** Shared by mode.set and scene.activate: the only two commands whose success path is a receipt. */
function matchedReceipt(value: unknown, status: number, request: Request): Receipt | undefined {
    if (!validate('receipt', value))
        return undefined;
    const receipt = value as Receipt;
    const receiptStatus = [200, 202].includes(status) || ([409, 422, 503].includes(status) && receipt.outcome === 'failed' && failures[status]?.includes(receipt.failure?.code ?? ''));
    if (receiptStatus && receipt.controllerId === request.controllerId && receipt.deviceId === request.deviceId && receipt.requestId.epoch === request.requestId.epoch && receipt.requestId.sequence === request.requestId.sequence)
        return receipt;
    return undefined;
}
/** The service extensions for one fixed device; `name` is how its descriptions refer to it. */
function extensions(config: Config, store: Pick<CredentialStore, 'forDispatch'>, transport: Transport, name: string) {
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
        description: write ? `Request Work, Quiet or Free through the ${name} controller. Preserve the snapshot request identity; queued or sent is not visible-light confirmation.` : `Read the ${name} controller snapshot without refreshing tasks or sending light commands.`,
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
            if (write) {
                const receipt = matchedReceipt(value, result.status, request!);
                if (receipt)
                    return { data: { kind: 'receipt', receipt }, isError: ['failed', 'partially-applied', 'uncertain'].includes(receipt.outcome) };
            }
            const code = genericFailure(value, result.status);
            if (code)
                return failure(code, false, request);
            return failure(write ? 'uncertain-result' : 'transport-failure', write, request);
        }
    });
    const sceneActivate: ServiceExtension = {
        description: `Activate a saved ${name} scene through the controller. Free mode only; the tool never switches mode itself. Preserve the request identity; queued or sent is not visible-light confirmation.`,
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
            const receipt = matchedReceipt(value, result.status, request);
            if (receipt)
                return { data: { kind: 'receipt', receipt }, isError: ['failed', 'partially-applied', 'uncertain'].includes(receipt.outcome) };
            const code = genericFailure(value, result.status);
            if (code)
                return failure(code, false, request);
            return failure('uncertain-result', true, request);
        }
    };
    const scenesList: ServiceExtension = {
        description: `List the ${name} controller's advertised saved scenes with their opaque IDs and Nanoleaf app names, without refreshing tasks or sending light commands.`,
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
    const extensionFailure = (code: string, possible: boolean, requestId?: unknown, message?: string) => ({ data: { kind: 'failure', code, priorEffects: possible ? 'possible' : 'none', retry: 'never-automatically', ...(requestId ? { requestId } : {}), ...(message ? { message } : {}) }, isError: true });
    const animationsList: ServiceExtension = {
        description: 'List the Nanoleaf mood presets, animation patterns, speeds, directions and limits, with the current mode, expectedRevision and requestId that nanoleaf_animation_play needs. Reads without refreshing tasks or sending light commands.',
        scope: 'read', annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: true },
        inputSchema: { type: 'object', additionalProperties: false, properties: {}, required: [] }, outputSchema: animationsOutputSchema,
        async invoke(_args, context) {
            let credential;
            try {
                credential = await store.forDispatch(context.principalId, 'read');
            }
            catch {
                return extensionFailure('forbidden', false);
            }
            let result: ExchangeResult;
            try {
                result = await transport(config, 'animations', credential.upstreamToken);
            }
            catch {
                return extensionFailure('transport-failure', false);
            }
            if (result.status === 200 && validAnimations(result.body, config))
                return { data: { kind: 'animations', animations: result.body as Record<string, unknown> } };
            return extensionFailure(genericFailure(result.body, result.status) ?? 'transport-failure', false);
        }
    };
    const restoreMessage = 'Scene restore requires an advertised remembered scene in Free. In Work or Quiet, switch to Free with nanoleaf_mode_set, then read nanoleaf_status for fresh request identity before restoring.';
    const sceneRestore: ServiceExtension = {
        description: 'Stop a Lines animation by activating the remembered scene. Free mode only; never switches mode or changes remembered brightness. Take request identity and revisions from nanoleaf_status. Queued or sent is not visible-light confirmation.',
        scope: 'control', annotations: { readOnlyHint: false, destructiveHint: true, idempotentHint: false, openWorldHint: true },
        inputSchema: { type: 'object', additionalProperties: false, $defs: schema.$defs, properties: { requestId: ref('ticket'), expectedConfigurationRevision: ref('counter'), expectedGeneration: ref('ticket') }, required: ['requestId', 'expectedConfigurationRevision', 'expectedGeneration'] },
        outputSchema: { ...outputSchema, properties: { ...outputSchema.properties, message: { type: 'string', maxLength: 512 } } },
        async invoke(args, context) {
            const listed = await animationsList.invoke({}, context);
            if (listed.isError)
                return { ...listed, data: { ...listed.data, requestId: args.requestId } };
            const options = listed.data.animations as Record<string, unknown>;
            if (options.mode !== 'Free')
                return extensionFailure('unsupported-capability', false, args.requestId, restoreMessage);
            if (options.rememberedSceneId === null)
                return extensionFailure('unsupported-capability', false, args.requestId, 'No advertised remembered scene is available to restore.');
            // Reuse activation, including its current authority check, receipt matching and no-retry policy.
            const result = await sceneActivate.invoke({ ...args, sceneId: options.rememberedSceneId }, context);
            const receipt = result.data.receipt as Receipt | undefined;
            if (result.data.code === 'unsupported-capability' || receipt?.failure?.code === 'unsupported-capability')
                return { ...result, data: { ...result.data, message: restoreMessage } };
            return result;
        }
    };
    const animationPlay: ServiceExtension = {
        description: 'Play a Nanoleaf animation on the Lines. Free mode only; the tool never switches mode itself, so switch with nanoleaf_mode_set first and take requestId and expectedRevision from nanoleaf_animations_list. Supply one favorite name, preset name, or explicit animation recipe. Direction applies to wave and gradient only. Queued or sent is not visible-light confirmation.',
        scope: 'control', annotations: { readOnlyHint: false, destructiveHint: true, idempotentHint: false, openWorldHint: true },
        inputSchema: { type: 'object', additionalProperties: false, properties: { requestId: extensionTicket, expectedRevision: { type: 'string', pattern: '^[a-f0-9]{64}$' }, preset: word, favorite: favoriteName, pattern: { enum: PATTERNS },
            colors: { type: 'array', minItems: 1, maxItems: 8, items: { type: 'string', pattern: '^#[0-9a-fA-F]{6}$' } }, speed: { enum: SPEEDS }, direction: { enum: DIRECTIONS }, loop: { type: 'boolean' } },
            required: ['requestId', 'expectedRevision'], oneOf: [{ properties: { preset: word, favorite: false, pattern: false, colors: false, speed: false, direction: false, loop: false }, required: ['preset'] }, { properties: { favorite: favoriteName, preset: false, pattern: false, colors: false, speed: false, direction: false, loop: false }, required: ['favorite'] }, { properties: { preset: false, favorite: false, pattern: { enum: PATTERNS }, colors: colorsSchema }, required: ['pattern', 'colors'] }] }, outputSchema: animationPlayOutputSchema,
        async invoke(args, context) {
            const requestId = args.requestId as { epoch: string; sequence: number };
            if ('favorite' in args && !validName(args.favorite) || 'direction' in args && !SPATIAL.includes(args.pattern as string))
                return extensionFailure('invalid-request', false, requestId);
            const command = { kind: 'animation.play', ...Object.fromEntries(['favorite', 'preset', 'pattern', 'colors', 'speed', 'direction', 'loop'].filter(key => key in args).map(key => [key, args[key]])) };
            const request = { apiVersion: EXTENSION, controllerId: config.controllerId, deviceId: config.deviceId, requestId, expectedRevision: args.expectedRevision, command };
            let credential;
            try {
                credential = await store.forDispatch(context.principalId, 'control');
            }
            catch {
                return extensionFailure('forbidden', false, requestId);
            }
            let result: ExchangeResult;
            try {
                result = await transport(config, 'extension-command', credential.upstreamToken, request);
            }
            catch (error) {
                const possible = !(error instanceof TransportFailure) || error.possible;
                return extensionFailure(possible ? 'uncertain-result' : 'transport-failure', possible, requestId);
            }
            const receipt = animationReceipt(result.body, result.status, requestId);
            if (receipt)
                return { data: { kind: 'receipt', receipt }, isError: ['failed', 'uncertain', 'cancelled'].includes(receipt.outcome as string) };
            const code = genericFailure(result.body, result.status);
            if (code)
                return extensionFailure(code, false, requestId, code === 'unsupported-capability' ? FREE_FIRST : undefined);
            return extensionFailure('uncertain-result', true, requestId);
        }
    };
    function favoriteEdit(kind: 'save' | 'rename' | 'forget'): ServiceExtension {
        const fields = kind === 'save' ? ['name', 'animation'] : kind === 'rename' ? ['name', 'newName'] : ['name'];
        const properties: Record<string, object> = kind === 'save' ? { name: favoriteName, animation: recipeSchema } : kind === 'rename' ? { name: favoriteName, newName: favoriteName } : { name: favoriteName };
        return {
            description: kind === 'save' ? 'Save supplied animation fields or a preset as a new private favorite; defaults are frozen. Existing names are never overwritten. Works in every mode and never plays lights. Use the ticket and revision from nanoleaf_animations_list.'
                : kind === 'rename' ? 'Atomically rename a private animation favorite. An occupied target is rejected without changing either recipe. Works in every mode; use a fresh animation-list ticket and revision.'
                : 'Delete an existing private animation favorite. Works in every mode without stopping or changing a playing animation. Use a fresh animation-list ticket and revision.',
            scope: 'control', annotations: { readOnlyHint: false, destructiveHint: true, idempotentHint: false, openWorldHint: true },
            inputSchema: { type: 'object', additionalProperties: false, properties: { requestId: extensionTicket, expectedRevision: { type: 'string', pattern: '^[a-f0-9]{64}$' }, ...properties }, required: ['requestId', 'expectedRevision', ...fields] },
            outputSchema: configurationOutputSchema,
            async invoke(args, context) {
                const requestId = args.requestId as { epoch: string; sequence: number };
                if (!validName(args.name) || kind === 'rename' && !validName(args.newName) || kind === 'save' && !validRecipe(args.animation))
                    return extensionFailure('invalid-request', false, requestId);
                const command = { kind: `animation.${kind}`, ...Object.fromEntries(fields.map(key => [key, args[key]])) };
                const request = { apiVersion: EXTENSION, controllerId: config.controllerId, deviceId: config.deviceId, requestId, expectedRevision: args.expectedRevision, command };
                let credential;
                try { credential = await store.forDispatch(context.principalId, 'control'); }
                catch { return extensionFailure('forbidden', false, requestId); }
                let result: ExchangeResult;
                try { result = await transport(config, 'extension-command', credential.upstreamToken, request); }
                catch (error) {
                    const possible = !(error instanceof TransportFailure) || error.possible;
                    return extensionFailure(possible ? 'uncertain-result' : 'transport-failure', possible, requestId);
                }
                const receipt = animationReceipt(result.body, result.status, requestId, true);
                if (receipt) return { data: { kind: 'receipt', receipt }, isError: ['failed', 'cancelled'].includes(receipt.outcome as string) };
                const code = genericFailure(result.body, result.status);
                return extensionFailure(code ?? 'uncertain-result', !code, requestId);
            }
        };
    }
    return { status: extension(false), mode: extension(true), scenes: scenesList, sceneActivate, animations: animationsList, animationPlay, sceneRestore, animationSave: favoriteEdit('save'), animationRename: favoriteEdit('rename'), animationForget: favoriteEdit('forget') };
}
export function bindings(config: Config, store: Pick<CredentialStore, 'forDispatch'>, transport: Transport = exchange) {
    // Without a Panels target the descriptions stay exactly as before; with one they name each device.
    const lines = extensions(config, store, transport, config.panelsDeviceId ? 'Nanoleaf Lines' : 'Nanoleaf');
    const registrations = [{ controllerId: config.controllerId, deviceId: config.deviceId, extensions: lines }];
    const panelsDeviceId = config.panelsDeviceId;
    if (panelsDeviceId) {
        // A second fixed target; animations stay Lines-only (#113).
        const { status, mode, scenes, sceneActivate } = extensions({ ...config, deviceId: panelsDeviceId }, store, transport, 'Nanoleaf Light Panels');
        registrations.push({ controllerId: config.controllerId, deviceId: panelsDeviceId, extensions: { status, mode, scenes, sceneActivate } as typeof lines });
    }
    const registry = createDeviceRegistry(registrations);
    const tools = [...bindServiceTools(registry, { deviceId: config.deviceId, bindings: [{ extension: 'status', name: 'nanoleaf_status' }, { extension: 'mode', name: 'nanoleaf_mode_set' }, { extension: 'scenes', name: 'nanoleaf_scenes_list' }, { extension: 'sceneActivate', name: 'nanoleaf_scene_activate' }, { extension: 'animations', name: 'nanoleaf_animations_list' }, { extension: 'animationPlay', name: 'nanoleaf_animation_play' }, { extension: 'sceneRestore', name: 'nanoleaf_scene_restore' }, { extension: 'animationSave', name: 'nanoleaf_animation_save' }, { extension: 'animationRename', name: 'nanoleaf_animation_rename' }, { extension: 'animationForget', name: 'nanoleaf_animation_forget' }] })];
    if (panelsDeviceId)
        tools.push(...bindServiceTools(registry, { deviceId: panelsDeviceId, bindings: [{ extension: 'status', name: 'nanoleaf_panels_status' }, { extension: 'mode', name: 'nanoleaf_panels_mode_set' }, { extension: 'scenes', name: 'nanoleaf_panels_scenes_list' }, { extension: 'sceneActivate', name: 'nanoleaf_panels_scene_activate' }] }));
    return { registry, tools };
}
