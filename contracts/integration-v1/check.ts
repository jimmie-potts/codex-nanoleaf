import {readFileSync} from 'node:fs';
import {validateRequest, configurationResult, animationResult, validateGeometry} from './consumer.ts';
import type {Receipt, AnimationReceipt} from './consumer.ts';
const fixture = JSON.parse(readFileSync(new URL('./fixtures.json', import.meta.url), 'utf8'));
for (const entry of fixture.requests) {
  if (validateRequest(entry.request) !== entry.valid) throw new Error(entry.name);
}
for (const entry of fixture.receipts) {
  if (configurationResult(entry.receipt as Receipt) !== entry.result) throw new Error(entry.name);
}
for (const entry of fixture.animationReceipts) {
  if (animationResult(entry.receipt as AnimationReceipt) !== entry.result) throw new Error(entry.name);
}
for (const entry of fixture.geometry) {
  if (validateGeometry(entry.geometry) !== entry.valid) throw new Error(entry.name);
}
// Optional: a JSON array of actual route outputs that must all validate.
const outputs = process.argv[2] ? JSON.parse(readFileSync(process.argv[2], 'utf8')) : [];
outputs.forEach((output: unknown, index: number) => { if (!validateGeometry(output)) throw new Error('geometry output ' + index); });
console.log(JSON.stringify({requests: fixture.requests.length, receipts: fixture.receipts.length, animationReceipts: fixture.animationReceipts.length,
  geometry: fixture.geometry.length, geometryOutputs: outputs.length}));
