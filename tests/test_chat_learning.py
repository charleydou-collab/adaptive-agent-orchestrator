"""Policy checks for chat-scoped feedback learning."""
import copy
import importlib.util
from pathlib import Path
import unittest

from tests.test_contracts import candidate as candidate_fixture

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / 'core/adaptive-agent-orchestrator/scripts/chat_learning.py'


def candidate(**updates):
    value = candidate_fixture()
    value.update(updates)
    return value


def state(conversation_key='conversation-key-1', lessons=None):
    return {'scope': {'adapter': 'adapter-a', 'conversation_id': 'conversation-1'},
        'conversation_key': conversation_key, 'lessons': list(lessons or [])}


def active_lesson(**updates):
    value = candidate()
    value.pop('candidate_id')
    value.update({'lesson_id': 'lesson-old', 'status': 'active', 'version': 1,
        'supersedes': None, 'expires_at': None,
        'updated_at': '2026-10-09T00:00:00Z'})
    value.update(updates)
    return value


class ChatLearningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location('chat_learning', MODULE)
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)

    def test_explicit_low_risk_instruction_activates_automatically(self):
        decision = self.module.activation_decision(candidate(), [], 1)
        self.assertEqual(decision, {'action': 'activate', 'status': 'active',
            'reason_code': 'explicit-low-risk', 'requires_confirmation': False,
            'conflicting_lesson_ids': []})

    def test_factual_correction_requires_verified_evidence(self):
        proposed = candidate(category='factual-correction', confidence_class='explicit', verified=False)
        decision = self.module.activation_decision(proposed, [], 1)
        self.assertEqual(decision['status'], 'proposed')
        self.assertEqual(decision['reason_code'], 'evidence-required')
        self.assertFalse(decision['requires_confirmation'])
        proposed['verified'] = True
        decision = self.module.activation_decision(proposed, [], 1)
        self.assertEqual(decision['status'], 'active')
        self.assertEqual(decision['reason_code'], 'verified-factual-correction')

    def test_repeated_preference_requires_two_events(self):
        value = candidate(confidence_class='repeated')
        self.assertEqual(self.module.activation_decision(value, [], 1)['status'], 'proposed')
        decision = self.module.activation_decision(value, [], 2)
        self.assertEqual(decision['status'], 'active')
        self.assertEqual(decision['reason_code'], 'repeated-preference')

    def test_one_off_inference_and_high_impact_require_confirmation(self):
        inferred = self.module.activation_decision(candidate(confidence_class='inferred'), [], 1)
        self.assertEqual(inferred['status'], 'proposed')
        self.assertTrue(inferred['requires_confirmation'])
        high = self.module.activation_decision(candidate(risk_class='high'), [], 9)
        self.assertEqual(high['status'], 'proposed')
        self.assertEqual(high['reason_code'], 'high-impact-confirmation')
        self.assertTrue(high['requires_confirmation'])

    def test_worker_identity_and_score_cannot_activate(self):
        for field in ('agent_score', 'worker_identity', 'score_event'):
            value = candidate(confidence_class='inferred')
            value[field] = 200
            with self.assertRaises(ValueError):
                self.module.activation_decision(value, [], 99)

    def test_exact_conversation_matching_for_conflicts_and_application(self):
        other = active_lesson(conversation_key='other-conversation')
        decision = self.module.activation_decision(candidate(), [other], 1)
        self.assertEqual(decision['conflicting_lesson_ids'], [])
        with self.assertRaises(ValueError):
            self.module.apply_candidate(state('other-conversation'), candidate(), decision)

    def test_newest_verified_rule_supersedes_conflicting_active_rule(self):
        old = active_lesson(rule='Use a long answer.')
        value = candidate(candidate_id='candidate-new', rule='Use a concise answer.', verified=True)
        decision = self.module.activation_decision(value, [old], 1)
        self.assertEqual(decision['conflicting_lesson_ids'], ['lesson-old'])
        target = state(lessons=[old])
        lesson_id = self.module.apply_candidate(target, value, decision)
        self.assertEqual(lesson_id, 'lesson-candidate-new')
        self.assertEqual(target['lessons'][0]['status'], 'superseded')
        newest = target['lessons'][1]
        self.assertEqual(newest['status'], 'active')
        self.assertEqual(newest['version'], 2)
        self.assertEqual(newest['supersedes'], 'lesson-old')
        self.assertEqual([item['lesson_id'] for item in target['lessons'] if item['status'] == 'active'], [lesson_id])

    def test_unconfirmed_conflict_disputes_old_rule(self):
        old = active_lesson(rule='Use a long answer.')
        value = candidate(candidate_id='candidate-new', rule='Use a concise answer.',
            confidence_class='inferred', verified=False)
        decision = self.module.activation_decision(value, [old], 1)
        target = state(lessons=[old])
        self.module.apply_candidate(target, value, decision)
        self.assertEqual(target['lessons'][0]['status'], 'disputed')
        self.assertEqual(target['lessons'][1]['status'], 'proposed')

    def test_forgetting_and_expiration(self):
        lessons = [active_lesson(lesson_id='forget-me'),
            active_lesson(lesson_id='expired', expires_at='2026-10-09T00:00:00Z'),
            active_lesson(lesson_id='future', expires_at='2026-10-11T00:00:00Z')]
        target = state(lessons=lessons)
        self.module.forget_lesson(target, 'forget-me')
        self.assertEqual(target['lessons'][0]['status'], 'forgotten')
        expired = self.module.expire_lessons(target, '2026-10-10T00:00:00Z')
        self.assertEqual(expired, ['expired'])
        self.assertEqual(target['lessons'][1]['status'], 'expired')
        self.assertEqual(target['lessons'][2]['status'], 'active')
        with self.assertRaises(ValueError):
            self.module.forget_lesson(target, 'missing')

    def test_confirmed_activation_rechecks_conflicts_and_updates_audit_fields(self):
        proposed = active_lesson(lesson_id='lesson-proposed', status='proposed',
            rule='Use a concise answer.', version=1, verified=False)
        conflicting = active_lesson(lesson_id='lesson-current', rule='Use a long answer.',
            version=3)
        target = state(lessons=[conflicting, proposed])
        self.module.activate_lesson(
            target, 'lesson-proposed', '2026-10-10T01:02:03Z')
        self.assertEqual(conflicting['status'], 'superseded')
        self.assertEqual(conflicting['updated_at'], '2026-10-10T01:02:03Z')
        self.assertEqual(proposed['status'], 'active')
        self.assertEqual(proposed['version'], 4)
        self.assertEqual(proposed['supersedes'], 'lesson-current')
        self.assertEqual(proposed['updated_at'], '2026-10-10T01:02:03Z')

    def test_decision_contains_no_feedback_or_prompt_content(self):
        decision = self.module.activation_decision(candidate(), [], 1)
        serialized = str(decision).lower()
        for token in ('prompt', 'feedback', 'full_output', 'source_documents'):
            self.assertNotIn(token, serialized)


if __name__ == '__main__':
    unittest.main()
