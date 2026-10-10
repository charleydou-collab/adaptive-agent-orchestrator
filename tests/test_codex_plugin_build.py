"""Deterministic and privacy-safe Codex distribution tests."""
import json
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / 'scripts' / 'build_codex_plugin.py'
ROOT_NAME = 'adaptive-agent-orchestrator-codex'
APPROVED_SCRIPTS = {
    'chat_learning.py', 'chat_state.py', 'compile_context.py',
    'manage_agent_ledger.py', 'manage_chat_state.py', 'resolve_model.py',
}


class CodexPluginBuildTests(unittest.TestCase):
    def build(self, output):
        result = subprocess.run(['/usr/bin/python3', '-B', str(BUILDER), '--output', str(output)],
            cwd=ROOT, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_codex_archive_has_explicit_runtime_inventory(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / 'codex.zip'
            self.build(archive)
            with zipfile.ZipFile(archive) as bundle:
                names = bundle.namelist()
                self.assertEqual({PurePosixPath(name).parts[0] for name in names}, {ROOT_NAME})
                manifest = json.loads(bundle.read(f'{ROOT_NAME}/plugin.json'))
                self.assertEqual(manifest['name'], ROOT_NAME)
                self.assertEqual(manifest['version'], '0.2.0')
                self.assertEqual(manifest['coreSkill'], 'adaptive-agent-orchestrator')
                skill = f'{ROOT_NAME}/skills/adaptive-agent-orchestrator/SKILL.md'
                self.assertIn(skill, names)
                self.assertIn(b'name: adaptive-agent-orchestrator', bundle.read(skill))
                scripts = {PurePosixPath(name).name for name in names if '/scripts/' in name}
                self.assertEqual(scripts, APPROVED_SCRIPTS)
                self.assertEqual(len([name for name in names if '/agents/' in name and name.endswith('.toml')]), 6)
                for required in ('AGENTS.bootstrap.md', 'chat-state-config.example.yaml', 'platform-capabilities.yaml',
                        'config-snippet.toml', 'ledger-config.example.yaml',
                        'model-registry.example.json', 'execution-requirements.example.json'):
                    self.assertIn(f'{ROOT_NAME}/codex/{required}', names)
                forbidden = ('/.git/', '__pycache__', '/tests/', '/docs/', 'agent-ledger.json',
                    '.sdd', 'chat-state.json', 'chatgpt-web', 'generic-prompt')
                self.assertFalse(any(any(token in name for token in forbidden) for name in names))
                content = b'\n'.join(bundle.read(name) for name in names)
                self.assertNotIn(b'/' + b'Users/', content)

    def test_codex_repeated_build_is_byte_identical(self):
        with tempfile.TemporaryDirectory() as directory:
            first, second = Path(directory) / 'one.zip', Path(directory) / 'two.zip'
            self.build(first)
            self.build(second)
            self.assertEqual(first.read_bytes(), second.read_bytes())


if __name__ == '__main__':
    unittest.main()
