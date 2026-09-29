"""Private coordination for explicitly launched disposable paired verification runs."""
import contextlib
import json
import os
from pathlib import Path
import re
import secrets
import stat


class PauseError(ValueError):
    """A fixed diagnostic that never includes paths or control contents."""


def read_control(runtime, kind):
    """None means absent. Unsafe, oversized or malformed files fail closed."""
    path = runtime / f'feed-pause.{kind}'
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        # A dangling symlink is an invalid control, not absence.
        if path.is_symlink():
            raise PauseError('Invalid feed pause control.') from None
        return None
    except OSError:
        raise PauseError('Invalid feed pause control.') from None
    try:
        with os.fdopen(descriptor, 'rb') as stream:
            info = os.fstat(stream.fileno())
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or
                    info.st_mode & 0o077 or info.st_nlink != 1 or info.st_size > 4096):
                raise ValueError()
            raw = stream.read(4097)
        if len(raw) > 4096:
            raise ValueError()
        value = json.loads(raw)
        keys = {'version', 'runId', 'nonce'} | ({'pid'} if kind == 'ack' else set())
        if (not isinstance(value, dict) or set(value) != keys or type(value['version']) is not int or
                value['version'] != 1 or not isinstance(value['runId'], str) or
                not re.fullmatch(r'[A-Za-z0-9_-]{1,120}', value['runId']) or
                not isinstance(value['nonce'], str) or not re.fullmatch(r'[0-9a-f]{32}', value['nonce']) or
                (kind == 'ack' and (type(value['pid']) is not int or value['pid'] <= 0))):
            raise ValueError()
        return value
    except (OSError, ValueError, UnicodeError):
        raise PauseError('Invalid feed pause control.') from None


class FeedPause:
    def __init__(self, data, runtime, run_id):
        self.runtime = Path(runtime)
        self.run_id = run_id
        try:
            info = self.runtime.lstat()
            if (not self.runtime.is_absolute() or not stat.S_ISDIR(info.st_mode) or
                    info.st_uid != os.getuid() or info.st_mode & 0o077 or
                    self.runtime.resolve() != self.runtime or
                    Path(data).resolve().parent != self.runtime or self.runtime.name != run_id or
                    not re.fullmatch(r'[A-Za-z0-9_-]{1,120}', run_id)):
                raise ValueError()
        except (OSError, ValueError, TypeError):
            raise PauseError('Invalid feed pause run context.') from None

    def request(self):
        value = read_control(self.runtime, 'request')
        if value is not None and value['runId'] != self.run_id:
            raise PauseError('Invalid feed pause run identity.')
        return value

    def blocked(self):
        """Called only by the serialized writer, before/after its fully drained poll."""
        try:
            request = self.request()
            if request is None:
                with contextlib.suppress(OSError):
                    (self.runtime / 'feed-pause.ack').unlink()
                return False
            expected = dict(request, pid=os.getpid())
            try:
                if read_control(self.runtime, 'ack') == expected:
                    return True
            except PauseError:
                pass
            temporary = self.runtime / f'.feed-pause-{secrets.token_hex(8)}'
            try:
                with os.fdopen(os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as stream:
                    json.dump(expected, stream)
                    stream.flush()
                    os.fsync(stream.fileno())
                if self.request() == request:
                    os.replace(temporary, self.runtime / 'feed-pause.ack')
            finally:
                with contextlib.suppress(OSError):
                    temporary.unlink()
        except (PauseError, OSError):
            # Invalid controls or a failed ack keep admission closed. The coordinator times out.
            pass
        return True

    def seed_release(self, paired):
        request = self.request()
        release = read_control(self.runtime, 'release')
        if request is None and release is None:
            return None
        if request is None or not paired or release != request:
            raise PauseError('Feed pause needs matching paired reseed authorization.')
        return request

    def consume_release(self, request):
        if request is None:
            return
        if self.request() != request or read_control(self.runtime, 'release') != request:
            raise PauseError('Feed pause authorization changed during seed.')
        # The core has stopped the old unit. Request is removed last, after successful seed.
        for kind in ('release', 'ack', 'request'):
            try:
                (self.runtime / f'feed-pause.{kind}').unlink()
            except FileNotFoundError:
                if kind != 'ack':
                    raise PauseError('Feed pause authorization changed during seed.') from None
