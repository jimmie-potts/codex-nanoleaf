import {readFileSync} from 'node:fs';
import {validateRequest, configurationResult} from './consumer.ts';
import type {Receipt} from './consumer.ts';
const fixture = JSON.parse(readFileSync(new URL('./fixtures.json', import.meta.url), 'utf8'));
for (const entry of fixture.requests) {
  if (validateRequest(entry.request) !== entry.valid) throw new Error(entry.name);
}
for (const entry of fixture.receipts) {
  if (configurationResult(entry.receipt as Receipt) !== entry.result) throw new Error(entry.name);
}
console.log(JSON.stringify({requests: fixture.requests.length, receipts: fixture.receipts.length}));
