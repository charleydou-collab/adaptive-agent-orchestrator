"""End-to-end acceptance scenarios for v0.2.0 chat learning."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'core/adaptive-agent-orchestrator/scripts'
sys.path.insert(0, str(SCRIPTS))

from chat_state import conversation_key, load_state, state_path, update_state  # noqa: E402
from compile_context import compile_context  # noqa: E402

from tests.test_contracts import candidate as candidate_fixture, episode as episode_fixture, retrieval_request

CLI = SCRIPTS / 'manage_chat_state.py'


def scope(conversation_id):
    return {'adapter': 'codex-local', 'conversation_id': conversation_id,
        'persistence_class': 'session', 'storage_ref': 'test-store'}


def candidate(conversation_id, serial, rule, roles):
    value = candidate_fixture()
    value.update(candidate_id=f'candidate-{serial}',
        conversation_key=conversation_key('codex-local', conversation_id),
        rule=rule, role_targets=roles, source_refs=[f'turn-{serial}'],
        created_at=f'2026-10-{serial:02d}T00:00:00Z')
    return value


class ChatLearningEndToEndTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.state_root = Path(self.tmp.name) / 'chat-state'
        self.ledger = Path(self.tmp.name) / 'agent-ledger.json'
        self.ledger.write_bytes(b'{"must":"not-change"}\n')

    def cli(self, *args, payload=None):
        result = subprocess.run([sys.executable, str(CLI), *args, '--root', str(self.state_root)],
            input=payload, text=True, capture_output=True)
        self.assertEqual(result.stderr, '')
        return result.returncode, json.loads(result.stdout)

    def init(self, conversation_id):
        code, value = self.cli('init', '--scope', '-', payload=json.dumps(scope(conversation_id)))
        self.assertEqual(code, 0)
        return value

    def propose(self, conversation_id, revision, value):
        code, state = self.cli('propose', '--adapter', 'codex-local',
            '--conversation-id', conversation_id, '--expected-revision', str(revision),
            '--payload', '-', payload=json.dumps(value))
        self.assertEqual(code, 0)
        return state

    def request(self, conversation_id, role='management'):
        value = retrieval_request()
        value.update(conversation_key=conversation_key('codex-local', conversation_id),
            role=role, lesson_limit=5 if role == 'management' else 3, episode_limit=20)
        return value

    def platform(self, name):
        return json.loads((ROOT / f'adapters/{name}/platform-capabilities.yaml').read_text())

    def test_learning_isolated_compiled_reset_and_fallback_safe(self):
        self.init('conversation-one')
        self.init('conversation-two')
        first = self.propose('conversation-one', 0,
            candidate('conversation-one', 1, 'Use concise answers.', ['management']))
        second = self.propose('conversation-two', 0,
            candidate('conversation-two', 2, 'Use detailed answers.', ['management']))
        first = self.propose('conversation-one', first['revision'],
            candidate('conversation-one', 3, 'Cite source identifiers.', ['research-worker']))

        codex = self.platform('codex')
        management = compile_context(self.request('conversation-one'), codex, first, [], [])
        worker = compile_context(self.request('conversation-one', 'research-worker'), codex, first, [], [])
        other = compile_context(self.request('conversation-two'), codex, second, [], [])
        self.assertEqual([item['rule'] for item in management['content']['lessons']], ['Use concise answers.'])
        self.assertEqual([item['rule'] for item in worker['content']['lessons']], ['Cite source identifiers.'])
        self.assertEqual([item['rule'] for item in other['content']['lessons']], ['Use detailed answers.'])

        episodes = []
        for serial in range(1, 31):
            item = episode_fixture()
            item.update(episode_id=f'episode-{serial:02d}',
                conversation_key=conversation_key('codex-local', 'conversation-one'),
                summary=('optional history ' + str(serial) + ' ') * 20,
                completed_at=f'2026-09-{serial:02d}T00:00:00Z')
            episodes.append(item)
        first = update_state(self.state_root, 'codex-local', 'conversation-one', first['revision'],
            lambda state: state['episodes'].extend(episodes))
        bounded = compile_context(self.request('conversation-one'), codex, first, [], [],
            {'policy': 10, 'capsule': 10, 'lessons': 40, 'episodes': 100,
                'recent_turns': 30, 'total': 150})
        self.assertEqual(bounded['status'], 'ready')
        self.assertLessEqual(bounded['package']['total_estimated_tokens'], 150)
        self.assertTrue(any(item['reason_code'] == 'budget' for item in bounded['package']['omissions']))

        mandatory = [{'ref': 'turn-mandatory', 'content': 'x' * 300, 'topics': [],
            'entities': [], 'mandatory': True, 'requires_exact': True}]
        blocked = compile_context(self.request('conversation-one'), codex, first, mandatory, [],
            {'policy': 10, 'capsule': 10, 'lessons': 40, 'episodes': 100,
                'recent_turns': 5, 'total': 165})
        self.assertEqual(blocked['status'], 'blocked')
        self.assertEqual(blocked['blocker']['refs'], ['turn-mandatory'])

        second_before = load_state(self.state_root, 'codex-local', 'conversation-two')
        code, reset = self.cli('reset', '--adapter', 'codex-local',
            '--conversation-id', 'conversation-one', '--expected-revision', str(first['revision']), '--confirm')
        self.assertEqual(code, 0)
        self.assertEqual(reset['lessons'], [])
        self.assertEqual(load_state(self.state_root, 'codex-local', 'conversation-two'), second_before)

        first_path = state_path(self.state_root, conversation_key('codex-local', 'conversation-one'))
        first_path.write_text('{corrupt-state')
        corrupt_bytes = first_path.read_bytes()
        with self.assertRaises(ValueError):
            load_state(self.state_root, 'codex-local', 'conversation-one')
        self.assertEqual(first_path.read_bytes(), corrupt_bytes)
        self.assertEqual(load_state(self.state_root, 'codex-local', 'conversation-two'), second_before)

        web = self.platform('chatgpt-web')
        web_result = compile_context(self.request('conversation-two'), web, second_before, [], [])
        self.assertIn('approximate-token-estimation', web_result['audit']['fallback_reasons'])
        self.assertFalse(web['conversation_context']['persistence_supported'])
        self.assertFalse(web['conversation_context']['message_list_control'])
        self.assertEqual(web['conversation_context']['learning_scope'], 'in-chat')
        self.assertEqual(self.ledger.read_bytes(), b'{"must":"not-change"}\n')


if __name__ == '__main__':
    unittest.main()
