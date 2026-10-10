#!/usr/bin/env python3
"""JSON-only CLI for private chat state management."""
import argparse
import json
from pathlib import Path
import sys

from chat_learning import activate_lesson, activation_decision, apply_candidate, forget_lesson
from chat_state import delete_state, init_state, load_state, update_state


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError('invalid command')


def _read_object(reference):
    try:
        text = sys.stdin.read() if reference == '-' else Path(reference).read_text(encoding='utf-8')
        value = json.loads(text)
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError('invalid payload') from error
    if not isinstance(value, dict):
        raise ValueError('invalid payload')
    return value


def _parser():
    parser = Parser(add_help=True)
    commands = parser.add_subparsers(dest='command', required=True)

    init = commands.add_parser('init')
    init.add_argument('--scope', required=True)
    init.add_argument('--root', required=True)

    for name in ('show', 'apply-capsule', 'propose', 'activate', 'forget', 'compact', 'reset', 'delete'):
        command = commands.add_parser(name)
        command.add_argument('--adapter', required=True)
        command.add_argument('--conversation-id', required=True)
        if name != 'show':
            command.add_argument('--expected-revision', type=int, required=True)
        if name in {'apply-capsule', 'propose', 'activate', 'forget', 'compact'}:
            command.add_argument('--payload', required=True)
        if name == 'propose':
            command.add_argument('--corroboration-count', type=int, default=1)
        if name in {'activate', 'reset', 'delete'}:
            command.add_argument('--confirm', action='store_true')
        command.add_argument('--root', required=True)
    return parser


def _lesson_id(payload):
    if (not isinstance(payload, dict) or set(payload) != {'lesson_id'}
            or not isinstance(payload['lesson_id'], str) or not payload['lesson_id']
            or len(payload['lesson_id']) > 256):
        raise ValueError('invalid lesson request')
    return payload['lesson_id']


def _execute(args):
    root = Path(args.root)
    if args.command == 'init':
        return init_state(root, _read_object(args.scope))
    if args.command == 'show':
        return load_state(root, args.adapter, args.conversation_id)
    if args.command == 'delete':
        if not args.confirm:
            raise ValueError('confirmation required')
        return delete_state(root, args.adapter, args.conversation_id, args.expected_revision)
    if args.command == 'reset':
        if not args.confirm:
            raise ValueError('confirmation required')

        def reset(state):
            state['capsule'] = None
            state['lessons'] = []
            state['episodes'] = []
            state['administrative_events'].append({'operation': 'reset', 'at_revision': state['revision']})
        return update_state(root, args.adapter, args.conversation_id, args.expected_revision, reset)

    payload = _read_object(args.payload)
    if args.command == 'apply-capsule':
        operation = lambda state: state.update(capsule=payload)
    elif args.command == 'propose':
        def operation(state):
            decision = activation_decision(payload, state['lessons'], args.corroboration_count)
            apply_candidate(state, payload, decision)
    elif args.command == 'activate':
        def operation(state):
            if not args.confirm:
                raise ValueError('confirmation required')
            activate_lesson(state, _lesson_id(payload))
    elif args.command == 'forget':
        def operation(state):
            forget_lesson(state, _lesson_id(payload))
    elif args.command == 'compact':
        operation = lambda state: state['episodes'].append(payload)
    else:
        raise ValueError('invalid command')
    return update_state(root, args.adapter, args.conversation_id, args.expected_revision, operation)


def main():
    try:
        result = _execute(_parser().parse_args())
        code = 0
    except (ValueError, OSError, TypeError, KeyError):
        result = {'error': {'code': 'invalid-input', 'message': 'The state operation could not be completed.'}}
        code = 2
    json.dump(result, sys.stdout, sort_keys=True, separators=(',', ':'))
    sys.stdout.write('\n')
    return code


if __name__ == '__main__':
    raise SystemExit(main())
