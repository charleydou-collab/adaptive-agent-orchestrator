import json
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "scripts" / "build_chatgpt_plugin.py"


class PluginBuildTests(unittest.TestCase):
    def test_builds_one_self_contained_plugin(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "plugin.zip"
            result = subprocess.run(
                ["/usr/bin/python3", "-B", str(BUILDER), "--output", str(archive)],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(archive.is_file())
            with zipfile.ZipFile(archive) as bundle:
                names = bundle.namelist()
                roots = {PurePosixPath(name).parts[0] for name in names}
                self.assertEqual(roots, {"adaptive-agent-orchestrator"})
                self.assertIn("adaptive-agent-orchestrator/plugin.json", names)
                self.assertIn("adaptive-agent-orchestrator/.codex-plugin/plugin.json", names)
                skill = "adaptive-agent-orchestrator/skills/adaptive-agent-orchestrator/SKILL.md"
                self.assertIn(skill, names)
                self.assertFalse(any("/scripts/" in name for name in names))
                self.assertFalse(any(".sdd" in name or "__pycache__" in name for name in names))
                manifest = json.loads(bundle.read("adaptive-agent-orchestrator/plugin.json"))
                compatibility = json.loads(bundle.read("adaptive-agent-orchestrator/.codex-plugin/plugin.json"))
                self.assertEqual(manifest["name"], "adaptive-agent-orchestrator")
                self.assertEqual(manifest["version"], "0.2.0")
                self.assertEqual(compatibility["name"], manifest["name"])
                self.assertEqual(compatibility["version"], manifest["version"])
                for key, value in manifest["extensions"]["com.openai"]["interface"].items():
                    self.assertEqual(compatibility["interface"][key], value)
                self.assertIn(b"name: adaptive-agent-orchestrator", bundle.read(skill))
                self.assertIn(
                    "adaptive-agent-orchestrator/skills/adaptive-agent-orchestrator/schemas/clarification-request.schema.json",
                    names,
                )
                self.assertIn(
                    "adaptive-agent-orchestrator/skills/adaptive-agent-orchestrator/schemas/clarification-response.schema.json",
                    names,
                )
                self.assertIn(
                    "adaptive-agent-orchestrator/skills/adaptive-agent-orchestrator/references/chat-learning.md",
                    names,
                )
                self.assertIn(
                    "adaptive-agent-orchestrator/skills/adaptive-agent-orchestrator/schemas/context-package.schema.json",
                    names,
                )
                forbidden = ("/.git/", "__pycache__", "/tests/", "agent-ledger.json", "/chat-state/", "/docs/")
                self.assertFalse(any(any(token in name for token in forbidden) for name in names))
                content = b"\n".join(bundle.read(name) for name in names)
                self.assertNotIn(b"/Users/", content)
                self.assertNotIn(b"adaptive-agent-orchestrator/scripts/", content)

    def test_repeated_build_is_byte_identical(self):
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "one.zip"
            second = Path(directory) / "two.zip"
            for output in (first, second):
                result = subprocess.run(
                    ["/usr/bin/python3", "-B", str(BUILDER), "--output", str(output)],
                    cwd=ROOT,
                    text=True,
                    capture_output=True,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(first.read_bytes(), second.read_bytes())


if __name__ == "__main__":
    unittest.main()
