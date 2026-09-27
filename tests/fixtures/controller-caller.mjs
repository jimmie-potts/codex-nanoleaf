// #194: a stand-in for the Hub's controller client. It presents the Hub's controller token to a
// paired wall run's controller endpoint as the Hub does, for the hub-paired tests and the delivery
// evidence procedure (docs/development.md, Hub-paired runs).
//
//   node tests/fixtures/controller-caller.mjs <controller endpoint> <controller token file> <wall url>
//
// makes the Hub's reads with and without the credential, admits one integration setting, waits for
// the wall's writer to apply it and prints one JSON record. The record never holds the token.
import {readFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';

/** One request as the Hub's controller client makes it; resolves with its status and JSON body. */
export async function callController(endpoint, path, {credential, body} = {}) {
  const response = await fetch(new URL(path, endpoint), {method: body ? 'POST' : 'GET',
    headers: {...(credential ? {authorization: `Bearer ${credential}`} : {}), ...(body ? {'content-type': 'application/json'} : {})},
    ...(body ? {body: JSON.stringify(body)} : {})});
  return {status: response.status, body: await response.json()};
}

/** The Hub's calls against one paired wall: reads, one `settings.set`, and the wall's own view once it is applied. */
export async function exercise(endpoint, credential, wallUrl) {
  const record = {endpoint};
  record.withoutCredential = (await callController(endpoint, 'controller/v1/devices')).status;
  const devices = await callController(endpoint, 'controller/v1/devices', {credential});
  record.devices = {status: devices.status, identities: (devices.body.devices ?? []).map(({identity}) =>
    ({controllerId: identity.controllerId, deviceId: identity.deviceId, sourceId: identity.sourceId}))};
  record.snapshot = (await callController(endpoint, 'controller/v1/snapshot?deviceId=wall', {credential})).status;
  const extension = await callController(endpoint, 'controller/integration/v1/snapshot?deviceId=wall', {credential});
  record.integrationSnapshot = {status: extension.status, style: extension.body.settings?.style};
  const command = {apiVersion: extension.body.apiVersion, controllerId: 'wall-controller', deviceId: 'wall', requestId: extension.body.nextRequestId,
    expectedRevision: extension.body.revision, command: {kind: 'settings.set', style: extension.body.settings?.style === 'project' ? 'classic' : 'project'}};
  const admitted = await callController(endpoint, 'controller/integration/v1/commands', {credential, body: command});
  record.command = {status: admitted.status, outcome: admitted.body.outcome, style: command.command.style};
  let state;
  for (let waited = 0; waited <= 10000; waited += 200) {
    state = await (await fetch(new URL('verify/state', wallUrl))).json();
    if (state.integration.queued === 0 && state.integration.applied + state.integration.failed > 0) break;
    await new Promise(resolve => setTimeout(resolve, 200));
  }
  record.verifyState = state;
  const receipt = await callController(endpoint, `controller/integration/v1/receipt?deviceId=wall&epoch=${command.requestId.epoch}&sequence=${command.requestId.sequence}`, {credential});
  record.receipt = {status: receipt.status, outcome: receipt.body.outcome};
  record.wallStyle = (await (await fetch(new URL('api/state', wallUrl))).json()).settings.style;
  if (JSON.stringify(record).includes(credential)) throw new Error('the record would hold the token');
  return record;
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const [endpoint, tokenFile, wallUrl] = process.argv.slice(2);
  console.log(JSON.stringify(await exercise(endpoint, readFileSync(tokenFile, 'utf8').trim(), wallUrl), null, 2));
}
