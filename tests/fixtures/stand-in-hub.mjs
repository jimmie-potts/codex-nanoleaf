// #194: a stand-in for a paired Hub run's monitor feed, for the hub-paired tests and the delivery
// evidence procedure (docs/development.md, Hub-paired runs). It serves the one route the wall reads,
// GET /api/monitor/v1/sessions?snapshotVersion=1.2, with tests/fixtures/paired-hub-feed.json's
// envelope, and answers only the wall's feed token with `X-Pixoo-Request: 1`. It binds 127.0.0.1 on
// a kernel-chosen port that no installed service uses. It reads no Hub state and contacts nothing.
//
//   node tests/fixtures/stand-in-hub.mjs <feed token file> [<request log>]
//
// prints {"origin": "http://127.0.0.1:<port>/"} once listening and serves until SIGTERM.
import {appendFileSync, readFileSync} from 'node:fs';
import {createServer} from 'node:http';
import {join} from 'node:path';
import {fileURLToPath} from 'node:url';

const ROOT = fileURLToPath(new URL('../..', import.meta.url));
export const FEED = JSON.parse(readFileSync(join(ROOT, 'tests/fixtures/paired-hub-feed.json'), 'utf8'));
const INSTALLED_PORTS = new Set([8788, 8765, 8787, 8791, 41230, 41231]);

/**
 * Start a stand-in Hub feed. `envelope` and `status` may be changed while it serves; `requests`
 * counts every request and `log`, when given, receives one JSON line per request without its header values.
 */
export async function standInHub(feedToken, {log} = {}) {
  const hub = {envelope: structuredClone(FEED.envelope), status: 200, requests: 0};
  const server = createServer((request, response) => {
    hub.requests++;
    const ok = request.method === 'GET' && request.url === '/api/monitor/v1/sessions?snapshotVersion=1.2'
      && request.headers.authorization === `Bearer ${feedToken}` && request.headers['x-pixoo-request'] === '1';
    const status = ok ? hub.status : 401;
    if (log) appendFileSync(log, JSON.stringify({at: new Date().toISOString(), method: request.method, url: request.url, status}) + '\n');
    const body = JSON.stringify(status === 200 ? hub.envelope : {error: 'rejected'});
    response.writeHead(status, {'content-type': 'application/json', 'content-length': Buffer.byteLength(body)});
    response.end(body);
  });
  // The kernel could hand out an installed service's port while that service is down; the wall refuses one.
  do {
    await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
    if (INSTALLED_PORTS.has(server.address().port)) await new Promise(resolve => server.close(resolve));
  } while (!server.listening);
  hub.port = server.address().port;
  hub.origin = `http://127.0.0.1:${hub.port}/`;
  hub.close = () => new Promise(resolve => {server.close(resolve); server.closeAllConnections()});
  return hub;
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const [tokenFile, log] = process.argv.slice(2);
  const hub = await standInHub(readFileSync(tokenFile, 'utf8').trim(), {log});
  process.on('SIGTERM', async () => {await hub.close(); process.exit(0)});
  console.log(JSON.stringify({origin: hub.origin}));
}
