"""Storage and CLI checks for conversation-isolated chat state."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

from tests.test_contracts import candidate as candidate_fixture

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / 'core/adaptive-agent-orchestrator/scripts/chat_state.py'
CLI = ROOT / 'core/adaptive-agent-orchestrator/scripts/manage_chat_state.py'


def scope(adapter='adapter-a', conversation_id='conversation-1'):
    return {'adapter': adapter, 'conversation_id': conversation_id,
        'persistence_class': 'session', 'storage_ref': 'local-private-store'}


def capsule_fixture(conversation_id='conversation-1'):
    return {'conversation_key': hashlib.sha256(
            ('adapter-a\0' + conversation_id).encode()).hexdigest(),
        'revision': 1, 'objectives': [], 'decisions': [], 'constraints': [],
        'open_questions': [], 'accepted_facts': [], 'active_preferences': [],
        'artifact_refs': [], 'updated_at': '2026-10-10T00:00:00Z'}


def episode_fixture(episode_id='episode-1', conversation_id='conversation-1'):
    return {'episode_id': episode_id, 'conversation_key': hashlib.sha256(
            ('adapter-a\0' + conversation_id).encode()).hexdigest(),
        'task_id': 'task-' + episode_id, 'task_category': 'test', 'role_targets': [],
        'topics': [], 'entities': [], 'outcome': 'accepted', 'decision_refs': [],
        'lesson_ids': [], 'source_refs': [], 'summary': 'Stored test episode.',
        'completed_at': '2026-10-10T00:00:00Z'}


class ChatStateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location('chat_state', MODULE)
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'state'

    def test_conversation_key_is_deterministic_fixed_and_path_safe(self):
        for adapter, conversation_id in (
                ('a', 'x'), ('adapter-a', '../../escape'), ('../adapter', '/absolute/path')):
            expected = hashlib.sha256((adapter + '\0' + conversation_id).encode()).hexdigest()
            key = self.module.conversation_key(adapter, conversation_id)
            self.assertEqual(key, expected)
            self.assertRegex(key, r'^[0-9a-f]{64}$')
            path = self.module.state_path(self.root, key)
            self.assertEqual(path.parent, self.root)
            self.assertEqual(path.name, key + '.json')

    def test_initialization_is_private_and_does_not_overwrite(self):
        value = self.module.init_state(self.root, scope())
        path = self.module.state_path(self.root, self.module.conversation_key('adapter-a', 'conversation-1'))
        self.assertEqual(value['version'], 1)
        self.assertEqual(value['revision'], 0)
        self.assertEqual(value['capsule'], None)
        self.assertEqual(value['lessons'], [])
        self.assertEqual(value['episodes'], [])
        self.assertEqual(value['administrative_events'], [])
        self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)
        before = path.read_bytes()
        with self.assertRaises(ValueError):
            self.module.init_state(self.root, scope())
        self.assertEqual(path.read_bytes(), before)

    def test_non_persistent_and_workspace_scopes_cannot_be_stored(self):
        for index, (persistence_class, storage_ref) in enumerate(
                (('none', None), ('workspace', 'workspace-store'))):
            invalid = scope(conversation_id=f'conversation-{index}')
            invalid.update(persistence_class=persistence_class, storage_ref=storage_ref)
            with self.subTest(persistence_class=persistence_class):
                with self.assertRaises(ValueError):
                    self.module.init_state(self.root, invalid)

    def test_load_rejects_non_persistent_state_even_if_injected_on_disk(self):
        self.module.init_state(self.root, scope())
        key = self.module.conversation_key('adapter-a', 'conversation-1')
        path = self.module.state_path(self.root, key)
        injected = json.loads(path.read_text())
        injected['scope']['persistence_class'] = 'none'
        injected['scope']['storage_ref'] = None
        path.write_text(json.dumps(injected))
        with self.assertRaises(ValueError):
            self.module.load_state(self.root, 'adapter-a', 'conversation-1')

    def test_initialization_does_not_replace_concurrent_destination(self):
        target_scope = scope()
        key = self.module.conversation_key('adapter-a', 'conversation-1')
        path = self.module.state_path(self.root, key)
        self.root.mkdir(parents=True)
        original = b'concurrent-writer\n'
        real_link = self.module.os.link

        def create_first(source, destination):
            Path(destination).write_bytes(original)
            return real_link(source, destination)

        with mock.patch.object(self.module.os, 'link', side_effect=create_first):
            with self.assertRaises(ValueError):
                self.module.init_state(self.root, target_scope)
        self.assertEqual(path.read_bytes(), original)
        self.assertEqual(list(self.root.glob('.*.tmp')), [])

    def test_two_conversations_are_isolated(self):
        self.module.init_state(self.root, scope(conversation_id='one'))
        self.module.init_state(self.root, scope(conversation_id='two'))
        first = self.module.update_state(self.root, 'adapter-a', 'one', 0,
            lambda state: state.update(capsule=capsule_fixture('one')))
        second = self.module.load_state(self.root, 'adapter-a', 'two')
        self.assertEqual(first['revision'], 1)
        self.assertEqual(first['capsule'], capsule_fixture('one'))
        self.assertEqual(second['revision'], 0)
        self.assertIsNone(second['capsule'])

    def test_atomic_update_and_failed_replace_preserve_original(self):
        self.module.init_state(self.root, scope())
        path = self.module.state_path(self.root, self.module.conversation_key('adapter-a', 'conversation-1'))
        before = path.read_bytes()
        real_replace = self.module.os.replace

        def inspect_then_replace(source, destination):
            self.assertEqual(Path(source).parent, path.parent)
            self.assertEqual(Path(destination), path)
            self.assertEqual(path.read_bytes(), before)
            json.loads(Path(source).read_text())
            real_replace(source, destination)

        with mock.patch.object(self.module.os, 'replace', side_effect=inspect_then_replace):
            self.module.update_state(self.root, 'adapter-a', 'conversation-1', 0,
                lambda state: state['episodes'].append(episode_fixture('episode-1')))
        after = path.read_bytes()
        with mock.patch.object(self.module.os, 'replace', side_effect=OSError('simulated')):
            with self.assertRaises(OSError):
                self.module.update_state(self.root, 'adapter-a', 'conversation-1', 1,
                    lambda state: state['episodes'].append(episode_fixture('episode-2')))
        self.assertEqual(path.read_bytes(), after)
        self.assertEqual(list(path.parent.glob('.*.tmp')), [])

    def test_corrupt_state_is_preserved(self):
        self.root.mkdir(parents=True)
        path = self.module.state_path(self.root, self.module.conversation_key('adapter-a', 'conversation-1'))
        path.write_text('{not-json')
        before = path.read_bytes()
        with self.assertRaises(ValueError):
            self.module.load_state(self.root, 'adapter-a', 'conversation-1')
        with self.assertRaises(ValueError):
            self.module.update_state(self.root, 'adapter-a', 'conversation-1', 0, lambda state: None)
        self.assertEqual(path.read_bytes(), before)

    def test_stale_revision_rejects_second_writer_without_mutation(self):
        self.module.init_state(self.root, scope())
        snapshot = self.module.load_state(self.root, 'adapter-a', 'conversation-1')
        self.module.update_state(self.root, 'adapter-a', 'conversation-1', snapshot['revision'],
            lambda state: state['episodes'].append(episode_fixture('first')))
        before = copy.deepcopy(self.module.load_state(self.root, 'adapter-a', 'conversation-1'))
        with self.assertRaises(ValueError):
            self.module.update_state(self.root, 'adapter-a', 'conversation-1', snapshot['revision'],
                lambda state: state['episodes'].append(episode_fixture('second')))
        self.assertEqual(self.module.load_state(self.root, 'adapter-a', 'conversation-1'), before)

    def test_concurrent_writers_serialize_revision_check_and_write(self):
        self.module.init_state(self.root, scope())
        operation_barrier = threading.Barrier(2)
        results = []

        def write(episode_id):
            try:
                def operation(state):
                    try:
                        operation_barrier.wait(timeout=0.3)
                    except threading.BrokenBarrierError:
                        pass
                    state['episodes'].append(episode_fixture(episode_id))
                results.append(('ok', self.module.update_state(
                    self.root, 'adapter-a', 'conversation-1', 0, operation)['revision']))
            except ValueError as error:
                results.append(('error', str(error)))

        threads = [threading.Thread(target=write, args=(name,)) for name in ('one', 'two')]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=3)
        self.assertTrue(all(not thread.is_alive() for thread in threads))
        self.assertEqual(sorted(item[0] for item in results), ['error', 'ok'])
        self.assertEqual(self.module.load_state(self.root, 'adapter-a', 'conversation-1')['revision'], 1)

    def test_delete_cannot_interleave_with_reset_and_resurrect_state(self):
        self.module.init_state(self.root, scope())
        reset_entered = threading.Event()
        release_reset = threading.Event()
        outcomes = []

        def reset():
            try:
                def operation(state):
                    reset_entered.set()
                    release_reset.wait(timeout=2)
                    state['capsule'] = None
                    state['lessons'] = []
                    state['episodes'] = []
                    state['administrative_events'].append(
                        {'operation': 'reset', 'at_revision': state['revision']})
                outcomes.append(('reset', 'ok', self.module.update_state(
                    self.root, 'adapter-a', 'conversation-1', 0, operation)['revision']))
            except (OSError, ValueError) as error:
                outcomes.append(('reset', 'error', str(error)))

        def delete():
            try:
                outcomes.append(('delete', 'ok', self.module.delete_state(
                    self.root, 'adapter-a', 'conversation-1', 0)))
            except (OSError, ValueError) as error:
                outcomes.append(('delete', 'error', str(error)))

        reset_thread = threading.Thread(target=reset)
        reset_thread.start()
        self.assertTrue(reset_entered.wait(timeout=1))
        delete_thread = threading.Thread(target=delete)
        delete_thread.start()
        time.sleep(0.05)
        release_reset.set()
        reset_thread.join(timeout=3)
        delete_thread.join(timeout=3)
        self.assertEqual([(item[0], item[1]) for item in outcomes],
            [('reset', 'ok'), ('delete', 'error')])
        self.assertEqual(self.module.load_state(
            self.root, 'adapter-a', 'conversation-1')['revision'], 1)

    def test_mutation_boundary_rejects_malformed_persisted_records(self):
        mutations = (
            lambda state: state.update(capsule={'summary': 'not a capsule'}),
            lambda state: state['episodes'].append({'episode_id': 'incomplete'}),
            lambda state: state['lessons'].append({'lesson_id': 'incomplete'}),
            lambda state: state['administrative_events'].append({'operation': 'unknown'}),
        )
        for index, operation in enumerate(mutations):
            with self.subTest(operation=operation):
                conversation_id = f'conversation-{index}'
                self.module.init_state(self.root, scope(conversation_id=conversation_id))
                with self.assertRaises(ValueError):
                    self.module.update_state(
                        self.root, 'adapter-a', conversation_id, 0, operation)
                self.assertEqual(self.module.load_state(
                    self.root, 'adapter-a', conversation_id)['revision'], 0)

    def test_episode_size_limit_is_enforced_at_storage_boundary(self):
        self.module.init_state(self.root, scope())
        oversized = episode_fixture('oversized')
        oversized['summary'] = 'x' * 4001
        with self.assertRaisesRegex(ValueError, 'invalid episode summary'):
            self.module.update_state(self.root, 'adapter-a', 'conversation-1', 0,
                lambda state: state['episodes'].append(oversized))
        self.assertEqual(self.module.load_state(
            self.root, 'adapter-a', 'conversation-1')['revision'], 0)

    def test_mutation_boundary_rejects_records_from_another_conversation(self):
        for index, record_type in enumerate(('capsule', 'episode')):
            conversation_id = f'conversation-{index}'
            self.module.init_state(self.root, scope(conversation_id=conversation_id))
            foreign_capsule = capsule_fixture('other-conversation')
            foreign_episode = episode_fixture('foreign', 'other-conversation')
            operation = (lambda state: state.update(capsule=foreign_capsule)) if record_type == 'capsule' else (
                lambda state: state['episodes'].append(foreign_episode))
            with self.subTest(operation=operation):
                with self.assertRaises(ValueError):
                    self.module.update_state(
                        self.root, 'adapter-a', conversation_id, 0, operation)
                self.assertEqual(self.module.load_state(
                    self.root, 'adapter-a', conversation_id)['revision'], 0)

    def cli(self, *args, payload=None):
        result = subprocess.run([sys.executable, str(CLI), *args, '--root', str(self.root)],
            input=payload, text=True, capture_output=True)
        self.assertEqual(result.stderr, '')
        return result.returncode, json.loads(result.stdout)

    def test_cli_json_operations_confirmation_and_revisions(self):
        encoded_scope = json.dumps(scope())
        code, state = self.cli('init', '--scope', '-', payload=encoded_scope)
        self.assertEqual(code, 0)
        self.assertEqual(state['revision'], 0)

        common = ('--adapter', 'adapter-a', '--conversation-id', 'conversation-1')
        self.assertEqual(self.cli('show', *common)[0], 0)
        code, state = self.cli('apply-capsule', *common, '--expected-revision', '0',
            '--payload', '-', payload=json.dumps(capsule_fixture()))
        self.assertEqual(code, 0)
        self.assertEqual(state['revision'], 1)
        learning_candidate = candidate_fixture()
        learning_candidate['conversation_key'] = hashlib.sha256(
            b'adapter-a\0conversation-1').hexdigest()
        learning_candidate['confidence_class'] = 'inferred'
        learning_candidate['verified'] = False
        code, state = self.cli('propose', *common, '--expected-revision', '1',
            '--payload', '-', payload=json.dumps(learning_candidate))
        self.assertEqual(code, 0)
        code, state = self.cli('activate', *common, '--expected-revision', '2',
            '--payload', '-', '--confirm', payload=json.dumps({'lesson_id': 'lesson-candidate-1'}))
        self.assertEqual(code, 0)
        self.assertEqual(state['lessons'][0]['status'], 'active')
        self.assertEqual(state['lessons'][0]['version'], 2)
        self.assertNotEqual(state['lessons'][0]['updated_at'], state['lessons'][0]['created_at'])
        code, state = self.cli('forget', *common, '--expected-revision', '3',
            '--payload', '-', payload=json.dumps({'lesson_id': 'lesson-candidate-1'}))
        self.assertEqual(code, 0)
        self.assertEqual(state['lessons'][0]['status'], 'forgotten')
        self.assertEqual(self.cli('compact', *common, '--expected-revision', '4',
            '--payload', '-', payload=json.dumps(episode_fixture()))[0], 0)

        self.assertEqual(self.cli('reset', *common, '--expected-revision', '5')[0], 2)
        code, reset = self.cli('reset', *common, '--expected-revision', '5', '--confirm')
        self.assertEqual(code, 0)
        self.assertEqual(reset['revision'], 6)
        self.assertEqual(reset['lessons'], [])
        self.assertEqual(self.cli('delete', *common, '--expected-revision', '6')[0], 2)
        self.assertEqual(self.cli('delete', *common, '--expected-revision', '6', '--confirm')[0], 0)
        self.assertEqual(self.cli('show', *common)[0], 2)

    def test_cli_payload_file_stale_revision_and_sanitized_errors(self):
        scope_path = Path(self.tmp.name) / 'scope.json'
        scope_path.write_text(json.dumps(scope(conversation_id='../../secret-id')))
        self.assertEqual(self.cli('init', '--scope', str(scope_path))[0], 0)
        common = ('--adapter', 'adapter-a', '--conversation-id', '../../secret-id')
        payload_path = Path(self.tmp.name) / 'capsule.json'
        payload_path.write_text(json.dumps(capsule_fixture('../../secret-id')))
        self.assertEqual(self.cli('apply-capsule', *common, '--expected-revision', '0',
            '--payload', str(payload_path))[0], 0)
        code, error = self.cli('apply-capsule', *common, '--expected-revision', '0',
            '--payload', str(payload_path))
        self.assertEqual(code, 2)
        self.assertNotIn('../../secret-id', json.dumps(error))
        code, error = self.cli('apply-capsule', *common, '--expected-revision', '1',
            '--payload', '-', payload='{private-corrupt-payload')
        self.assertEqual(code, 2)
        self.assertNotIn('private-corrupt-payload', json.dumps(error))


if __name__ == '__main__':
    unittest.main()
