import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ADAPTERS = ROOT / "adapters"


class AdapterTests(unittest.TestCase):
    def test_required_adapter_files(self):
        required = (
            "codex/AGENTS.bootstrap.md",
            "codex/config-snippet.toml",
            "codex/ledger-config.example.yaml",
            "codex/platform-capabilities.yaml",
            "chatgpt-web/custom-instructions-bootstrap.md",
            "chatgpt-web/platform-capabilities.yaml",
            "chatgpt-web/plugin/plugin.json",
            "generic-prompt/system-prompt.md",
            "generic-prompt/platform-capabilities.example.yaml",
        )
        for relative in required:
            self.assertTrue((ADAPTERS / relative).is_file(), relative)

    def test_codex_archetypes_are_model_neutral(self):
        agents = ADAPTERS / "codex" / "agents"
        expected = {"research-worker", "document-analyst", "data-analyst", "synthesis-worker", "artifact-producer", "verification-auditor"}
        self.assertEqual({p.stem for p in agents.glob("*.toml")}, expected)
        for path in agents.glob("*.toml"):
            text = path.read_text(encoding="utf-8")
            for field in ("name", "description", "developer_instructions"):
                self.assertRegex(text, rf"(?m)^{field}\s*=")
            self.assertNotRegex(text, r"(?m)^model(_reasoning_effort)?\s*=")

    def test_concurrency_policy_is_bounded(self):
        config = (ADAPTERS / "codex" / "config-snippet.toml").read_text(encoding="utf-8")
        self.assertIn("max_concurrent_threads_per_session = 5", config)
        bootstrap = (ADAPTERS / "codex" / "AGENTS.bootstrap.md").read_text(encoding="utf-8").lower()
        self.assertIn("desired concurrency of 3", bootstrap)
        self.assertIn("authorized ceiling of 5", bootstrap)

    def test_codex_persistent_scoring_is_configurable_and_portable(self):
        bootstrap = (ADAPTERS / "codex" / "AGENTS.bootstrap.md").read_text(encoding="utf-8")
        ledger = (ADAPTERS / "codex" / "ledger-config.example.yaml").read_text(encoding="utf-8")
        self.assertIn("workspace-scoped performance ledger", bootstrap)
        self.assertIn("manage_agent_ledger.py", bootstrap)
        self.assertIn("score_update_mode: freeze", bootstrap)
        self.assertIn("${WORKSPACE_ROOT}", ledger)
        self.assertIn("${AGENTS_HOME}", ledger)
        self.assertNotIn("/Users/", bootstrap + ledger)

    def test_web_manifest_and_activation_are_honest(self):
        manifest = json.loads((ADAPTERS / "chatgpt-web" / "plugin" / "plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["name"], "adaptive-agent-orchestrator")
        self.assertRegex(manifest["version"], r"^\d+\.\d+\.\d+$")
        interface = manifest["extensions"]["com.openai"]["interface"]
        self.assertLessEqual(len(interface["shortDescription"]), 30)
        self.assertLessEqual(len(interface["defaultPrompt"]), 3)
        web = json.loads((ADAPTERS / "chatgpt-web" / "platform-capabilities.yaml").read_text(encoding="utf-8"))
        self.assertFalse(web["activation"]["guaranteed"])
        self.assertEqual(web["persistence"]["scope"], "none")
        custom = (ADAPTERS / "chatgpt-web" / "custom-instructions-bootstrap.md").read_text(encoding="utf-8").lower()
        self.assertIn("explicitly select", custom)

    def test_generic_adapter_claims_only_fallback_capabilities(self):
        declaration = json.loads((ADAPTERS / "generic-prompt" / "platform-capabilities.example.yaml").read_text(encoding="utf-8"))
        self.assertFalse(declaration["delegation"]["supported"])
        self.assertEqual(declaration["delegation"]["max_concurrency"], 1)
        self.assertEqual(declaration["persistence"]["scope"], "none")
        prompt = (ADAPTERS / "generic-prompt" / "system-prompt.md").read_text(encoding="utf-8").lower()
        for token in ("sequential role simulation", "do not claim", "capability"):
            self.assertIn(token, prompt)
        self.assertNotRegex(prompt, r"gpt-|claude-|gemini-")

    def test_platform_declarations_are_json_compatible_yaml(self):
        paths = (
            ADAPTERS / "codex" / "platform-capabilities.yaml",
            ADAPTERS / "chatgpt-web" / "platform-capabilities.yaml",
            ADAPTERS / "generic-prompt" / "platform-capabilities.example.yaml",
        )
        for path in paths:
            with self.subTest(path=path):
                value = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(value["modalities"], ["text"])
                self.assertIn("fallback_mode", value["delegation"])
                self.assertIsInstance(value["models"]["registry"], dict)
                self.assertIn("models", value["models"]["registry"])


if __name__ == "__main__":
    unittest.main()
