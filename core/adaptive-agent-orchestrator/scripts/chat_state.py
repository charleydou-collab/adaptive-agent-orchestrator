#!/usr/bin/env python3
"""Private, revisioned, conversation-isolated state storage."""
from copy import deepcopy
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

try:  # POSIX hosts.
    import fcntl
except ImportError:  # pragma: no cover - exercised on Windows.
    fcntl = None

try:  # Windows hosts.
    import msvcrt
except ImportError:  # pragma: no cover - exercised on POSIX.
    msvcrt = None


REQUIRED_STATE_FIELDS = {
    'version', 'scope', 'revision', 'capsule', 'lessons', 'episodes',
    'administrative_events', 'created_at', 'updated_at',
}
SCHEMA_ROOT = Path(__file__).resolve().parents[1] / 'schemas'
MAX_STATE_ITEMS = 256
MAX_ADMINISTRATIVE_EVENTS = 128


def _now():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def conversation_key(adapter: str, conversation_id: str) -> str:
    if not isinstance(adapter, str) or not adapter or not isinstance(conversation_id, str) or not conversation_id:
        raise ValueError('invalid conversation scope')
    return hashlib.sha256((adapter + '\0' + conversation_id).encode('utf-8')).hexdigest()


def state_path(root: Path, key: str) -> Path:
    if not isinstance(key, str) or len(key) != 64 or any(char not in '0123456789abcdef' for char in key):
        raise ValueError('invalid conversation key')
    return Path(root) / (key + '.json')


def _prepare_root(root: Path) -> Path:
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    return root


def _validate_scope(scope):
    _validate_schema(scope, 'conversation-scope.schema.json', 'invalid conversation scope')
    conversation_key(scope['adapter'], scope['conversation_id'])


def _schema_type(value, kind):
    types = {'object': dict, 'array': list, 'string': str, 'boolean': bool,
        'integer': int, 'null': type(None)}
    return isinstance(value, types[kind]) and not (kind == 'integer' and isinstance(value, bool))


def _matches_schema(value, schema, root):
    if '$ref' in schema:
        if not schema['$ref'].startswith('#/'):
            return False
        target = root
        for part in schema['$ref'][2:].split('/'):
            target = target[part]
        return _matches_schema(value, target, root)
    if 'type' in schema:
        allowed = schema['type'] if isinstance(schema['type'], list) else [schema['type']]
        if not any(_schema_type(value, kind) for kind in allowed):
            return False
    if 'enum' in schema and value not in schema['enum']:
        return False
    if 'const' in schema and value != schema['const']:
        return False
    if isinstance(value, dict):
        if any(key not in value for key in schema.get('required', [])):
            return False
        properties = schema.get('properties', {})
        if schema.get('additionalProperties') is False and set(value) - set(properties):
            return False
        if any(not _matches_schema(item, properties[key], root)
                for key, item in value.items() if key in properties):
            return False
    if isinstance(value, list):
        if len(value) < schema.get('minItems', 0) or len(value) > schema.get('maxItems', float('inf')):
            return False
        if schema.get('uniqueItems'):
            serialized = [json.dumps(item, sort_keys=True, separators=(',', ':')) for item in value]
            if len(set(serialized)) != len(serialized):
                return False
        if any(not _matches_schema(item, schema.get('items', {}), root) for item in value):
            return False
    if isinstance(value, str):
        if len(value) < schema.get('minLength', 0) or len(value) > schema.get('maxLength', float('inf')):
            return False
        if 'pattern' in schema and re.search(schema['pattern'], value) is None:
            return False
    if isinstance(value, int) and not isinstance(value, bool):
        if value < schema.get('minimum', -float('inf')) or value > schema.get('maximum', float('inf')):
            return False
    if any(not _matches_schema(value, child, root) for child in schema.get('allOf', [])):
        return False
    if 'if' in schema:
        branch = schema.get('then', {}) if _matches_schema(value, schema['if'], root) else schema.get('else', {})
        if not _matches_schema(value, branch, root):
            return False
    return True


def _validate_schema(value, filename, message):
    try:
        schema = json.loads((SCHEMA_ROOT / filename).read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError('schema unavailable or corrupt') from error
    if not _matches_schema(value, schema, schema):
        raise ValueError(message)


def _validate_administrative_event(event):
    if (not isinstance(event, dict) or set(event) != {'operation', 'at_revision'}
            or event['operation'] != 'reset' or isinstance(event['at_revision'], bool)
            or not isinstance(event['at_revision'], int) or event['at_revision'] < 0):
        raise ValueError('invalid administrative event')


def _validate_state(state):
    if not isinstance(state, dict) or set(state) != REQUIRED_STATE_FIELDS:
        raise ValueError('invalid state document')
    _validate_scope(state['scope'])
    expected_key = conversation_key(
        state['scope']['adapter'], state['scope']['conversation_id'])
    if state['version'] != 1 or isinstance(state['revision'], bool) or not isinstance(state['revision'], int) or state['revision'] < 0:
        raise ValueError('invalid state document')
    for field in ('lessons', 'episodes', 'administrative_events'):
        if not isinstance(state[field], list):
            raise ValueError('invalid state document')
    if len(state['lessons']) > MAX_STATE_ITEMS or len(state['episodes']) > MAX_STATE_ITEMS:
        raise ValueError('invalid state document')
    if len(state['administrative_events']) > MAX_ADMINISTRATIVE_EVENTS:
        raise ValueError('invalid state document')
    if state['capsule'] is not None:
        _validate_schema(state['capsule'], 'chat-state-capsule.schema.json', 'invalid state capsule')
        if state['capsule']['conversation_key'] != expected_key:
            raise ValueError('state scope mismatch')
    for lesson in state['lessons']:
        _validate_schema(lesson, 'chat-lesson.schema.json', 'invalid chat lesson')
        if lesson['conversation_key'] != expected_key:
            raise ValueError('state scope mismatch')
    for episode in state['episodes']:
        _validate_schema(episode, 'episode-summary.schema.json', 'invalid episode summary')
        if episode['conversation_key'] != expected_key:
            raise ValueError('state scope mismatch')
    for event in state['administrative_events']:
        _validate_administrative_event(event)
    if not isinstance(state['created_at'], str) or not isinstance(state['updated_at'], str):
        raise ValueError('invalid state document')


def _require_persistent_scope(scope):
    if scope['persistence_class'] == 'none':
        raise ValueError('persistence unavailable')


@contextmanager
def _conversation_lock(root: Path, key: str, create_root=False):
    root = _prepare_root(root) if create_root else Path(root)
    if not root.is_dir():
        raise ValueError('state unavailable or corrupt')
    lock_path = root / (key + '.lock')
    descriptor = os.open(str(lock_path), os.O_CREAT | os.O_RDWR, 0o600)
    try:
        os.fchmod(descriptor, 0o600)
        if fcntl is not None:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
        elif msvcrt is not None:  # pragma: no cover - exercised on Windows.
            if os.fstat(descriptor).st_size == 0:
                os.write(descriptor, b'0')
            os.lseek(descriptor, 0, os.SEEK_SET)
            msvcrt.locking(descriptor, msvcrt.LK_LOCK, 1)
        else:  # pragma: no cover - all supported hosts provide one primitive.
            raise OSError('file locking unavailable')
        yield
    finally:
        if fcntl is not None:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        elif msvcrt is not None:  # pragma: no cover - exercised on Windows.
            os.lseek(descriptor, 0, os.SEEK_SET)
            msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
        os.close(descriptor)


def _temporary_json(path: Path, value):
    descriptor, temporary = tempfile.mkstemp(prefix='.' + path.name + '.', suffix='.tmp', dir=path.parent)
    temporary_path = Path(temporary)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
            json.dump(value, stream, sort_keys=True, separators=(',', ':'))
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        return temporary_path
    except Exception:
        try:
            os.close(descriptor)
        except OSError:
            pass
        temporary_path.unlink(missing_ok=True)
        raise


def _sync_directory(path: Path):
    descriptor = os.open(str(path), os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def init_state(root: Path, scope: dict) -> dict:
    _validate_scope(scope)
    _require_persistent_scope(scope)
    root = Path(root)
    key = conversation_key(scope['adapter'], scope['conversation_id'])
    path = state_path(root, key)
    timestamp = _now()
    state = {'version': 1, 'scope': deepcopy(scope), 'revision': 0, 'capsule': None,
        'lessons': [], 'episodes': [], 'administrative_events': [],
        'created_at': timestamp, 'updated_at': timestamp}
    with _conversation_lock(root, key, create_root=True):
        temporary = _temporary_json(path, state)
        try:
            try:
                os.link(temporary, path)
            except FileExistsError as error:
                raise ValueError('state already exists') from error
            _sync_directory(root)
        finally:
            temporary.unlink(missing_ok=True)
    return deepcopy(state)


def _load_state_unlocked(root: Path, adapter: str, conversation_id: str) -> dict:
    path = state_path(Path(root), conversation_key(adapter, conversation_id))
    try:
        with path.open('r', encoding='utf-8') as stream:
            state = json.load(stream)
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError('state unavailable or corrupt') from error
    _validate_state(state)
    _require_persistent_scope(state['scope'])
    expected = conversation_key(state['scope']['adapter'], state['scope']['conversation_id'])
    if expected != path.stem:
        raise ValueError('state scope mismatch')
    return state


def load_state(root: Path, adapter: str, conversation_id: str) -> dict:
    key = conversation_key(adapter, conversation_id)
    with _conversation_lock(Path(root), key):
        return _load_state_unlocked(root, adapter, conversation_id)


def update_state(root: Path, adapter: str, conversation_id: str, expected_revision: int, operation) -> dict:
    if isinstance(expected_revision, bool) or not isinstance(expected_revision, int) or expected_revision < 0:
        raise ValueError('invalid expected revision')
    key = conversation_key(adapter, conversation_id)
    path = state_path(Path(root), key)
    with _conversation_lock(Path(root), key):
        current = _load_state_unlocked(root, adapter, conversation_id)
        if current['revision'] != expected_revision:
            raise ValueError('stale revision')
        updated = deepcopy(current)
        operation(updated)
        if updated['version'] != current['version'] or updated['scope'] != current['scope'] or updated['revision'] != current['revision'] or updated['created_at'] != current['created_at']:
            raise ValueError('immutable state fields changed')
        updated['revision'] = current['revision'] + 1
        updated['updated_at'] = _now()
        _validate_state(updated)
        temporary = _temporary_json(path, updated)
        try:
            os.replace(temporary, path)
            _sync_directory(path.parent)
        finally:
            temporary.unlink(missing_ok=True)
    return deepcopy(updated)


def delete_state(root: Path, adapter: str, conversation_id: str, expected_revision: int) -> dict:
    if isinstance(expected_revision, bool) or not isinstance(expected_revision, int) or expected_revision < 0:
        raise ValueError('invalid expected revision')
    key = conversation_key(adapter, conversation_id)
    path = state_path(Path(root), key)
    with _conversation_lock(Path(root), key):
        current = _load_state_unlocked(root, adapter, conversation_id)
        if current['revision'] != expected_revision:
            raise ValueError('stale revision')
        path.unlink()
        _sync_directory(path.parent)
    return {'deleted': True, 'conversation_key': path.stem, 'revision': expected_revision}
