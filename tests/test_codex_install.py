import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts" / "install_codex.py"


class CodexInstallTests(unittest.TestCase):
    def test_installs_without_changing_main_model_effort(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            codex = base / ".codex"
            agents = base / ".agents"
            codex.mkdir()
            original = 'model = "example"\nmodel_reasoning_effort = "low"\n'
            (codex / "config.toml").write_text(original, encoding="utf-8")
            result = subprocess.run(
                ["/usr/bin/python3", "-B", str(INSTALLER), "--codex-home", str(codex), "--agents-home", str(agents)],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            config = (codex / "config.toml").read_text(encoding="utf-8")
            self.assertIn(original.strip(), config)
            self.assertIn("max_concurrent_threads_per_session = 5", config)
            self.assertTrue((codex / "AGENTS.md").is_file())
            self.assertEqual(len(list((codex / "agents").glob("*.toml"))), 6)
            self.assertTrue((agents / "skills" / "adaptive-agent-orchestrator" / "SKILL.md").is_file())
            self.assertTrue((codex / "config.toml.pre-adaptive-orchestrator").is_file())

    def test_refuses_ambiguous_existing_installation(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            codex = base / ".codex"
            agents = base / ".agents"
            codex.mkdir()
            (codex / "config.toml").write_text("[agents]\nenabled = true\n", encoding="utf-8")
            result = subprocess.run(
                ["/usr/bin/python3", "-B", str(INSTALLER), "--codex-home", str(codex), "--agents-home", str(agents)],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("already contains [agents]", result.stderr)


if __name__ == "__main__":
    unittest.main()
