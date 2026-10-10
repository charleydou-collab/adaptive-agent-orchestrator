import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts" / "install_codex.py"


def load_installer():
    spec = importlib.util.spec_from_file_location('install_codex_tested', INSTALLER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CodexInstallTests(unittest.TestCase):
    def legacy_bytes(self, relative):
        return self.legacy_content[relative]

    def run_installer(self, codex, agents, *extra):
        if '--upgrade' in extra and hasattr(self, 'legacy_hashes'):
            installer = load_installer()
            patches = (
                mock.patch.object(installer, 'LEGACY_SKILL_SHA256',
                    self.legacy_hashes['skill']),
                mock.patch.object(installer, 'LEGACY_AGENT_SHA256',
                    self.legacy_hashes['agents']),
                mock.patch.object(installer, 'LEGACY_BOOTSTRAP_SHA256',
                    self.legacy_hashes['bootstrap']),
            )
            try:
                with patches[0], patches[1], patches[2]:
                    installer.install(codex, agents, upgrade=True)
            except (OSError, ValueError) as exc:
                return SimpleNamespace(returncode=2, stderr=str(exc))
            return SimpleNamespace(returncode=0, stderr='')
        return subprocess.run(
            ["/usr/bin/python3", "-B", str(INSTALLER), "--codex-home", str(codex),
                "--agents-home", str(agents), *extra],
            cwd=ROOT, text=True, capture_output=True)

    def legacy_install(self, base):
        installer = load_installer()
        codex, agents = base / '.codex', base / '.agents'
        codex.mkdir()
        config_original = 'model = "example"\nmodel_reasoning_effort = "low"\n'
        snippet = (ROOT / 'adapters/codex/config-snippet.toml').read_text().strip()
        (codex / 'config.toml').write_text(config_original.rstrip() + '\n\n' + snippet + '\n')
        self.legacy_content = {}
        legacy_bootstrap = '# Synthetic known v0.1.3 bootstrap\n'
        self.legacy_content['adapters/codex/AGENTS.bootstrap.md'] = legacy_bootstrap.encode()
        bootstrap = ('<!-- adaptive-agent-orchestrator:start -->\n' + legacy_bootstrap.rstrip()
            + '\n<!-- adaptive-agent-orchestrator:end -->\n')
        (codex / 'AGENTS.md').write_text('User content\n\n' + bootstrap)
        (codex / 'agents').mkdir()
        agent_names = ('artifact-producer.toml', 'data-analyst.toml', 'document-analyst.toml',
            'research-worker.toml', 'synthesis-worker.toml', 'verification-auditor.toml')
        for name in agent_names:
            content = ('legacy agent ' + name + '\n').encode()
            self.legacy_content['adapters/codex/agents/' + name] = content
            (codex / 'agents' / name).write_bytes(content)
        skill = agents / 'skills/adaptive-agent-orchestrator'
        for relative in installer.LEGACY_SKILL_SHA256:
            if relative == 'schemas/clarification-request.schema.json':
                content = json.dumps({'properties': {'question': {'minLength': 1}}}).encode()
            elif relative.endswith('.json'):
                content = json.dumps({'legacy_fixture': relative}).encode()
            else:
                content = ('legacy skill ' + relative + '\n').encode()
            repository_relative = 'core/adaptive-agent-orchestrator/' + relative
            self.legacy_content[repository_relative] = content
            target = skill / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        (skill / '.adaptive-agent-orchestrator-version').write_text('0.1.3\n')
        self.legacy_hashes = {
            'skill': {relative: installer._managed_digest(skill / relative, relative)
                for relative in installer.LEGACY_SKILL_SHA256},
            'agents': {name: installer._sha256_file(codex / 'agents' / name)
                for name in agent_names},
            'bootstrap': installer._sha256_bytes(legacy_bootstrap.encode()),
        }
        runtime = codex / 'adaptive-agent-orchestrator'
        (runtime / 'chat-state').mkdir(parents=True)
        (runtime / 'chat-state/conversation.json').write_text('{"preserve":true}\n')
        (runtime / 'agent-ledger.json').write_text('{"preserve":true}\n')
        return codex, agents, config_original

    def test_installs_without_changing_main_model_effort(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            codex = base / ".codex"
            agents = base / ".agents"
            codex.mkdir()
            original = 'model = "example"\nmodel_reasoning_effort = "low"\n'
            (codex / "config.toml").write_text(original, encoding="utf-8")
            result = self.run_installer(codex, agents)
            self.assertEqual(result.returncode, 0, result.stderr)
            config = (codex / "config.toml").read_text(encoding="utf-8")
            self.assertIn(original.strip(), config)
            self.assertIn("max_concurrent_threads_per_session = 5", config)
            self.assertTrue((codex / "AGENTS.md").is_file())
            self.assertEqual(len(list((codex / "agents").glob("*.toml"))), 6)
            self.assertTrue((agents / "skills" / "adaptive-agent-orchestrator" / "SKILL.md").is_file())
            self.assertEqual((agents / "skills" / "adaptive-agent-orchestrator" / ".adaptive-agent-orchestrator-version").read_text().strip(), "0.2.0")
            self.assertTrue((agents / "skills" / "adaptive-agent-orchestrator" / "config" / "chat-state-config.example.yaml").is_file())
            state_config = (agents / "skills" / "adaptive-agent-orchestrator" / "config" / "chat-state-config.example.yaml").read_text()
            self.assertIn('${WORKSPACE_ROOT}', state_config)
            self.assertIn('${CONVERSATION_ID}', state_config)
            self.assertIn('adapter-provided', state_config)
            self.assertIn('disable-persistence', state_config)
            self.assertTrue((codex / "config.toml.pre-adaptive-orchestrator").is_file())

    def test_refuses_ambiguous_existing_installation(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            codex = base / ".codex"
            agents = base / ".agents"
            codex.mkdir()
            (codex / "config.toml").write_text("[agents]\nenabled = true\n", encoding="utf-8")
            result = self.run_installer(codex, agents)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("already contains [agents]", result.stderr)

    def test_upgrades_known_v013_and_preserves_configuration_and_runtime_state(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            codex, agents, original = self.legacy_install(base)
            config_before = (codex / 'config.toml').read_bytes()
            (codex / 'config.toml.pre-adaptive-orchestrator-upgrade-0.2.0').write_text('older backup')
            result = self.run_installer(codex, agents, '--upgrade')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((codex / 'config.toml').read_bytes(), config_before)
            self.assertIn(original.strip(), (codex / 'config.toml').read_text())
            self.assertEqual((codex / 'config.toml').read_text().count('[agents]'), 1)
            agents_md = (codex / 'AGENTS.md').read_text()
            self.assertEqual(agents_md.count('<!-- adaptive-agent-orchestrator:start -->'), 1)
            self.assertEqual(agents_md.count('<!-- adaptive-agent-orchestrator:end -->'), 1)
            skill = agents / 'skills/adaptive-agent-orchestrator'
            self.assertEqual((skill / '.adaptive-agent-orchestrator-version').read_text().strip(), '0.2.0')
            self.assertTrue((skill / 'references/chat-learning.md').is_file())
            self.assertTrue((skill / 'config/chat-state-config.example.yaml').is_file())
            self.assertEqual((codex / 'adaptive-agent-orchestrator/chat-state/conversation.json').read_text(), '{"preserve":true}\n')
            self.assertEqual((codex / 'adaptive-agent-orchestrator/agent-ledger.json').read_text(), '{"preserve":true}\n')
            self.assertTrue((codex / 'config.toml.pre-adaptive-orchestrator-upgrade-0.2.0.1').is_file())
            self.assertTrue(any(codex.glob('AGENTS.md.pre-adaptive-orchestrator-upgrade-0.2.0*')))
            skill_backups = list((agents / 'skills').glob(
                'adaptive-agent-orchestrator.pre-adaptive-orchestrator-upgrade-0.2.0*'))
            self.assertEqual(len(skill_backups), 1)
            self.assertEqual(
                (skill_backups[0] / 'SKILL.md').read_bytes(),
                self.legacy_bytes('core/adaptive-agent-orchestrator/SKILL.md'))
            agent_backups = list(codex.glob(
                'agents.pre-adaptive-orchestrator-upgrade-0.2.0*'))
            self.assertEqual(len(agent_backups), 1)
            for name in ('artifact-producer.toml', 'data-analyst.toml',
                    'document-analyst.toml', 'research-worker.toml',
                    'synthesis-worker.toml', 'verification-auditor.toml'):
                self.assertEqual(
                    (agent_backups[0] / name).read_bytes(),
                    self.legacy_bytes('adapters/codex/agents/' + name))

    def test_upgrade_refuses_modified_managed_v013_file(self):
        with tempfile.TemporaryDirectory() as directory:
            codex, agents, _ = self.legacy_install(Path(directory))
            skill = agents / 'skills/adaptive-agent-orchestrator'
            (skill / 'SKILL.md').write_text('locally modified\n')
            before = (skill / 'SKILL.md').read_bytes()

            result = self.run_installer(codex, agents, '--upgrade')

            self.assertEqual(result.returncode, 2)
            self.assertIn('modified', result.stderr.lower())
            self.assertEqual((skill / 'SKILL.md').read_bytes(), before)
            self.assertFalse(any((agents / 'skills').glob(
                '*.pre-adaptive-orchestrator-upgrade-0.2.0*')))

    def test_upgrade_accepts_semantically_identical_legacy_json_formatting(self):
        with tempfile.TemporaryDirectory() as directory:
            codex, agents, _ = self.legacy_install(Path(directory))
            schema = (agents / 'skills/adaptive-agent-orchestrator/schemas'
                / 'clarification-request.schema.json')
            schema.write_text(json.dumps(json.loads(schema.read_text()),
                separators=(',', ':')) + '\n')

            result = self.run_installer(codex, agents, '--upgrade')

            self.assertEqual(result.returncode, 0, result.stderr)

    def test_upgrade_refuses_semantically_modified_legacy_json(self):
        with tempfile.TemporaryDirectory() as directory:
            codex, agents, _ = self.legacy_install(Path(directory))
            schema = (agents / 'skills/adaptive-agent-orchestrator/schemas'
                / 'clarification-request.schema.json')
            value = json.loads(schema.read_text())
            value['properties']['question']['minLength'] = 2
            schema.write_text(json.dumps(value) + '\n')

            result = self.run_installer(codex, agents, '--upgrade')

            self.assertEqual(result.returncode, 2)
            self.assertIn('modified', result.stderr.lower())

    def test_explicit_custom_bootstrap_migration_preserves_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            codex, agents, _ = self.legacy_install(Path(directory))
            bootstrap = codex / 'AGENTS.md'
            customized = bootstrap.read_text().replace(
                '# Synthetic known v0.1.3 bootstrap',
                '# User-approved customized v0.1.3 bootstrap')
            bootstrap.write_text(customized)
            installer = load_installer()
            patches = (
                mock.patch.object(installer, 'LEGACY_SKILL_SHA256',
                    self.legacy_hashes['skill']),
                mock.patch.object(installer, 'LEGACY_AGENT_SHA256',
                    self.legacy_hashes['agents']),
                mock.patch.object(installer, 'LEGACY_BOOTSTRAP_SHA256',
                    self.legacy_hashes['bootstrap']),
            )
            with patches[0], patches[1], patches[2]:
                with self.assertRaisesRegex(ValueError, 'modified v0.1.3 bootstrap'):
                    installer.install(codex, agents, upgrade=True)
                result = installer.install(codex, agents, upgrade=True,
                    allow_modified_bootstrap=True)

            self.assertTrue(result['custom_bootstrap_migrated'])
            backups = list(codex.glob(
                'AGENTS.md.pre-adaptive-orchestrator-upgrade-0.2.0*'))
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_text(), customized)
            self.assertIn('For each prompt, act as the management agent',
                bootstrap.read_text())

    def test_upgrade_rolls_back_all_managed_targets_on_late_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            codex, agents, _ = self.legacy_install(Path(directory))
            skill = agents / 'skills/adaptive-agent-orchestrator'
            original_skill = (skill / 'SKILL.md').read_bytes()
            original_bootstrap = (codex / 'AGENTS.md').read_bytes()
            original_agents = {
                path.name: path.read_bytes() for path in (codex / 'agents').glob('*.toml')
            }
            installer = load_installer()
            real_atomic_text = installer._atomic_text
            calls = {'count': 0}

            def fail_first_bootstrap_write(path, text):
                calls['count'] += 1
                if calls['count'] == 1:
                    raise OSError('injected late failure')
                return real_atomic_text(path, text)

            with mock.patch.object(installer, 'LEGACY_SKILL_SHA256',
                    self.legacy_hashes['skill']), mock.patch.object(
                    installer, 'LEGACY_AGENT_SHA256', self.legacy_hashes['agents']), mock.patch.object(
                    installer, 'LEGACY_BOOTSTRAP_SHA256', self.legacy_hashes['bootstrap']), mock.patch.object(
                    installer, '_atomic_text', side_effect=fail_first_bootstrap_write):
                with self.assertRaises(OSError):
                    installer.install(codex, agents, upgrade=True)

            self.assertEqual((skill / 'SKILL.md').read_bytes(), original_skill)
            self.assertEqual((codex / 'AGENTS.md').read_bytes(), original_bootstrap)
            self.assertEqual(
                {path.name: path.read_bytes() for path in (codex / 'agents').glob('*.toml')},
                original_agents)

    def test_upgrade_refuses_ambiguous_partial_install(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            codex, agents = base / '.codex', base / '.agents'
            codex.mkdir()
            (codex / 'config.toml').write_text('model = "example"\n')
            skill = agents / 'skills/adaptive-agent-orchestrator'
            skill.mkdir(parents=True)
            (skill / 'SKILL.md').write_text('partial')
            result = self.run_installer(codex, agents, '--upgrade')
            self.assertEqual(result.returncode, 2)
            self.assertIn('ambiguous', result.stderr.lower())


if __name__ == "__main__":
    unittest.main()
