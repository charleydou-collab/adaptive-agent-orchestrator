#!/usr/bin/env python3
"""Stdlib-only metadata ledger. Serialize writers; atomic replace is not a lock."""
import argparse
import copy
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
import tempfile

SCHEMA_PATH = Path(__file__).resolve().parents[1] / 'schemas/ledger-event.schema.json'


def validate(value, schema):
    """Validate exactly the vocabulary used by the canonical ledger schema."""
    kinds = {'object': dict, 'array': list, 'string': str, 'number': (int, float), 'null': type(None)}
    if 'type' in schema:
        allowed = schema['type'] if isinstance(schema['type'], list) else [schema['type']]
        if not any(isinstance(value, kinds[k]) and not (k == 'number' and isinstance(value, bool)) for k in allowed):
            raise ValueError('Invalid metadata type')
    if 'const' in schema and (type(value) is not type(schema['const']) or value != schema['const']):
        raise ValueError('Verified evidence is required')
    if 'enum' in schema and value not in schema['enum']:
        raise ValueError('Invalid metadata enumeration')
    if isinstance(value, dict):
        props = schema.get('properties', {})
        if set(schema.get('required', [])) - value.keys():
            raise ValueError('Required metadata is missing')
        if schema.get('additionalProperties') is False and value.keys() - props.keys():
            raise ValueError('Unknown or sensitive payload field rejected')
        for key, item in value.items():
            validate(item, props.get(key, {}))
    elif isinstance(value, list):
        if len(value) < schema.get('minItems', 0):
            raise ValueError('Required metadata list is empty')
        if schema.get('uniqueItems') and len({json.dumps(x, sort_keys=True) for x in value}) != len(value):
            raise ValueError('Duplicate metadata item')
        for item in value:
            validate(item, schema.get('items', {}))
    elif isinstance(value, str):
        if len(value) < schema.get('minLength', 0) or len(value) > schema.get('maxLength', math.inf):
            raise ValueError('Invalid metadata text length')
        if schema.get('minLength') and not value.strip():
            raise ValueError('Blank metadata text')
        if 'pattern' in schema and not re.search(schema['pattern'], value):
            raise ValueError('Invalid metadata format')
        if schema.get('format') == 'date-time':
            datetime.fromisoformat(value.replace('Z', '+00:00'))
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        if not math.isfinite(value) or not schema.get('minimum', -math.inf) <= value <= schema.get('maximum', math.inf):
            raise ValueError('Invalid score delta')


def atomic_write(path, state):
    """Flush a private same-directory temporary file, then atomically replace."""
    path = Path(path)
    text = json.dumps(state, indent=2, sort_keys=True, allow_nan=False) + '\n'
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                         prefix='.' + path.name + '.', suffix='.tmp', delete=False) as stream:
            temporary = stream.name
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None and os.path.exists(temporary):
            os.unlink(temporary)


def atomic_create(path, state):
    """Create a flushed ledger without replacing a concurrently created file."""
    path = Path(path)
    text = json.dumps(state, indent=2, sort_keys=True, allow_nan=False) + '\n'
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                         prefix='.' + path.name + '.', suffix='.tmp', delete=False) as stream:
            temporary = stream.name
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError as exc:
            raise ValueError('Ledger already exists; use confirmed reset') from exc
    finally:
        if temporary is not None and os.path.exists(temporary):
            os.unlink(temporary)


def load_ledger(path):
    state = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(state, dict) or state.get('version') != 1:
        raise ValueError('Unsupported ledger format')
    return state


def init_ledger(path, scope='workspace'):
    if scope not in ('durable', 'workspace', 'session'):
        raise ValueError('Persistence scope must support a ledger')
    state = {'version': 1, 'scope': scope, 'identities': {},
             'events': [], 'outcomes': {}, 'administrative_events': []}
    atomic_create(path, state)
    return state


def identity_key(event):
    scope = {key: copy.deepcopy(event[key]) for key in ('agent_identity', 'adapter', 'platform', 'execution_fingerprint', 'role', 'task_category', 'capability_tier')}
    for name in ('tools', 'modalities'):
        scope['execution_fingerprint'][name].sort()
    return hashlib.sha256(json.dumps(scope, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def new_identity(event, key):
    return {'identity_key': key, 'agent_identity': event['agent_identity'], 'adapter': event['adapter'],
            'platform': event['platform'], 'execution_fingerprint': copy.deepcopy(event['execution_fingerprint']),
            'role': event['role'], 'task_category': event['task_category'], 'capability_tier': event['capability_tier'],
            'score': 100, 'status': 'active', 'eligible': True, 'generation': 0}


def record_event(path, event):
    validate(event, json.loads(SCHEMA_PATH.read_text(encoding='utf-8')))
    state = load_ledger(path)
    if event['event_id'] in state['outcomes']:
        raise ValueError('Event ID already recorded')
    if 'correction_of' in event and 'equivalence_of' in event:
        raise ValueError('Correction and equivalence must be separate events')
    key = identity_key(event)
    fresh = key not in state['identities']
    item = state['identities'].setdefault(key, new_identity(event, key))
    before = item['score']
    frozen = event['score_update_mode'] == 'freeze'
    delta = Decimal(str(event['delta']))
    if 'equivalence_of' in event:
        source = state['outcomes'].get(event['equivalence_of'])
        if not fresh or source is None or delta != 0:
            raise ValueError('Equivalence requires a new scope, a current source event, and zero delta')
        source_item = state['identities'][source['identity_key']]
        if source['generation'] != source_item['generation']:
            raise ValueError('Equivalence requires the current source reset generation')
        if source_item['agent_identity'] != event['agent_identity']:
            raise ValueError('Equivalence cannot change logical identity')
        if not frozen:
            item['score'] = source['score_after']
            item['status'] = source_item['status']
    if 'correction_of' in event:
        original = state['outcomes'].get(event['correction_of'])
        if original is None or original['identity_key'] != key or original['generation'] != item['generation'] or original['applied_delta'] >= 0 or delta <= 0:
            raise ValueError('Correction requires an applied deduction in this scope and reset generation')
        restored = sum((Decimal(str(state['outcomes'][e['event_id']]['applied_delta']))
                        for e in state['events'] if e.get('correction_of') == event['correction_of']), Decimal(0))
        if restored + delta > -Decimal(str(original['applied_delta'])) / 2:
            raise ValueError('Cumulative corrections exceed half the actual deduction')
    if not frozen:
        item['score'] = float(max(Decimal(0), min(Decimal(200), Decimal(str(item['score'])) + delta)))
        if item['score'] == 0:
            item['status'] = 'retired'
    item['eligible'] = item['status'] == 'active' and item['score'] > 0
    applied = float(Decimal(str(item['score'])) - Decimal(str(before)))
    # Imported equivalence is attribution, never a correctable deduction.
    if 'equivalence_of' in event:
        applied = 0
    state['events'].append(copy.deepcopy(event))
    state['outcomes'][event['event_id']] = {'identity_key': key, 'score_before': before,
        'score_after': item['score'], 'applied_delta': applied, 'generation': item['generation']}
    atomic_write(path, state)
    return item


def administrative_event(state, operation, key):
    entry = {'operation': operation, 'timestamp': datetime.now(timezone.utc).isoformat(),
             'identity_key': key, 'generation': state['identities'][key]['generation']}
    state['administrative_events'].append(entry)


def retire_identity(path, key, confirm=False):
    if confirm is not True:
        raise ValueError('Retirement requires --confirm')
    state = load_ledger(path)
    if key not in state['identities']:
        raise ValueError('Unknown scoped identity')
    item = state['identities'][key]
    item.update(status='retired', eligible=False)
    administrative_event(state, 'retire', key)
    atomic_write(path, state)
    return item


def reset_ledger(path, key, confirm=False):
    if confirm is not True:
        raise ValueError('Reset requires --confirm')
    state = load_ledger(path)
    if key not in state['identities']:
        raise ValueError('Unknown scoped identity')
    item = state['identities'][key]
    item.update(score=100, status='active', eligible=True, generation=item['generation'] + 1)
    administrative_event(state, 'reset', key)
    atomic_write(path, state)
    return state


class JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError(message)


def main(argv=None):
    parser = JsonArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='operation', required=True)
    for operation in ('init', 'record', 'show', 'retire', 'reset'):
        command = commands.add_parser(operation)
        command.add_argument('--ledger', required=True, type=Path)
        if operation == 'init':
            command.add_argument('--scope', choices=('durable', 'workspace', 'session'), default='workspace')
        if operation == 'record':
            command.add_argument('--event', required=True, help='Canonical event JSON file, or - for stdin')
        if operation in ('retire', 'reset'):
            command.add_argument('--identity-key', required=True)
        if operation in ('retire', 'reset'):
            command.add_argument('--confirm', action='store_true')
    try:
        args = parser.parse_args(argv)
        if args.operation == 'init':
            result = init_ledger(args.ledger, args.scope)
        elif args.operation == 'record':
            raw = sys.stdin.read() if args.event == '-' else Path(args.event).read_text(encoding='utf-8')
            result = record_event(args.ledger, json.loads(raw))
        elif args.operation == 'show':
            result = load_ledger(args.ledger)
        elif args.operation == 'retire':
            result = retire_identity(args.ledger, args.identity_key, args.confirm)
        else:
            result = reset_ledger(args.ledger, args.identity_key, args.confirm)
        print(json.dumps(result, sort_keys=True, allow_nan=False))
        return 0
    except (OSError, ValueError, TypeError, KeyError) as exc:
        # Input data and filesystem contents must never be echoed in diagnostics.
        message = str(exc) if type(exc) is ValueError else 'Invalid input or ledger I/O failure'
        print(json.dumps({'error': message}))
        return 2


if __name__ == '__main__':
    sys.exit(main())
