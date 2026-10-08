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
NAMES = ('platform-capabilities', 'model-registry', 'task-contract', 'completion-report', 'ledger-event')


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


def event():
    return {'event_id': 'event-1', 'task_id': 'task-1', 'adapter': 'adapter-a', 'platform': 'platform-a',
        'agent_identity': 'researcher-1', 'archetype': 'researcher', 'role': 'Researcher', 'task_category': 'research',
        'capability_tier': 'balanced', 'abstract_effort': 'standard',
        'execution_fingerprint': {'provider': 'vendor-a', 'model_id': 'opaque-7', 'version': '1',
            'tools': ['read'], 'modalities': ['text'], 'effort': 'normal', 'effort_mapping': 'standard=normal'},
        'kpi_outcome': 'pass', 'verified': True, 'evidence_refs': ['evidence-1'],
        'delta': 2, 'reason': 'Verified first-pass compliance', 'score_update_mode': 'apply',
        'timestamp': '2026-10-07T00:00:00Z'}


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
            for token in ('gpt-', 'claude-', 'gemini-', 'spawn_agent', 'mcp__', '/users/', '/home/', '~/', 'c:\\'):
                self.assertNotIn(token, text)

    def test_valid_examples_and_required_fields(self):
        for name, value in zip(NAMES, (platform(), registry(), contract(), report(), event())):
            self.check(name, value)
            for key in self.schemas[name]['required']:
                broken = copy.deepcopy(value)
                del broken[key]
                with self.assertRaises(AssertionError, msg=f'{name}: {key}'):
                    self.check(name, broken)

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
