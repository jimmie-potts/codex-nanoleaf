import {constants} from 'node:fs';
import {open} from 'node:fs/promises';
import {basename, join} from 'node:path';

/** A diagnostic never initiates its own Hub read while the serving process is paused. */
export async function feedPauseCheck(runtimeDir, runId = basename(runtimeDir)) {
  let file;
  try {
    file = await open(join(runtimeDir, 'feed-pause.request'), constants.O_RDONLY | constants.O_NOFOLLOW | constants.O_NONBLOCK);
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
    return {outcome: 'skipped', reason: 'the Hub feed is paused for aggregate reset'};
  } catch (error) {
    if (error.code === 'ENOENT') return undefined;
    return {outcome: 'failed', reason: 'feed-pause.request is invalid for this run'};
  } finally {
    await file?.close();
  }
}
