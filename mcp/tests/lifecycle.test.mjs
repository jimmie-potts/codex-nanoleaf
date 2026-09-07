import test from 'node:test';
import assert from 'node:assert/strict';
import { startHost } from '../dist/server.js';
test('disabled source configuration refuses to start a listener',async()=>{await assert.rejects(startHost({enabled:false}),/disabled/);});
