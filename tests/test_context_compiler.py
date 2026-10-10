"""Deterministic selection and budget tests for compiled chat context."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest

from tests.test_chat_learning import active_lesson
from tests.test_contracts import SCHEMAS, episode as episode_fixture, platform as platform_fixture, retrieval_request, validate

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'core/adaptive-agent-orchestrator/scripts/compile_context.py'
ADAPTER = 'test-adapter'
CONVERSATION_ID = 'test-conversation'
CONVERSATION_KEY = hashlib.sha256(
    (ADAPTER + '\0' + CONVERSATION_ID).encode('utf-8')).hexdigest()


def request(**updates):
    value = retrieval_request()
    value.update(conversation_key=CONVERSATION_KEY,
        required_evidence_refs=[], applicability_facts=[])
    value.update(updates)
    return value


def lesson(serial, **updates):
    value = active_lesson(lesson_id=f'lesson-{serial}', updated_at=f'2026-10-{serial:02d}T00:00:00Z')
    value.update(conversation_key=CONVERSATION_KEY, conditions=[])
    value.update(updates)
    return value


def episode(serial, **updates):
    value = episode_fixture()
    value.update(episode_id=f'episode-{serial}', conversation_key=CONVERSATION_KEY,
        completed_at=f'2026-10-{serial:02d}T00:00:00Z')
    value.update(updates)
    return value


def state(lessons=None, episodes=None, capsule=None):
    return {'version': 1, 'scope': {'adapter': ADAPTER,
        'conversation_id': CONVERSATION_ID, 'persistence_class': 'session',
        'storage_ref': 'test-store'}, 'revision': 1, 'capsule': capsule,
        'lessons': list(lessons or []), 'episodes': list(episodes or []),
        'administrative_events': [], 'created_at': '2026-10-01T00:00:00Z',
        'updated_at': '2026-10-10T00:00:00Z'}


class ContextCompilerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location('compile_context', SCRIPT)
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)

    def test_default_and_maximum_budgets(self):
        self.assertEqual(self.module.NORMAL_LIMITS,
            {'policy': 600, 'capsule': 500, 'lessons': 300, 'episodes': 800, 'recent_turns': 1200})
        self.assertEqual(self.module.MAX_LIMITS,
            {'policy': 1000, 'capsule': 800, 'lessons': 600, 'episodes': 1500, 'recent_turns': 2000})

    def test_estimator_is_deterministic_conservative_and_approximate(self):
        self.assertEqual(self.module.estimate_tokens(''), 0)
        self.assertEqual(self.module.estimate_tokens('abc'), 1)
        self.assertEqual(self.module.estimate_tokens('abcd'), 2)
        self.assertGreater(self.module.estimate_tokens('你好'), 1)
        result = self.module.compile_context(request(), platform_fixture(), state(), [], [])
        self.assertEqual(result['package']['estimate_quality'], 'approximate')
        self.assertEqual(result['audit']['estimate_quality'], 'approximate')

    def test_lesson_filtering_ranking_and_audience_limits(self):
        values = [lesson(i) for i in range(1, 8)]
        values.extend([
            lesson(8, status='proposed'),
            lesson(9, conversation_key='other'),
            lesson(10, task_categories=['unrelated']),
            lesson(11, role_targets=['worker']),
        ])
        ranked = self.module.rank_lessons(request(), values)
        self.assertEqual([item['lesson_id'] for item in ranked[:3]], ['lesson-7', 'lesson-6', 'lesson-5'])
        management = self.module.compile_context(request(), platform_fixture(), state(lessons=values), [], [])
        self.assertEqual(len(management['package']['selected_lesson_ids']), 5)
        worker_request = request(role='research-worker')
        worker_values = [lesson(i, role_targets=['research-worker']) for i in range(1, 7)]
        worker = self.module.compile_context(worker_request, platform_fixture(), state(lessons=worker_values), [], [])
        self.assertEqual(len(worker['package']['selected_lesson_ids']), 3)

    def test_mismatched_request_state_or_capsule_identity_fails_closed(self):
        wrong_state = state()
        wrong_state['scope']['conversation_id'] = 'different-conversation'
        with self.assertRaisesRegex(ValueError, 'conversation scope mismatch'):
            self.module.compile_context(request(), platform_fixture(), wrong_state, [], [])

        wrong_capsule = {
            'conversation_key': 'different-key', 'revision': 1,
            'objectives': [], 'decisions': [], 'constraints': [],
            'open_questions': [], 'accepted_facts': [],
            'active_preferences': [], 'artifact_refs': [],
            'updated_at': '2026-10-10T00:00:00Z',
        }
        with self.assertRaisesRegex(ValueError, 'capsule conversation mismatch'):
            self.module.compile_context(
                request(), platform_fixture(), state(capsule=wrong_capsule), [], [])

    def test_lesson_conditions_and_exceptions_use_request_facts(self):
        values = [
            lesson(1, rule='conditional', conditions=['needs-translation']),
            lesson(2, rule='excepted', exceptions=['draft-only']),
            lesson(3, rule='applicable', conditions=['needs-citations'],
                exceptions=['legal-only']),
        ]
        facts = request(applicability_facts=['needs-citations', 'draft-only'])
        result = self.module.compile_context(
            facts, platform_fixture(), state(lessons=values), [], [])
        self.assertEqual(result['package']['selected_lesson_ids'], ['lesson-3'])

    def test_worker_omits_management_capsule_and_unscoped_history(self):
        current_capsule = {
            'conversation_key': CONVERSATION_KEY, 'revision': 1,
            'objectives': [{'text': 'management only', 'source_refs': ['turn-secret']}],
            'decisions': [], 'constraints': [], 'open_questions': [],
            'accepted_facts': [], 'active_preferences': [], 'artifact_refs': [],
            'updated_at': '2026-10-10T00:00:00Z',
        }
        history = [
            episode(1, role_targets=['management'], summary='management history'),
            episode(2, role_targets=['research-worker'], summary='worker history'),
        ]
        turns = [
            {'ref': 'turn-management', 'content': 'management turn', 'topics': [],
                'entities': [], 'mandatory': False, 'requires_exact': False,
                'role_targets': ['management']},
            {'ref': 'turn-worker', 'content': 'worker turn', 'topics': [],
                'entities': [], 'mandatory': False, 'requires_exact': False,
                'role_targets': ['research-worker']},
        ]
        result = self.module.compile_context(request(role='research-worker'),
            platform_fixture(), state(episodes=history, capsule=current_capsule), turns, [])
        self.assertIsNone(result['content']['capsule'])
        self.assertIsNone(result['package']['capsule_ref'])
        self.assertEqual(result['package']['selected_episode_ids'], ['episode-2'])
        self.assertEqual(result['package']['selected_recent_turn_refs'], ['turn-worker'])

    def test_episode_ranking_uses_task_role_topic_entity_and_stable_id(self):
        values = [
            episode(1, task_category='other', topics=['none'], entities=[]),
            episode(2, role_targets=['management'], topics=['backup'], entities=['company documents']),
            episode(3, role_targets=['management'], topics=['backup'], entities=['company documents']),
            episode(4, conversation_key='other'),
        ]
        ranked = self.module.rank_episodes(request(), values)
        self.assertEqual([item['episode_id'] for item in ranked], ['episode-3', 'episode-2', 'episode-1'])

    def test_compilation_is_deterministic_and_preserves_required_inputs(self):
        current = state(lessons=[lesson(1)], episodes=[episode(1)])
        turns = [{'ref': 'turn-2', 'content': 'recent detail', 'topics': ['backup'],
            'entities': [], 'mandatory': False, 'requires_exact': False}]
        required = [{'ref': 'artifact-1', 'content': 'required source body', 'requires_exact': True}]
        first = self.module.compile_context(request(), platform_fixture(), current, turns, required)
        second = self.module.compile_context(request(), platform_fixture(), copy.deepcopy(current), copy.deepcopy(turns), copy.deepcopy(required))
        self.assertEqual(first, second)
        self.assertEqual(first['status'], 'ready')
        self.assertEqual(first['content']['required_inputs'], required)
        self.assertIn('artifact-1', first['package']['rehydration_refs'])
        self.assertEqual(first['audit']['rehydration_refs'], ['artifact-1'])
        validate(first['package'], json.loads((SCHEMAS / 'context-package.schema.json').read_text()))
        validate(first['audit'], json.loads((SCHEMAS / 'context-audit.schema.json').read_text()))

    def test_serialized_emitted_collections_and_total_stay_within_budget(self):
        current = state(lessons=[lesson(1, rule='x')],
            episodes=[episode(1, summary='y')])
        turns = [{'ref': 'turn-1', 'content': 'z', 'topics': [], 'entities': [],
            'mandatory': False, 'requires_exact': False}]
        required = [{'ref': 'input-1', 'content': 'q', 'requires_exact': False}]
        limits = {'policy': 100, 'capsule': 10, 'lessons': 20, 'episodes': 30,
            'recent_turns': 30, 'total': 100}
        result = self.module.compile_context(
            request(), platform_fixture(), current, turns, required, limits)
        content = result['content']
        estimates = result['package']['component_token_estimates']
        self.assertEqual(estimates['policy'],
            self.module._serialized_tokens(content['policy_refs']))
        self.assertEqual(estimates['capsule'], 0)
        self.assertEqual(estimates['lessons'],
            self.module._serialized_tokens(content['lessons']))
        self.assertEqual(estimates['episodes'],
            self.module._serialized_tokens(content['episodes']))
        self.assertEqual(estimates['recent_turns'],
            self.module._serialized_tokens(content['recent_turns']))
        self.assertEqual(result['package']['total_estimated_tokens'],
            self.module._serialized_tokens(self.module._historical_content(content)))
        self.assertEqual(result['package']['required_input_token_estimate'],
            self.module._serialized_tokens(content['required_inputs']))
        self.assertLessEqual(estimates['lessons'], limits['lessons'])
        self.assertLessEqual(estimates['episodes'], limits['episodes'])
        self.assertLessEqual(estimates['recent_turns'], limits['recent_turns'])
        self.assertLessEqual(result['package']['total_estimated_tokens'], limits['total'])

    def test_required_inputs_use_separate_task_budget(self):
        required = [{'ref': 'source-document', 'content': 'x' * 3000,
            'requires_exact': True}]
        result = self.module.compile_context(request(), platform_fixture(),
            state(), [], required)
        self.assertEqual(result['status'], 'ready')
        self.assertEqual(result['package']['required_input_refs'], ['source-document'])
        self.assertGreater(result['package']['required_input_token_estimate'], 900)
        self.assertLessEqual(result['package']['total_estimated_tokens'],
            sum(self.module.NORMAL_LIMITS.values()))

        blocked = self.module.compile_context(request(), platform_fixture(),
            state(), [], required, {'required_inputs': 100})
        self.assertEqual(blocked['status'], 'blocked')
        self.assertEqual(blocked['blocker'], {
            'code': 'required-input-overflow', 'refs': ['source-document']})

    def test_fixed_collection_overhead_cannot_be_ready_over_component_caps(self):
        limits = {'policy': 100, 'capsule': 0, 'lessons': 0, 'episodes': 0,
            'recent_turns': 0, 'total': 100}
        result = self.module.compile_context(
            request(), platform_fixture(), state(), [], [], limits)
        self.assertEqual(result['status'], 'blocked')
        self.assertEqual(result['blocker']['code'], 'mandatory-content-overflow')
        self.assertEqual(result['blocker']['refs'], [
            'episodes:fixed-overhead', 'lessons:fixed-overhead',
            'recent_turns:fixed-overhead'])

    def test_required_evidence_is_preserved_or_explicitly_blocked(self):
        unavailable = self.module.compile_context(
            request(required_evidence_refs=['missing-source']),
            platform_fixture(), state(), [], [])
        self.assertEqual(unavailable['status'], 'blocked')
        self.assertEqual(unavailable['blocker'], {
            'code': 'required-evidence-unavailable', 'refs': ['missing-source']})
        self.assertEqual(unavailable['package']['rehydration_refs'], ['missing-source'])

        retrievable_platform = platform_fixture()
        retrievable_platform['conversation_context']['transcript_retrieval'] = True
        retrievable_platform['conversation_context']['original_turn_rehydration'] = True
        retrievable = self.module.compile_context(
            request(required_evidence_refs=['remote-source']),
            retrievable_platform, state(), [], [])
        self.assertEqual(retrievable['status'], 'ready')
        self.assertEqual(retrievable['package']['rehydration_refs'], ['remote-source'])

    def test_optional_eviction_removes_episode_before_recent_turn_and_lesson(self):
        current = state(lessons=[lesson(1, rule='keep lesson')],
            episodes=[episode(1, summary='drop episode')])
        turns = [{'ref': 'turn-1', 'content': 'keep recent', 'topics': ['backup'],
            'entities': [], 'mandatory': False, 'requires_exact': False}]
        limits = {'policy': 100, 'capsule': 10, 'lessons': 100, 'episodes': 100,
            'recent_turns': 100, 'total': 100}
        result = self.module.compile_context(request(), platform_fixture(), current, turns, [], limits)
        self.assertEqual(result['status'], 'ready')
        self.assertEqual(result['package']['selected_episode_ids'], [])
        self.assertEqual(result['package']['selected_recent_turn_refs'], ['turn-1'])
        self.assertEqual(result['package']['selected_lesson_ids'], ['lesson-1'])
        self.assertIn({'ref': 'episode-1', 'reason_code': 'budget'}, result['package']['omissions'])

    def test_mandatory_item_overflow_returns_capacity_blocker(self):
        turns = [{'ref': 'turn-required', 'content': 'x' * 100, 'topics': [],
            'entities': [], 'mandatory': True, 'requires_exact': True}]
        limits = {'policy': 100, 'capsule': 10, 'lessons': 10, 'episodes': 100,
            'recent_turns': 2, 'total': 100}
        result = self.module.compile_context(request(), platform_fixture(), state(), turns, [], limits)
        self.assertEqual(result['status'], 'blocked')
        self.assertEqual(result['blocker']['code'], 'mandatory-content-overflow')
        self.assertEqual(result['blocker']['refs'], ['turn-required'])
        self.assertNotIn('content', result['audit'])

    def test_full_context_uses_maxima_and_marks_rehydration(self):
        full = request(full_context=True, required_evidence_refs=['turn-1'])
        turns = [{'ref': 'turn-1', 'content': 'exact wording', 'topics': [],
            'entities': [], 'mandatory': False, 'requires_exact': False}]
        result = self.module.compile_context(full, platform_fixture(), state(), turns, [])
        self.assertEqual(result['limits'], self.module.MAX_LIMITS)
        self.assertEqual(result['package']['budget_status'], 'max-budget')
        self.assertEqual(result['package']['rehydration_refs'], ['turn-1'])

    def test_json_cli(self):
        payload = {'request': request(), 'platform': platform_fixture(), 'state': state(),
            'recent_turns': [], 'required_inputs': []}
        result = subprocess.run([sys.executable, str(SCRIPT)], input=json.dumps(payload),
            text=True, capture_output=True)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, '')
        self.assertEqual(json.loads(result.stdout)['status'], 'ready')
        invalid = subprocess.run([sys.executable, str(SCRIPT)], input='{private-invalid',
            text=True, capture_output=True)
        self.assertEqual(invalid.returncode, 2)
        self.assertEqual(invalid.stderr, '')
        self.assertNotIn('private-invalid', invalid.stdout)


if __name__ == '__main__':
    unittest.main()
