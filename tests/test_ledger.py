"""Behavioral and CLI checks for the metadata-only deterministic ledger."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from test_contracts import event

SCRIPT = Path(__file__).resolve().parents[1] / 'core/adaptive-agent-orchestrator/scripts/manage_agent_ledger.py'


class LedgerTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location('agent_ledger', SCRIPT)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'ledger.json'
        self.module.init_ledger(self.path)
        self.serial = 0

    def record(self, delta=0, **updates):
        value = event()
        self.serial += 1
        value.update(event_id=f'event-{self.serial}', delta=delta, **updates)
        return self.module.record_event(self.path, value)

    def test_initialization_and_no_overwrite(self):
        self.assertEqual(self.module.load_ledger(self.path)['identities'], {})
        result = self.record()
        self.assertEqual(result['score'], 100)
        self.assertTrue(result['eligible'])
        with self.assertRaises(ValueError):
            self.module.init_ledger(self.path)

    def test_initialization_does_not_replace_concurrent_destination(self):
        fresh = Path(self.tmp.name) / 'concurrent.json'
        original = b'concurrent-writer\n'
        real_link = self.module.os.link

        def create_first(source, destination):
            Path(destination).write_bytes(original)
            return real_link(source, destination)

        with mock.patch.object(self.module.os, 'link', side_effect=create_first):
            with self.assertRaises(ValueError):
                self.module.init_ledger(fresh)
        self.assertEqual(fresh.read_bytes(), original)
        self.assertEqual(list(fresh.parent.glob('.concurrent.json.*.tmp')), [])

    def test_verified_reward_deduction_and_requirements(self):
        self.assertEqual(self.record(20)['score'], 120)
        self.assertEqual(self.record(-30)['score'], 90)
        for key in ('verified', 'evidence_refs', 'reason', 'task_category', 'adapter', 'platform', 'role', 'capability_tier', 'execution_fingerprint'):
            value = event()
            del value[key]
            with self.assertRaises(ValueError):
                self.module.record_event(self.path, value)
        for changes in ({'verified': False}, {'verified': 1}, {'evidence_refs': []}, {'delta': True}, {'delta': float('nan')}, {'timestamp': '2026-99-07T00:00:00Z'}):
            with self.assertRaises(ValueError):
                self.record(**changes)

    def test_cap_floor_and_retirement_is_sticky(self):
        self.assertEqual(self.record(200)['score'], 200)
        result = self.record(-200)
        self.assertEqual(result['score'], 0)
        self.assertEqual(result['status'], 'retired')
        self.assertFalse(result['eligible'])
        result = self.record(10)
        self.assertEqual(result['status'], 'retired')
        self.assertFalse(result['eligible'])

    def test_freeze_records_without_changing_score(self):
        self.assertEqual(self.record(-200, score_update_mode='freeze')['score'], 100)
        self.assertEqual(len(self.module.load_ledger(self.path)['events']), 1)

    def test_corrections_cumulatively_restore_at_most_half(self):
        self.record(-40)
        self.assertEqual(self.record(12, correction_of='event-1')['score'], 72)
        self.assertEqual(self.record(8, correction_of='event-1')['score'], 80)
        with self.assertRaises(ValueError):
            self.record(1, correction_of='event-1')
        self.assertEqual(len(self.module.load_ledger(self.path)['events']), 3)

    def test_correction_uses_actual_deduction_and_same_scope(self):
        self.record(-200)
        with self.assertRaises(ValueError):
            self.record(51, correction_of='event-1')
        with self.assertRaises(ValueError):
            self.record(10, correction_of='event-1', adapter='other')
        self.assertEqual(self.record(50, correction_of='event-1')['score'], 50)
        with self.assertRaises(ValueError):
            self.record(-1, correction_of='event-1')

    def test_frozen_deduction_cannot_be_corrected(self):
        self.record(-40, score_update_mode='freeze')
        with self.assertRaises(ValueError):
            self.record(20, correction_of='event-1')

    def test_fingerprint_adapter_isolation_and_explicit_equivalence(self):
        self.record(20)
        changed = copy.deepcopy(event()['execution_fingerprint'])
        changed['version'] = '2'
        self.assertEqual(self.record(1, execution_fingerprint=changed)['score'], 101)
        self.assertEqual(self.record(2, adapter='adapter-b')['score'], 102)
        result = self.record(0, adapter='adapter-c', equivalence_of='event-1')
        self.assertEqual(result['score'], 120)
        self.assertEqual(self.record(3)['score'], 123)
        self.assertEqual(self.record(0, adapter='adapter-c')['score'], 120)

    def test_equivalence_cannot_overwrite_or_copy_frozen(self):
        self.record(20)
        with self.assertRaises(ValueError):
            self.record(0, equivalence_of='event-1')
        result = self.record(0, adapter='other', equivalence_of='event-1', score_update_mode='freeze')
        self.assertEqual(result['score'], 100)

    def test_confirmation_and_reset_preserves_history(self):
        item = self.record(20)
        for function, args in ((self.module.retire_identity, (self.path, item['identity_key'])), (self.module.reset_ledger, (self.path, item['identity_key']))):
            with self.assertRaises(ValueError):
                function(*args)
        self.module.retire_identity(self.path, item['identity_key'], confirm=True)
        self.assertFalse(self.module.load_ledger(self.path)['identities'][item['identity_key']]['eligible'])
        state = self.module.reset_ledger(self.path, item['identity_key'], confirm=True)
        self.assertEqual(state['identities'][item['identity_key']]['score'], 100)
        self.assertEqual(len(state['events']), 1)
        self.assertEqual(len(state['administrative_events']), 2)
        with self.assertRaises(ValueError):
            self.record(1, correction_of='event-1')

    def test_role_category_and_tier_are_independent_score_scopes(self):
        original = self.record(30)
        for field, changed in (('role', 'Reviewer'), ('task_category', 'review'), ('capability_tier', 'advanced')):
            with self.subTest(field=field):
                result = self.record(5, **{field: changed})
                self.assertEqual(result['score'], 105)
                self.assertNotEqual(result['identity_key'], original['identity_key'])
                self.assertEqual(result[field], changed)
                with self.assertRaises(ValueError):
                    self.record(0, correction_of='event-1', **{field: changed})
        self.assertEqual(self.record(0)['score'], 130)
        self.assertEqual(len(self.module.load_ledger(self.path)['identities']), 4)

    def test_targeted_reset_generations_and_unaffected_identity(self):
        target = self.record(-40)
        other = self.record(-20, agent_identity='other-agent')
        self.module.retire_identity(self.path, target['identity_key'], confirm=True)
        self.module.retire_identity(self.path, other['identity_key'], confirm=True)
        other_before = copy.deepcopy(self.module.load_ledger(self.path)['identities'][other['identity_key']])
        state = self.module.reset_ledger(self.path, target['identity_key'], confirm=True)
        self.assertEqual(state['identities'][target['identity_key']]['score'], 100)
        self.assertTrue(state['identities'][target['identity_key']]['eligible'])
        self.assertEqual(state['identities'][target['identity_key']]['generation'], 1)
        self.assertEqual(state['identities'][other['identity_key']], other_before)
        self.assertEqual(state['administrative_events'][-1]['identity_key'], target['identity_key'])
        with self.assertRaises(ValueError):
            self.record(1, correction_of='event-1')
        with self.assertRaises(ValueError):
            self.record(0, adapter='other', equivalence_of='event-1')
        self.assertEqual(self.record(10, agent_identity='other-agent', correction_of='event-2')['score'], 90)
        self.assertEqual(self.record(0, agent_identity='other-agent', adapter='other', equivalence_of='event-2')['score'], 80)
        self.record(-10)
        deduction_id = f'event-{self.serial}'
        self.assertEqual(self.record(5, correction_of=deduction_id)['score'], 95)
        before = self.path.read_bytes()
        with self.assertRaises(ValueError):
            self.module.reset_ledger(self.path, 'unknown', confirm=True)
        self.assertEqual(self.path.read_bytes(), before)

    def test_approved_promotion_bands(self):
        policy = (SCRIPT.parents[1] / 'references/scoring-policy.md').read_text()
        for band in ('0 Retired', '1–69 Restricted', '70–99 Probation', '100–119 Qualified', '120–149 Senior', '150–199 Expert', '200 Elite'):
            self.assertIn(band, policy)

    def test_atomic_replacement_and_failed_write_preserves_original(self):
        before = self.path.read_bytes()
        real_replace = self.module.os.replace
        def check(source, destination):
            self.assertEqual(Path(source).parent, self.path.parent)
            self.assertEqual(Path(destination), self.path)
            self.assertEqual(self.path.read_bytes(), before)
            json.loads(Path(source).read_text())
            real_replace(source, destination)
        with mock.patch.object(self.module.os, 'replace', side_effect=check) as replace:
            self.record(2)
            replace.assert_called_once()
        before = self.path.read_bytes()
        with mock.patch.object(self.module.os, 'replace', side_effect=OSError('simulated')):
            with self.assertRaises(OSError):
                self.record(3)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(list(self.path.parent.iterdir()), [self.path])

    def test_sensitive_fields_rejected_at_every_level(self):
        for key in ('prompt', 'full_prompt', 'source_documents', 'documents', 'full_output', 'output'):
            for nested in (False, True):
                value = event()
                target = value['execution_fingerprint'] if nested else value
                target[key] = 'sensitive'
                with self.assertRaises(ValueError):
                    self.module.record_event(self.path, value)
        self.assertEqual(self.module.load_ledger(self.path)['events'], [])

    def test_duplicate_id_and_invalid_reference_do_not_mutate(self):
        self.record(2)
        before = self.path.read_bytes()
        with self.assertRaises(ValueError):
            self.module.record_event(self.path, event())
        with self.assertRaises(ValueError):
            self.record(0, equivalence_of='missing')
        self.assertEqual(self.path.read_bytes(), before)

    def test_cli_json_results_and_errors(self):
        def cli(*args, payload=None):
            result = subprocess.run([sys.executable, str(SCRIPT), *args, '--ledger', str(self.path)], input=payload, text=True, capture_output=True)
            self.assertEqual(result.stderr, '')
            return result.returncode, json.loads(result.stdout)
        code, result = cli('record', '--event', '-', payload=json.dumps(event()))
        self.assertEqual(code, 0)
        self.assertEqual(result['score'], 102)
        self.assertEqual(cli('show')[0], 0)
        self.assertNotEqual(cli('retire', '--identity-key', result['identity_key'])[0], 0)
        self.assertEqual(cli('retire', '--identity-key', result['identity_key'], '--confirm')[0], 0)
        self.assertNotEqual(cli('reset')[0], 0)
        self.assertNotEqual(cli('reset', '--confirm')[0], 0)
        self.assertNotEqual(cli('reset', '--identity-key', result['identity_key'])[0], 0)
        self.assertEqual(cli('reset', '--identity-key', result['identity_key'], '--confirm')[0], 0)
        self.assertNotEqual(cli('unknown')[0], 0)
        fresh = Path(self.tmp.name) / 'fresh.json'
        result = subprocess.run([sys.executable, str(SCRIPT), 'init', '--ledger', str(fresh)], text=True, capture_output=True)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)['identities'], {})


if __name__ == '__main__':
    unittest.main()
