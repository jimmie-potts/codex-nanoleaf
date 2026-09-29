import {constants} from 'node:fs';
import {open} from 'node:fs/promises';
import {basename, join} from 'node:path';

async function control(runtimeDir, runId, kind) {
  let file;
  try {
    file = await open(join(runtimeDir, `feed-pause.${kind}`), constants.O_RDONLY | constants.O_NOFOLLOW | constants.O_NONBLOCK);
    const info = await file.stat();
    if (!info.isFile() || info.uid !== process.getuid() || info.mode & 0o077 || info.nlink !== 1 || info.size > 4096) throw new Error();
    const bytes = Buffer.alloc(4097);
    let used = 0;
    while (used < bytes.length) {
      const {bytesRead} = await file.read(bytes, used, bytes.length - used, null);
      if (!bytesRead) break;
      used += bytesRead;
    }
    if (used > 4096) throw new Error();
    const value = JSON.parse(new TextDecoder('utf-8', {fatal: true}).decode(bytes.subarray(0, used)));
    if (!value || Object.keys(value).sort().join(',') !== 'nonce,runId,version' || value.version !== 1 ||
        value.runId !== runId || !/^[A-Za-z0-9_-]{1,120}$/.test(value.runId) ||
        typeof value.nonce !== 'string' || !/^[0-9a-f]{32}$/.test(value.nonce)) throw new Error();
    return {value};
  } catch (error) {
    if (error.code === 'ENOENT') return undefined;
    return {outcome: 'failed', reason: `feed-pause.${kind} is invalid for this run`};
  } finally {
    await file?.close();
  }
}

/** A diagnostic never probes Hub when pause inputs are present or invalid. */
export async function feedPauseCheck(runtimeDir, runId = basename(runtimeDir)) {
  const request = await control(runtimeDir, runId, 'request');
  if (request?.outcome) return request;
  const release = await control(runtimeDir, runId, 'release');
  if (release?.outcome) return release;
  if (release && (!request || release.value.nonce !== request.value.nonce)) {
    return {outcome: 'failed', reason: 'feed-pause.release is invalid for this run'};
  }
  return request ? {outcome: 'skipped', reason: 'the Hub feed is paused for aggregate reset'} : undefined;
}
