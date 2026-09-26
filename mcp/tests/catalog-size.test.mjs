import test from 'node:test';
import assert from 'node:assert/strict';
import { bindings } from '../dist/tools.js';

// Reserve at least half of the gateway's 1 MiB response allowance
// for future tools and protocol overhead, including the optional Panels tools.
for (const panelsDeviceId of [undefined, 'panels']) {
    test(`published ${panelsDeviceId ? 'Lines and Panels' : 'Lines'} catalog retains room for new tools`, () => {
        const { tools } = bindings(
            { controllerId: 'controller', deviceId: 'lines', ...(panelsDeviceId ? { panelsDeviceId } : {}) },
            { forDispatch: async () => { throw new Error('Discovery must not dispatch'); } },
        );
        const bytes = Buffer.byteLength(JSON.stringify({ jsonrpc: '2.0', id: 1, result: { tools } }));
        assert.ok(bytes < 512 * 1024, `Published catalog uses ${bytes} bytes; expected below 512 KiB`);
    });
}
