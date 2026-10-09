#!/usr/bin/env python3
"""Private, revisioned, conversation-isolated state storage."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile


REQUIRED_STATE_FIELDS = {
    'version', 'scope', 'revision', 'capsule', 'lessons', 'episodes',
    'administrative_events', 'created_at', 'updated_at',
}


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
    if not isinstance(scope, dict):
        raise ValueError('invalid conversation scope')
    required = {'adapter', 'conversation_id', 'persistence_class', 'storage_ref'}
    if set(scope) != required:
        raise ValueError('invalid conversation scope')
    conversation_key(scope['adapter'], scope['conversation_id'])
    if scope['persistence_class'] not in {'durable', 'workspace', 'session', 'none'}:
        raise ValueError('invalid conversation scope')
    if scope['storage_ref'] is not None and not isinstance(scope['storage_ref'], str):
        raise ValueError('invalid conversation scope')


def _validate_state(state):
    if not isinstance(state, dict) or set(state) != REQUIRED_STATE_FIELDS:
        raise ValueError('invalid state document')
    _validate_scope(state['scope'])
    if state['version'] != 1 or isinstance(state['revision'], bool) or not isinstance(state['revision'], int) or state['revision'] < 0:
        raise ValueError('invalid state document')
    for field in ('lessons', 'episodes', 'administrative_events'):
        if not isinstance(state[field], list):
            raise ValueError('invalid state document')
    if not isinstance(state['created_at'], str) or not isinstance(state['updated_at'], str):
        raise ValueError('invalid state document')


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
    root = _prepare_root(root)
    key = conversation_key(scope['adapter'], scope['conversation_id'])
    path = state_path(root, key)
    timestamp = _now()
    state = {'version': 1, 'scope': deepcopy(scope), 'revision': 0, 'capsule': None,
        'lessons': [], 'episodes': [], 'administrative_events': [],
        'created_at': timestamp, 'updated_at': timestamp}
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


def load_state(root: Path, adapter: str, conversation_id: str) -> dict:
    path = state_path(Path(root), conversation_key(adapter, conversation_id))
    try:
        with path.open('r', encoding='utf-8') as stream:
            state = json.load(stream)
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError('state unavailable or corrupt') from error
    _validate_state(state)
    expected = conversation_key(state['scope']['adapter'], state['scope']['conversation_id'])
    if expected != path.stem:
        raise ValueError('state scope mismatch')
    return state


def update_state(root: Path, adapter: str, conversation_id: str, expected_revision: int, operation) -> dict:
    if isinstance(expected_revision, bool) or not isinstance(expected_revision, int) or expected_revision < 0:
        raise ValueError('invalid expected revision')
    path = state_path(Path(root), conversation_key(adapter, conversation_id))
    current = load_state(root, adapter, conversation_id)
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
    current = load_state(root, adapter, conversation_id)
    if current['revision'] != expected_revision:
        raise ValueError('stale revision')
    path = state_path(Path(root), conversation_key(adapter, conversation_id))
    path.unlink()
    _sync_directory(path.parent)
    return {'deleted': True, 'conversation_key': path.stem, 'revision': expected_revision}
