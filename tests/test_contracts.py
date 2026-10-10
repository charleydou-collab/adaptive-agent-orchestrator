"""Canonical contract tests; stdlib validator for the schema vocabulary used here.

This deliberately is not a general JSON Schema implementation. Cross-document
execution compatibility is checked separately from structural validation.
"""
import copy
import json
from pathlib import Path
import re
import unittest

SCHEMAS = Path(__file__).resolve().parents[1] / 'core/adaptive-agent-orchestrator/schemas'
ROOT = Path(__file__).resolve().parents[1]
NAMES = (
    'platform-capabilities',
    'model-registry',
    'task-contract',
    'completion-report',
    'clarification-request',
    'clarification-response',
    'ledger-event',
    'conversation-scope',
    'chat-state-capsule',
    'learning-candidate',
    'chat-lesson',
    'episode-summary',
    'retrieval-request',
    'context-package',
    'context-audit',
    'learning-reset-request',
)


def json_equal(left, right):
    """Compare JSON values without Python's bool/int equality shortcut."""
    return json.dumps(left, sort_keys=True, separators=(',', ':')) == json.dumps(
        right, sort_keys=True, separators=(',', ':'))


def validate(value, schema, root=None):
    root = root or schema
    if '$ref' in schema:
        ref = schema['$ref']
        if ref.startswith('#/'):
            target = root
            for part in ref[2:].split('/'):
                target = target[part]
            validate(value, target, root)
        else:
            validate(value, json.loads((SCHEMAS / ref).read_text()))
        return
    kinds = {'object': dict, 'array': list, 'string': str, 'boolean': bool, 'integer': int, 'number': (int, float), 'null': type(None)}
    if 'type' in schema:
        allowed = schema['type'] if isinstance(schema['type'], list) else [schema['type']]
        assert any(isinstance(value, kinds[kind]) and not (kind in ('integer', 'number') and isinstance(value, bool)) for kind in allowed), 'type'
    if 'enum' in schema:
        assert any(json_equal(value, candidate) for candidate in schema['enum']), 'enum'
    if 'const' in schema:
        assert json_equal(value, schema['const']), 'const'
    if isinstance(value, dict):
        assert all(k in value for k in schema.get('required', [])), 'required'
        props = schema.get('properties', {})
        if schema.get('additionalProperties') is False:
            assert not set(value) - set(props), 'additionalProperties'
        for key, item in value.items():
            if key in props:
                validate(item, props[key], root)
    if isinstance(value, list):
        assert len(value) >= schema.get('minItems', 0), 'minItems'
        assert len(value) <= schema.get('maxItems', float('inf')), 'maxItems'
        if schema.get('uniqueItems'):
            assert len({json.dumps(x, sort_keys=True) for x in value}) == len(value), 'uniqueItems'
        for item in value:
            validate(item, schema.get('items', {}), root)
    if isinstance(value, str):
        assert len(value) >= schema.get('minLength', 0), 'minLength'
        assert len(value) <= schema.get('maxLength', float('inf')), 'maxLength'
        if 'pattern' in schema:
            assert re.search(schema['pattern'], value), 'pattern'
    if isinstance(value, (float, int)) and not isinstance(value, bool):
        assert value >= schema.get('minimum', -float('inf')), 'minimum'
        assert value <= schema.get('maximum', float('inf')), 'maximum'
    for child in schema.get('allOf', []):
        validate(value, child, root)
    if 'if' in schema:
        try:
            validate(value, schema['if'], root)
        except AssertionError:
            validate(value, schema.get('else', {}), root)
        else:
            validate(value, schema.get('then', {}), root)


def registry():
    return {'models': [{'provider': 'vendor-a', 'model_id': 'opaque-7', 'version': '1',
        'capability_tiers': ['balanced'], 'capabilities': ['analysis'], 'cost_class': 'low',
        'approval_policy': 'none',
        'context_window': 32000, 'modalities': ['text'], 'tools': ['read'],
        'supported_efforts': ['normal'], 'reasoning_mapping': {'minimal': 'normal', 'standard': 'normal', 'deep': None},
        'availability': 'available'}]}


def platform():
    return {'platform': 'platform-a', 'adapter_version': '1',
        'models': {'discovery': 'static', 'registry': registry()},
        'delegation': {'supported': False, 'max_concurrency': 1, 'per_worker_model_selection': False, 'fallback_mode': 'role-simulation'},
        'reasoning_effort': {'supported_values': ['normal']}, 'tools': ['read'], 'modalities': ['text'],
        'persistence': {'ledger_supported': False, 'scope': 'none'},
        'conversation_context': {'stable_identity': False, 'persistence_supported': False,
            'transcript_retrieval': False, 'message_list_control': False,
            'token_estimation': False, 'context_compilation': False,
            'original_turn_rehydration': False, 'deletion_event_support': False,
            'learning_scope': 'none', 'scope': 'none'},
        'activation': {'mode': 'explicit-invocation', 'guaranteed': False}}


def contract():
    return {'task_id': 'task-1', 'agent_identity': 'researcher-1',
        'role': {'title': 'Researcher', 'mission': 'Check evidence', 'expertise': ['analysis']},
        'responsibilities': ['Verify claims'], 'boundaries': ['No publication'], 'objective': 'Summarize sources',
        'inputs': ['source-ref'], 'expected_deliverable': 'summary-ref',
        'quality_kpis': [{'id': 'accuracy', 'description': 'All claims supported', 'target': '100%'}],
        'acceptance_criteria': ['All KPIs pass'], 'constraints': ['Use supplied sources'],
        'available_tools': ['read'], 'evidence_requirements': ['Source references'],
        'execution_requirements': {'capability_tier': 'balanced', 'minimum_context': 8000,
            'modalities': ['text'], 'required_tools': ['read'], 'minimum_reasoning_class': 'standard'},
        'resolved_execution': {'provider': 'vendor-a', 'model_id': 'opaque-7', 'effort': 'normal',
            'worker_mode': 'role-simulation', 'adapter': 'adapter-a', 'resolution_timestamp': '2026-10-07T00:00:00Z'},
        'completion_report_schema': 'completion-report.schema.json'}


def report():
    return {'status': 'complete', 'deliverable': 'summary-ref',
        'kpi_results': [{'kpi_id': 'accuracy', 'outcome': 'pass', 'evidence_refs': ['evidence-1']}],
        'evidence': ['evidence-1'], 'uncertainties': [], 'blockers': [],
        'escalation_recommendation': {'recommended': False, 'reason': 'Accepted'}}


def clarification_request():
    return {
        'request_id': 'clarify-1',
        'task_id': 'task-1',
        'question': 'Which reporting calendar should govern the summary?',
        'why_needed': 'Fiscal-year and calendar-year interpretations change the totals.',
        'blocked_scope': 'The year-over-year comparison is paused; source inventory can continue.',
        'options': [
            {'option_id': 'fiscal', 'label': 'Fiscal year',
             'description': 'Use the organization-defined fiscal-year boundaries.'},
            {'option_id': 'calendar', 'label': 'Calendar year',
             'description': 'Use January through December boundaries.'},
        ],
        'recommended_option_id': 'fiscal',
        'custom_response_allowed': True,
        'safe_assumption': {
            'available': True,
            'value': 'Use the fiscal year stated in the source document.',
            'risk': 'The result may not match a calendar-year comparison.',
        },
    }


def clarification_response():
    return {
        'request_id': 'clarify-1',
        'task_id': 'task-1',
        'selected_option_id': 'fiscal',
        'custom_response': None,
        'answer_text': 'Use the fiscal year stated in the source document.',
        'answered_by': 'user',
        'answered_at': '2026-10-08T00:00:00Z',
    }


def event():
    return {'event_id': 'event-1', 'task_id': 'task-1', 'adapter': 'adapter-a', 'platform': 'platform-a',
        'agent_identity': 'researcher-1', 'archetype': 'researcher', 'role': 'Researcher', 'task_category': 'research',
        'capability_tier': 'balanced', 'abstract_effort': 'standard',
        'execution_fingerprint': {'provider': 'vendor-a', 'model_id': 'opaque-7', 'version': '1',
            'tools': ['read'], 'modalities': ['text'], 'effort': 'normal', 'effort_mapping': 'standard=normal'},
        'kpi_outcome': 'pass', 'verified': True, 'evidence_refs': ['evidence-1'],
        'delta': 2, 'reason': 'Verified first-pass compliance', 'score_update_mode': 'apply',
        'timestamp': '2026-10-07T00:00:00Z'}


def conversation_scope():
    return {'adapter': 'adapter-a', 'conversation_id': 'conversation-opaque-1',
        'persistence_class': 'session', 'storage_ref': 'store-ref-1'}


def capsule():
    return {'conversation_key': 'conversation-key-1', 'revision': 2,
        'objectives': [{'text': 'Produce concise, sourced answers', 'source_refs': ['turn-1']}],
        'decisions': [], 'constraints': [{'text': 'Keep learning chat-scoped', 'source_refs': ['turn-2']}],
        'open_questions': [], 'accepted_facts': [], 'active_preferences': [],
        'artifact_refs': ['artifact-1'], 'updated_at': '2026-10-10T00:00:00Z'}


def candidate():
    return {'candidate_id': 'candidate-1', 'conversation_key': 'conversation-key-1',
        'rule': 'Prefer concise answers unless detail is requested.', 'category': 'preference',
        'task_categories': ['general'], 'role_targets': ['management'],
        'conditions': ['The user has not requested a detailed explanation.'], 'exceptions': [],
        'source_refs': ['turn-3'], 'confidence_class': 'explicit', 'risk_class': 'low',
        'verified': True, 'created_at': '2026-10-10T00:00:00Z'}


def lesson():
    value = candidate()
    value.pop('candidate_id')
    value.update({'lesson_id': 'lesson-1', 'status': 'active', 'version': 1,
        'supersedes': None, 'expires_at': None, 'updated_at': '2026-10-10T00:00:00Z'})
    return value


def episode():
    return {'episode_id': 'episode-1', 'conversation_key': 'conversation-key-1',
        'task_id': 'task-1', 'task_category': 'research', 'role_targets': ['management'],
        'topics': ['backup'], 'entities': ['company documents'], 'outcome': 'accepted',
        'decision_refs': ['decision-1'], 'lesson_ids': ['lesson-1'], 'source_refs': ['turn-1'],
        'summary': 'Compared three backup approaches and accepted the hybrid recommendation.',
        'completed_at': '2026-10-10T00:00:00Z'}


def retrieval_request():
    return {'conversation_key': 'conversation-key-1', 'task_id': 'task-2',
        'task_category': 'research', 'role': 'management', 'topics': ['backup'],
        'entities': ['company documents'], 'required_evidence_refs': ['artifact-1'],
        'applicability_facts': ['The user has not requested a detailed explanation.'],
        'lesson_limit': 5, 'episode_limit': 3, 'full_context': False}


def context_package():
    return {'package_id': 'context-1', 'conversation_key': 'conversation-key-1',
        'audience': 'management', 'task_id': 'task-2', 'capsule_ref': 'capsule:2',
        'selected_lesson_ids': ['lesson-1'], 'selected_episode_ids': ['episode-1'],
        'selected_recent_turn_refs': ['turn-4'], 'required_input_refs': ['artifact-1'],
        'omissions': [{'ref': 'episode-older', 'reason_code': 'budget'}],
        'component_token_estimates': {'policy': 300, 'capsule': 200, 'lessons': 80,
            'episodes': 120, 'recent_turns': 250}, 'total_estimated_tokens': 950,
        'required_input_token_estimate': 125, 'required_input_limit': 8000,
        'estimate_quality': 'approximate', 'budget_status': 'within-budget',
        'rehydration_refs': [], 'created_at': '2026-10-10T00:00:00Z'}


def context_audit():
    value = context_package()
    value.pop('audience')
    value.pop('capsule_ref')
    value.pop('required_input_refs')
    value.pop('created_at')
    value['fallback_reasons'] = []
    return value


def reset_request():
    return {'request_id': 'reset-1', 'conversation_key': 'conversation-key-1',
        'operation': 'reset', 'confirm': True, 'requested_at': '2026-10-10T00:00:00Z'}


def compatible(task, models):
    resolved, needs = task['resolved_execution'], task['execution_requirements']
    return any(m['availability'] == 'available' and m['provider'] == resolved['provider']
        and m['model_id'] == resolved['model_id'] and needs['capability_tier'] in m['capability_tiers']
        and m['context_window'] >= needs['minimum_context']
        and set(needs['modalities']) <= set(m['modalities']) and set(needs['required_tools']) <= set(m['tools'])
        and resolved['effort'] in m['supported_efforts']
        and m['reasoning_mapping'][needs['minimum_reasoning_class']] == resolved['effort'] for m in models['models'])


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.schemas = {name: json.loads((SCHEMAS / (name + '.schema.json')).read_text()) for name in NAMES}

    def check(self, name, value):
        validate(value, self.schemas[name])

    def test_dialect_and_neutrality(self):
        for schema in self.schemas.values():
            self.assertEqual(schema['$schema'], 'https://json-schema.org/draft/2020-12/schema')
            text = json.dumps(schema).lower()
            for token in ('gpt-', 'claude-', 'gemini-', 'spawn_agent', 'mcp__', '/' + 'users/', '/' + 'home/', '~/', 'c:\\'):
                self.assertNotIn(token, text)

    def test_retrieval_request_has_finite_input_bounds(self):
        schema = self.schemas['retrieval-request']
        properties = schema['properties']
        for field in ('conversation_key', 'task_id', 'task_category', 'role'):
            self.assertGreater(properties[field]['maxLength'], 0)
        for field in ('topics', 'entities', 'required_evidence_refs', 'applicability_facts'):
            self.assertGreater(properties[field]['maxItems'], 0)
            self.assertGreater(properties[field]['items']['maxLength'], 0)
        self.assertEqual(properties['lesson_limit']['maximum'], 5)
        self.assertEqual(properties['episode_limit']['maximum'], 20)

        boundary = retrieval_request()
        boundary['topics'] = ['topic'] * (properties['topics']['maxItems'] + 1)
        with self.assertRaisesRegex(AssertionError, 'maxItems'):
            self.check('retrieval-request', boundary)
        boundary = retrieval_request()
        boundary['task_id'] = 'x' * (properties['task_id']['maxLength'] + 1)
        with self.assertRaisesRegex(AssertionError, 'maxLength'):
            self.check('retrieval-request', boundary)

    def test_valid_examples_and_required_fields(self):
        values = (
            platform(), registry(), contract(), report(), clarification_request(),
            clarification_response(), event(), conversation_scope(), capsule(), candidate(),
            lesson(), episode(), retrieval_request(), context_package(), context_audit(),
            reset_request(),
        )
        for name, value in zip(NAMES, values):
            self.check(name, value)
            for key in self.schemas[name]['required']:
                broken = copy.deepcopy(value)
                del broken[key]
                with self.assertRaises(AssertionError, msg=f'{name}: {key}'):
                    self.check(name, broken)

    def test_chat_contracts_are_closed_and_provider_neutral(self):
        samples = {
            'conversation-scope': conversation_scope(), 'chat-state-capsule': capsule(),
            'learning-candidate': candidate(), 'chat-lesson': lesson(),
            'episode-summary': episode(), 'retrieval-request': retrieval_request(),
            'context-package': context_package(), 'context-audit': context_audit(),
            'learning-reset-request': reset_request(),
        }
        for name, value in samples.items():
            with self.subTest(name=name):
                self.check(name, value)
                invalid = copy.deepcopy(value)
                invalid['unknown_field'] = 'not allowed'
                with self.assertRaises(AssertionError):
                    self.check(name, invalid)
                serialized = json.dumps(self.schemas[name]).lower()
                for token in ('gpt-', 'claude-', 'gemini-', 'mcp__', 'spawn_agent'):
                    self.assertNotIn(token, serialized)

    def test_chat_contracts_reject_sensitive_payload_fields(self):
        for name, value in (
                ('learning-candidate', candidate()), ('chat-lesson', lesson()),
                ('episode-summary', episode()), ('context-audit', context_audit())):
            for field in ('prompt', 'transcript', 'full_output', 'source_documents'):
                invalid = copy.deepcopy(value)
                invalid[field] = 'private content'
                with self.assertRaises(AssertionError, msg=f'{name}: {field}'):
                    self.check(name, invalid)

    def test_persisted_chat_contracts_have_enforced_size_bounds(self):
        for name, value, text_field, collection_field in (
                ('chat-state-capsule', capsule(), ('objectives', 0, 'text'), 'objectives'),
                ('learning-candidate', candidate(), ('rule',), 'source_refs'),
                ('chat-lesson', lesson(), ('rule',), 'source_refs'),
                ('episode-summary', episode(), ('summary',), 'source_refs')):
            schema = self.schemas[name]
            with self.subTest(name=name, boundary='text'):
                target = schema['properties']
                for part in text_field:
                    if isinstance(part, int):
                        target = target['items']
                    elif part == 'text' and '$ref' in target:
                        target = schema['$defs']['entry']['properties']['text']
                    else:
                        target = target[part] if part in target else target['properties'][part]
                self.assertIn('maxLength', target)
                invalid = copy.deepcopy(value)
                if name == 'chat-state-capsule':
                    invalid['objectives'][0]['text'] = 'x' * (target['maxLength'] + 1)
                elif name in ('learning-candidate', 'chat-lesson'):
                    invalid['rule'] = 'x' * (target['maxLength'] + 1)
                else:
                    invalid['summary'] = 'x' * (target['maxLength'] + 1)
                with self.assertRaises(AssertionError):
                    self.check(name, invalid)
            with self.subTest(name=name, boundary='collection'):
                collection = schema['properties'][collection_field]
                self.assertIn('maxItems', collection)
                invalid = copy.deepcopy(value)
                invalid[collection_field] = [f'ref-{index}' for index in range(collection['maxItems'] + 1)]
                if name == 'chat-state-capsule':
                    invalid[collection_field] = [
                        {'text': f'item-{index}', 'source_refs': [f'ref-{index}']}
                        for index in range(collection['maxItems'] + 1)]
                with self.assertRaises(AssertionError):
                    self.check(name, invalid)

    def test_platform_context_capabilities_are_coherent(self):
        value = platform()
        self.check('platform-capabilities', value)
        invalid = copy.deepcopy(value)
        invalid['conversation_context']['scope'] = 'session'
        with self.assertRaises(AssertionError):
            self.check('platform-capabilities', invalid)
        supported = copy.deepcopy(value)
        supported['conversation_context'] = {'stable_identity': True,
            'persistence_supported': True, 'transcript_retrieval': True,
            'message_list_control': False, 'token_estimation': True,
            'context_compilation': True, 'original_turn_rehydration': True,
            'deletion_event_support': True, 'learning_scope': 'session', 'scope': 'session'}
        self.check('platform-capabilities', supported)
        for field in ('scope', 'learning_scope'):
            workspace = copy.deepcopy(supported)
            workspace['conversation_context'][field] = 'workspace'
            with self.assertRaises(AssertionError, msg=field):
                self.check('platform-capabilities', workspace)

    def test_v013_contracts_remain_valid(self):
        self.check('task-contract', contract())
        self.check('completion-report', report())

    def test_task_accepts_compiled_context_references(self):
        value = contract()
        value['context_package_ref'] = 'context-1'
        value['applicable_lesson_ids'] = ['lesson-1']
        self.check('task-contract', value)

    def test_report_accepts_candidates_without_activating_them(self):
        value = report()
        value['learning_candidates'] = [candidate()]
        self.check('completion-report', value)
        self.assertNotIn('status', value['learning_candidates'][0])

    def test_needs_input_report_requires_structured_clarification(self):
        value = report()
        value['status'] = 'needs-input'
        value['deliverable'] = None
        value['clarification_request'] = clarification_request()
        self.check('completion-report', value)

        missing = copy.deepcopy(value)
        del missing['clarification_request']
        with self.assertRaises(AssertionError):
            self.check('completion-report', missing)

    def test_clarification_request_requires_choices_recommendation_and_custom_response(self):
        value = clarification_request()
        self.check('clarification-request', value)

        for mutation in ('too-few-options', 'no-recommendation', 'no-custom-response'):
            broken = copy.deepcopy(value)
            if mutation == 'too-few-options':
                broken['options'] = broken['options'][:1]
            elif mutation == 'no-recommendation':
                del broken['recommended_option_id']
            else:
                broken['custom_response_allowed'] = False
            with self.assertRaises(AssertionError, msg=mutation):
                self.check('clarification-request', broken)

    def test_answer_can_be_routed_back_to_original_task(self):
        value = contract()
        value['clarification_responses'] = [clarification_response()]
        self.check('task-contract', value)

        mismatched = copy.deepcopy(value)
        mismatched['clarification_responses'][0]['task_id'] = 'different-task'
        self.check('task-contract', mismatched)  # Structurally valid; management validates correlation.
        self.assertNotEqual(
            mismatched['task_id'], mismatched['clarification_responses'][0]['task_id'])

    def test_checked_in_platform_declarations_match_schema(self):
        paths = (
            ROOT / 'adapters/codex/platform-capabilities.yaml',
            ROOT / 'adapters/chatgpt-web/platform-capabilities.yaml',
            ROOT / 'adapters/generic-prompt/platform-capabilities.example.yaml',
        )
        for path in paths:
            with self.subTest(path=path):
                self.check('platform-capabilities', json.loads(path.read_text(encoding='utf-8')))

    def test_codex_registry_example_matches_schema(self):
        path = ROOT / 'adapters/codex/model-registry.example.json'
        self.check('model-registry', json.loads(path.read_text(encoding='utf-8')))

    def test_model_rename_and_unavailability(self):
        models, task = registry(), contract()
        self.assertTrue(compatible(task, models))
        models['models'][0]['model_id'] = 'completely-unrelated-label'
        self.check('model-registry', models)
        self.assertFalse(compatible(task, models))
        task['resolved_execution']['model_id'] = 'completely-unrelated-label'
        self.assertTrue(compatible(task, models))
        models['models'][0]['availability'] = 'unavailable'
        self.check('model-registry', models)
        self.assertFalse(compatible(task, models))

    def test_premium_registry_policy_is_explicit_and_high_cost_is_gated(self):
        models = registry()
        self.check('model-registry', models)
        models['models'][0]['cost_class'] = 'high'
        with self.assertRaises(AssertionError):
            self.check('model-registry', models)
        models['models'][0]['approval_policy'] = 'explicit-user-approval'
        self.check('model-registry', models)
        del models['models'][0]['approval_policy']
        with self.assertRaises(AssertionError):
            self.check('model-registry', models)

    def test_unsupported_effort(self):
        task = contract()
        task['resolved_execution']['effort'] = 'unsupported'
        self.check('task-contract', task)  # Adapter values remain opaque in the portable schema.
        self.assertFalse(compatible(task, registry()))
        task['execution_requirements']['minimum_reasoning_class'] = 'unsupported'
        with self.assertRaises(AssertionError):
            self.check('task-contract', task)

    def test_no_subagent_declaration(self):
        value = platform()
        self.check('platform-capabilities', value)
        for key, invalid in [('max_concurrency', 3), ('per_worker_model_selection', True), ('fallback_mode', 'native-parallel')]:
            bad = copy.deepcopy(value)
            bad['delegation'][key] = invalid
            with self.assertRaises(AssertionError):
                self.check('platform-capabilities', bad)

    def test_no_persistence_declaration(self):
        value = platform()
        self.check('platform-capabilities', value)
        value['persistence']['scope'] = 'durable'
        with self.assertRaises(AssertionError):
            self.check('platform-capabilities', value)
        value['persistence'] = {'ledger_supported': True, 'scope': 'session'}
        self.check('platform-capabilities', value)

    def test_task_identity_across_adapters(self):
        first, second = contract(), contract()
        second['resolved_execution'].update(adapter='adapter-b', model_id='different', effort='medium')
        for value in (first, second):
            self.check('task-contract', value)
        first.pop('resolved_execution')
        second.pop('resolved_execution')
        self.assertEqual(first, second)
        self.check('task-contract', first)  # The portable contract exists before dispatch.

    def test_nested_requirements(self):
        for name, sample, key in [('model-registry', registry(), 'models'), ('task-contract', contract(), 'execution_requirements'), ('ledger-event', event(), 'execution_fingerprint')]:
            if key == 'models':
                sample[key][0].pop('capability_tiers')
            else:
                sample[key].clear()
            with self.assertRaises(AssertionError):
                self.check(name, sample)

    def test_ledger_rejects_sensitive_fields(self):
        for field in ('prompt', 'full_prompt', 'source_documents', 'documents', 'full_output', 'output'):
            for nested in (False, True):
                value = event()
                target = value['execution_fingerprint'] if nested else value
                target[field] = 'private content'
                with self.assertRaises(AssertionError):
                    self.check('ledger-event', value)

    def test_verified_score_delta(self):
        value = event()
        value['verified'] = False
        with self.assertRaises(AssertionError):
            self.check('ledger-event', value)
        value['verified'] = 1
        with self.assertRaises(AssertionError):
            self.check('ledger-event', value)
        value['verified'] = True
        value['evidence_refs'] = []
        with self.assertRaises(AssertionError):
            self.check('ledger-event', value)
        value = event()
        value['score_update_mode'] = 'freeze'
        self.check('ledger-event', value)


if __name__ == '__main__':
    unittest.main()
