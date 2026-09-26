"""This integration's handlers in a Codex hooks.json, changed without disturbing anyone else's.

Codex trusts a hook by its event, group and handler position, so registration and removal keep
every unrelated byte in place: a span-preserving JSON parser locates the values to change.
"""
import argparse
import json
import os
from pathlib import Path
import shlex
import sys
import tempfile
import time

import configuration
import launcher
import shared_input

EVENTS = ('UserPromptSubmit', 'PreToolUse', 'PermissionRequest',
          'PostToolUse', 'Stop', 'Interrupt', 'SessionEnd')
MARKER = 'nanoleaf-codex-status-v1'


def hook_command(script, state_dir=None):
    state_args = ['--state-dir', str(state_dir)] if state_dir is not None else []
    return shlex.join([sys.executable, str(script), 'hook', *state_args])


def merge_hooks(original, command, remove=False):
    result = json.loads(json.dumps(original))
    hooks = result.setdefault('hooks', {})
    for name in EVENTS:
        groups = hooks.get(name, [])
        # Remove only handlers belonging to this integration, keeping others intact.
        clean = []
        for group in groups:
            item = dict(group)
            item['hooks'] = [h for h in group.get('hooks', [])
                             if h.get('statusMessage') != MARKER]
            if item['hooks']:
                clean.append(item)
        if not remove:
            handler = {'type': 'command', 'command': command,
                       'timeout': 3 if name in ('SessionEnd', 'Interrupt') else 5,
                       'statusMessage': MARKER}
            clean.append({'hooks': [handler]})
        if clean:
            hooks[name] = clean
        else:
            hooks.pop(name, None)
    return result


def parse_hooks_json(raw):
    """Validate current files and backups with the same unambiguous structure."""
    original = json.loads(raw.decode('utf-8-sig')) if raw is not None else {}
    if raw is not None:
        json_spans(raw.decode('utf-8-sig'))
    if type(original) is not dict or type(original.get('hooks', {})) is not dict:
        raise ValueError('invalid hooks.json structure')
    hooks = original.get('hooks', {})
    if any(type(groups) is not list or any(type(group) is not dict
           or type(group.get('hooks', [])) is not list
           or any(type(handler) is not dict for handler in group.get('hooks', []))
           for group in groups) for groups in hooks.values()):
        raise ValueError('invalid hooks.json structure')
    return original


def manage_hooks(codex_home, operation, script, state_dir=None):
    """Change this integration's hooks in one explicitly selected Codex home."""
    if operation not in ('remove', 'register'):
        raise ValueError('invalid hook operation')
    codex_home = Path(codex_home)
    hooks_file = codex_home / 'hooks.json'
    original_bytes = hooks_file.read_bytes() if hooks_file.exists() else None
    original = parse_hooks_json(original_bytes)
    command = hook_command(Path(script), state_dir=state_dir)
    saved = original if has_legacy_hooks_value(original) else None
    saved_bytes = original_bytes if saved is not None else None
    if operation == 'register' and saved is None:
        for candidate in sorted(codex_home.glob('hooks.nanoleaf-backup-*.json'), reverse=True):
            try:
                candidate_bytes = candidate.read_bytes()
                value = parse_hooks_json(candidate_bytes)
            except (OSError, ValueError, UnicodeError):
                continue
            if type(value) is dict and has_legacy_hooks_value(value):
                saved = value
                saved_bytes = candidate_bytes
                break
    if operation == 'remove':
        if not has_legacy_hooks_value(original):
            return False
        rendered = remove_marked_hooks_json(original_bytes)
    else:
        fresh = merge_hooks({}, command)
        groups_by_event = marked_groups(fresh)
        if saved is not None:
            groups_by_event.update(marked_groups(saved))
        # Hook trust is indexed by event/group/handler position. Existing handlers
        # must stay in place, including marked handlers inside mixed groups.
        rendered = original_bytes if original_bytes is not None else b'{}'
        if saved_bytes is not None and remove_marked_hooks_json(saved_bytes) == rendered:
            # Undo our own removal byte for byte only if nothing else changed.
            rendered = saved_bytes
        present = marked_groups(parse_hooks_json(rendered))
        for event, groups in groups_by_event.items():
            if event not in present:
                rendered = append_hook_groups_json(rendered, event, groups)
        # Re-registering an already-correct configuration must not rewrite bytes.
    if isinstance(rendered, str):
        bom = b'\xef\xbb\xbf' if original_bytes is not None and original_bytes.startswith(b'\xef\xbb\xbf') else b''
        rendered = bom + rendered.encode('utf-8')
    if original_bytes is not None and json.loads(rendered.decode('utf-8-sig')) == original:
        return False
    codex_home.mkdir(parents=True, exist_ok=True)
    if original_bytes is not None:
        backup = hooks_file.with_name('hooks.nanoleaf-backup-' + str(time.time_ns()) + '.json')
        descriptor = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, 'wb') as backup_file:
            backup_file.write(original_bytes)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=codex_home, prefix='.hooks-', suffix='.tmp', delete=False) as output:
            temporary = Path(output.name)
            output.write(rendered)
        temporary.replace(hooks_file)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return True


def command(argv):
    """`bridge.py hooks register|remove`: the hooks run this installation's bridge.py."""
    parser = argparse.ArgumentParser(description='Manage Nanoleaf hooks in one Codex home.')
    parser.add_argument('operation', choices=('remove', 'register'))
    parser.add_argument('--codex-home', type=Path, required=True)
    parser.add_argument('--state-dir', type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    directory = args.state_dir or configuration.data_dir()
    if args.operation == 'remove':
        if shared_input.inspect(directory)['source'] != 'shared':
            parser.error('Cannot remove legacy hooks while legacy input is selected.')
    try:
        changed = manage_hooks(args.codex_home, args.operation, launcher.SCRIPT, state_dir=directory)
    except (OSError, ValueError, UnicodeError, json.JSONDecodeError):
        parser.error('Cannot update hooks.json; it is malformed or unavailable, and no changes were made.')
    print(('Updated' if changed else 'Already current') + ' Nanoleaf hooks in ' + str(args.codex_home / 'hooks.json'))
    print('Restart Codex to reload hook configuration.')
    print('Review required hooks marked new or modified after reload, including retained shared hooks.')


def has_legacy_hooks(codex_home):
    """Legacy input needs marked handlers for every lifecycle event."""
    hooks_file = Path(codex_home) / 'hooks.json'
    try:
        text = hooks_file.read_text(encoding='utf-8-sig')
        value = json.loads(text)
        json_spans(text)
        hooks = value.get('hooks', {}) if type(value) is dict else {}
        return type(hooks) is dict and all(
            has_legacy_hooks_value({'hooks': {event: hooks.get(event)}}) for event in EVENTS)
    except (OSError, ValueError, UnicodeError):
        return False


def has_legacy_hooks_value(value):
    hooks = value.get('hooks', {}) if type(value) is dict else {}
    return type(hooks) is dict and any(
        type(groups) is list and any(type(group) is dict and type(group.get('hooks', [])) is list
        and any(type(handler) is dict and handler.get('statusMessage') == MARKER
                for handler in group.get('hooks', [])) for group in groups)
        for name, groups in hooks.items() if name in EVENTS)


def marked_groups(value):
    hooks = value.get('hooks', {}) if type(value) is dict else {}
    result = {}
    if type(hooks) is not dict:
        return result
    for event in EVENTS:
        groups = hooks.get(event, [])
        if type(groups) is not list:
            continue
        selected = []
        for group in groups:
            if type(group) is not dict or type(group.get('hooks', [])) is not list:
                continue
            marked = [handler for handler in group['hooks']
                      if type(handler) is dict and handler.get('statusMessage') == MARKER]
            if marked:
                selected.append({**group, 'hooks': marked})
        if selected:
            result[event] = selected
    return result


def json_spans(text):
    """Parse JSON while retaining value and property byte-span boundaries."""
    def whitespace(index):
        while index < len(text) and text[index] in ' \t\r\n':
            index += 1
        return index

    def parse(index):
        index = whitespace(index)
        start = index
        char = text[index]
        if char == '{':
            index = whitespace(index + 1)
            members = []
            if text[index] == '}':
                return ('object', start, index + 1, members), index + 1
            while True:
                key_start = index
                key_node, index = parse(index)
                if key_node[0] != 'string':
                    raise ValueError('invalid JSON object key')
                key = json.loads(text[key_node[1]:key_node[2]])
                if any(member[0] == key for member in members):
                    raise ValueError('duplicate JSON object key')
                index = whitespace(index)
                if text[index] != ':':
                    raise ValueError('invalid JSON object')
                value_node, index = parse(index + 1)
                members.append((key, key_start, key_node[2], value_node))
                index = whitespace(index)
                if text[index] == '}':
                    return ('object', start, index + 1, members), index + 1
                if text[index] != ',':
                    raise ValueError('invalid JSON object')
                index = whitespace(index + 1)
        if char == '[':
            index = whitespace(index + 1)
            values = []
            if text[index] == ']':
                return ('array', start, index + 1, values), index + 1
            while True:
                value_node, index = parse(index)
                values.append(value_node)
                index = whitespace(index)
                if text[index] == ']':
                    return ('array', start, index + 1, values), index + 1
                if text[index] != ',':
                    raise ValueError('invalid JSON array')
                index = whitespace(index + 1)
        if char == '"':
            index += 1
            escaped = False
            while index < len(text):
                current = text[index]
                index += 1
                if escaped:
                    escaped = False
                elif current == '\\':
                    escaped = True
                elif current == '"':
                    return ('string', start, index, None), index
            raise ValueError('invalid JSON string')
        while index < len(text) and text[index] not in ',]} \t\r\n':
            index += 1
        json.loads(text[start:index])
        return ('value', start, index, None), index

    node, end = parse(0)
    if whitespace(end) != len(text):
        raise ValueError('trailing JSON data')
    return node


def json_member(node, key):
    if node[0] != 'object':
        return None
    return next((member for member in node[3] if member[0] == key), None)


def remove_marked_hooks_json(raw):
    """Remove marked handlers while retaining every unrelated JSON value verbatim."""
    if raw is None:
        return b'{}'
    bom = b'\xef\xbb\xbf' if raw.startswith(b'\xef\xbb\xbf') else b''
    text = raw.decode('utf-8-sig')
    root = json_spans(text)
    hooks_member = json_member(root, 'hooks')
    if not hooks_member:
        return raw
    hooks = hooks_member[3]
    patches = []
    if hooks[0] != 'object':
        return raw
    for event in EVENTS:
        event_member = json_member(hooks, event)
        if not event_member or event_member[3][0] != 'array':
            continue
        groups = event_member[3]
        updated_groups = []
        changed = False
        for group in groups[3]:
            hooks_member = json_member(group, 'hooks')
            if not hooks_member or hooks_member[3][0] != 'array':
                updated_groups.append(text[group[1]:group[2]])
                continue
            array = hooks_member[3]
            retained = [item for item in array[3]
                        if not (type(json.loads(text[item[1]:item[2]])) is dict
                                and json.loads(text[item[1]:item[2]]).get('statusMessage') == MARKER)]
            if len(retained) == len(array[3]):
                updated_groups.append(text[group[1]:group[2]])
                continue
            changed = True
            if not retained:
                continue
            group_text = text[group[1]:group[2]]
            left = array[1] - group[1] + 1
            right = array[2] - group[1] - 1
            replacement = ','.join(text[item[1]:item[2]] for item in retained)
            updated_groups.append(group_text[:left] + replacement + group_text[right:])
        if changed:
            array = groups
            left = array[1] + 1
            right = array[2] - 1
            patches.append((left, right, ','.join(updated_groups)))
    for left, right, replacement in sorted(patches, reverse=True):
        text = text[:left] + replacement + text[right:]
    return bom + text.encode('utf-8')


def append_hook_groups_json(raw, event, groups):
    text = raw.decode('utf-8-sig') if isinstance(raw, bytes) else raw
    root = json_spans(text)
    hooks_member = json_member(root, 'hooks')
    serialized = ','.join(json.dumps(group, ensure_ascii=True) for group in groups)
    if not hooks_member:
        hooks_text = '{' + json.dumps(event) + ':[' + serialized + ']}'
        insert = (', ' if root[3] else '') + json.dumps('hooks') + ': ' + hooks_text
        return text[:root[2] - 1] + insert + text[root[2] - 1:]
    hooks = hooks_member[3]
    event_member = json_member(hooks, event)
    if event_member:
        array = event_member[3]
        insert = (',' if array[3] else '') + serialized
        return text[:array[2] - 1] + insert + text[array[2] - 1:]
    insert = (', ' if hooks[3] else '') + json.dumps(event) + ': [' + serialized + ']'
    return text[:hooks[2] - 1] + insert + text[hooks[2] - 1:]
