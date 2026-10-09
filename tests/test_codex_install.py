import subprocess
import shutil
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts" / "install_codex.py"


class CodexInstallTests(unittest.TestCase):
    def run_installer(self, codex, agents, *extra):
        return subprocess.run(
            ["/usr/bin/python3", "-B", str(INSTALLER), "--codex-home", str(codex),
                "--agents-home", str(agents), *extra],
            cwd=ROOT, text=True, capture_output=True)

    def legacy_install(self, base):
        codex, agents = base / '.codex', base / '.agents'
        codex.mkdir()
        config_original = 'model = "example"\nmodel_reasoning_effort = "low"\n'
        snippet = (ROOT / 'adapters/codex/config-snippet.toml').read_text().strip()
        (codex / 'config.toml').write_text(config_original.rstrip() + '\n\n' + snippet + '\n')
        bootstrap = '<!-- adaptive-agent-orchestrator:start -->\n# Legacy v0.1.3 bootstrap\n<!-- adaptive-agent-orchestrator:end -->\n'
        (codex / 'AGENTS.md').write_text('User content\n\n' + bootstrap)
        (codex / 'agents').mkdir()
        for source in (ROOT / 'adapters/codex/agents').glob('*.toml'):
            shutil.copy2(source, codex / 'agents' / source.name)
        skill = agents / 'skills/adaptive-agent-orchestrator'
        shutil.copytree(ROOT / 'core/adaptive-agent-orchestrator', skill)
        (skill / '.adaptive-agent-orchestrator-version').write_text('0.1.3\n')
        (skill / 'references/chat-learning.md').unlink()
        (skill / 'references/context-compilation.md').unlink()
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
