/** Native-client contract only. This module never sends or retries a request. */
export const apiVersion = 'nanoleaf.integration/1.0';
export type Ticket = {epoch: string; sequence: number};
export const patterns = {wave: true, gradient: true, pulse: false, breathe: false, sparkle: false} as const;
export type Pattern = keyof typeof patterns;
export type Animation = {kind: 'animation.play'; pattern: Pattern; colors: string[]; speed?: 'slow' | 'medium' | 'fast';
  direction?: 'left' | 'right' | 'up' | 'down' | 'outward' | 'inward'; loop?: boolean};
export type Command =
  | {kind: 'settings.set'; style?: 'classic' | 'project'; coverage?: 'whole' | 'status'}
  | {kind: 'elements.assign'; elements: {id: string; projectId?: string | null; signature?: 0 | 1}[]}
  | {kind: 'task.assign'; taskId: string; projectId: string | null}
  | {kind: 'project.color'; projectId: string; color: string}
  | Animation;
export type Request = {apiVersion: typeof apiVersion; controllerId: string; deviceId: string;
  requestId: Ticket; expectedRevision: string; command: Command};
export type Receipt = {apiVersion: typeof apiVersion; requestId: Ticket;
  outcome: 'queued' | 'applied' | 'failed' | 'cancelled'; priorEffects: 'none' | 'configuration';
  physicalOutcome: 'unknown'; failure?: {code: string}};
/** An animation.play receipt: transport evidence only, never visible output. */
export type AnimationReceipt = {apiVersion: typeof apiVersion; requestId: Ticket;
  outcome: 'queued' | 'sent' | 'failed' | 'uncertain' | 'cancelled'; priorEffects: 'none' | 'confirmed-transmission' | 'possible';
  physicalOutcome: 'unknown'; failure?: {code: string}};

const object = (v: unknown): v is Record<string, any> => v !== null && typeof v === 'object' && !Array.isArray(v);
const exact = (v: Record<string, any>, keys: string[]) => Object.keys(v).sort().join(',') === keys.sort().join(',');
const match = (v: unknown, regex: RegExp) => typeof v === 'string' && !/[\r\n]/.test(v) && regex.test(v);
const ref = (v: unknown, kind: string, nullable = false) => nullable && v === null || match(v, new RegExp('^' + kind + '-[a-f0-9]{64}$'));
export const ticket = (v: unknown): v is Ticket => object(v) && exact(v, ['epoch', 'sequence']) && match(v.epoch, /^[a-f0-9]{32}$/) && Number.isSafeInteger(v.sequence) && v.sequence >= 0;

export function validateRequest(v: unknown): v is Request {
  if (!object(v) || !exact(v, ['apiVersion','controllerId','deviceId','requestId','expectedRevision','command']) || v.apiVersion !== apiVersion || !ticket(v.requestId)
      || !match(v.controllerId, /^[A-Za-z0-9_.-]{1,128}$/) || !match(v.deviceId, /^[A-Za-z0-9_.-]{1,128}$/)
      || !match(v.expectedRevision, /^[a-f0-9]{64}$/) || !object(v.command)) return false;
  const c = v.command;
  switch (c.kind) {
    case 'settings.set':
      return Object.keys(c).length >= 2 && Object.keys(c).every(k => ['kind','style','coverage'].includes(k))
        && (!('style' in c) || ['classic','project'].includes(c.style)) && (!('coverage' in c) || ['whole','status'].includes(c.coverage));
    case 'elements.assign': {
      if (!exact(c, ['kind','elements']) || !Array.isArray(c.elements) || c.elements.length < 1 || c.elements.length > 300) return false;
      const seen = new Set();
      return c.elements.every(e => {
        if (!object(e) || Object.keys(e).length < 2 || !Object.keys(e).every(k => ['id','projectId','signature'].includes(k)) || !match(e.id, /^[0-9]{1,5}:[0-9]{1,5}$/) || seen.has(e.id)
          || 'projectId' in e && !ref(e.projectId, 'project', true) || 'signature' in e && ![0,1].includes(e.signature)) return false;
        seen.add(e.id); return true;
      });
    }
    case 'task.assign': return exact(c, ['kind','taskId','projectId']) && ref(c.taskId, 'task') && ref(c.projectId, 'project', true);
    case 'project.color': return exact(c, ['kind','projectId','color']) && ref(c.projectId, 'project') && match(c.color, /^#[a-fA-F0-9]{6}$/);
    case 'animation.play': {
      const keys = Object.keys(c);
      if (!['kind','pattern','colors'].every(k => keys.includes(k)) || !keys.every(k => ['kind','pattern','colors','speed','direction','loop'].includes(k))
          || typeof c.pattern !== 'string' || !Object.hasOwn(patterns, c.pattern)
          || !Array.isArray(c.colors) || c.colors.length < 1 || c.colors.length > 8 || !c.colors.every((v: unknown) => match(v, /^#[a-fA-F0-9]{6}$/))) return false;
      return (!('speed' in c) || ['slow','medium','fast'].includes(c.speed))
        && (!('direction' in c) || patterns[c.pattern as Pattern] && ['left','right','up','down','outward','inward'].includes(c.direction))
        && (!('loop' in c) || typeof c.loop === 'boolean');
    }
    default: return false;
  }
}

/** Read-only element geometry from `GET /geometry`, in the wall map's display coordinates. */
export type Point = [number, number];
export type Geometry = {apiVersion: typeof apiVersion;
  identity: {controllerId: string; deviceId: string; sourceId: string; controllerEpoch: string};
  kind: 'lines' | 'panels' | null;
  elements: {id: string; number: number; zones: number[]; points: Point[] | null}[];
  connectors: {nodes: {id: string; x: number; y: number}[]; lines: {id: string; a: string; b: string}[]} | null};

const neutral = (v: unknown) => match(v, /^[A-Za-z0-9_.-]{1,128}$/);
const point = (v: unknown) => Array.isArray(v) && v.length === 2 && v.every(n => typeof n === 'number' && Number.isFinite(n));
const zone = (v: unknown) => Number.isInteger(v) && (v as number) >= 0 && (v as number) <= 65535;

export function validateGeometry(v: unknown): v is Geometry {
  if (!object(v) || !exact(v, ['apiVersion','identity','kind','elements','connectors']) || v.apiVersion !== apiVersion
      || !object(v.identity) || !exact(v.identity, ['controllerId','deviceId','sourceId','controllerEpoch'])
      || !Object.values(v.identity).every(neutral) || ![null,'lines','panels'].includes(v.kind)
      || !Array.isArray(v.elements) || v.elements.length > 300) return false;
  // Lines have two zones per element and Panels one; a device without a saved layout has neither.
  const perElement = v.kind === 'lines' ? 2 : 1, drawn = v.elements[0]?.points !== null, seen = new Set();
  if (v.kind === null && (v.elements.length > 0 || v.connectors !== null)) return false;
  const elements = v.elements.every((e: unknown, index: number) => {
    if (!object(e) || !exact(e, ['id','number','zones','points']) || e.number !== index + 1
        || !Array.isArray(e.zones) || e.zones.length !== perElement || !e.zones.every(zone) || new Set(e.zones).size !== perElement
        || e.id !== [...e.zones].sort((a, b) => a - b).join(':') || seen.has(e.id)
        || (e.points === null) === drawn || e.points !== null && !(Array.isArray(e.points) && e.points.length === 3 && e.points.every(point))) return false;
    seen.add(e.id); return true;
  });
  if (!elements) return false;
  if (v.connectors === null) return true;
  const c = v.connectors;
  if (v.kind !== 'lines' || !object(c) || !exact(c, ['nodes','lines']) || !Array.isArray(c.nodes) || c.nodes.length < 1 || c.nodes.length > 600
      || !Array.isArray(c.lines) || c.lines.length !== v.elements.length) return false;
  const nodes = new Set();
  for (const n of c.nodes) {
    if (!object(n) || !exact(n, ['id','x','y']) || !match(n.id, /^[0-9]{1,5}$/) || nodes.has(n.id) || !point([n.x, n.y])) return false;
    nodes.add(n.id);
  }
  return c.lines.every((l: unknown, index: number) => object(l) && exact(l, ['id','a','b']) && l.id === v.elements[index].id
    && nodes.has(l.a) && nodes.has(l.b) && l.a !== l.b);
}

export function animationResult(receipt: AnimationReceipt): 'pending' | 'sent' | 'uncertain' | 'refresh' | 'stopped' {
  // Sent is transport evidence only. Uncertain may have reached the device and is
  // never retried automatically; look up the original ticket instead.
  switch (receipt.outcome) {
    case 'queued': return 'pending';
    case 'sent': return 'sent';
    case 'uncertain': return 'uncertain';
    case 'failed': return 'refresh';
    case 'cancelled': return 'stopped';
  }
}

export function configurationResult(receipt: Receipt): 'pending' | 'saved' | 'refresh' | 'stopped' {
  // A saved configuration never establishes physical delivery. A lost response
  // requires receipt lookup using the original ticket, never a fresh write.
  switch (receipt.outcome) {
    case 'queued': return 'pending';
    case 'applied': return 'saved';
    case 'failed': return 'refresh';
    case 'cancelled': return 'stopped';
  }
}
