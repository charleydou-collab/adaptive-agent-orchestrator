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
            "codex/model-registry.example.json",
            "codex/execution-requirements.example.json",
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

    def test_every_management_adapter_preserves_premium_consent_gate(self):
        paths = (
            ADAPTERS / "codex" / "AGENTS.bootstrap.md",
            ADAPTERS / "chatgpt-web" / "custom-instructions-bootstrap.md",
            ADAPTERS / "generic-prompt" / "system-prompt.md",
        )
        for path in paths:
            with self.subTest(path=path):
                text = path.read_text(encoding="utf-8").lower()
                self.assertIn("premium", text)
                self.assertIn("explicit", text)
                self.assertIn("approval", text)

    def test_every_management_adapter_relays_worker_clarifications(self):
        paths = (
            ADAPTERS / "codex" / "AGENTS.bootstrap.md",
            ADAPTERS / "chatgpt-web" / "custom-instructions-bootstrap.md",
            ADAPTERS / "generic-prompt" / "system-prompt.md",
        )
        for path in paths:
            with self.subTest(path=path):
                text = path.read_text(encoding="utf-8").lower()
                for token in (
                    "clarification", "management agent", "recommended option",
                    "custom response", "same task",
                ):
                    self.assertIn(token, text)

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
        for token in ("bounded in-chat capsule", "host-controlled", "native history", "durable storage"):
            self.assertIn(token, custom)
        self.assertRegex(custom, r"cannot (guarantee|claim)[^.]*token")

    def test_codex_chat_learning_requires_stable_identity_and_configured_storage(self):
        bootstrap = (ADAPTERS / "codex" / "AGENTS.bootstrap.md").read_text(encoding="utf-8").lower()
        for token in ("stable conversation identity", "configured storage", "manage_chat_state.py", "compile_context.py"):
            self.assertIn(token, bootstrap)
        self.assertIn("do not use a global fallback", bootstrap)

    def test_all_adapters_define_chat_learning_controls_and_capability_fallbacks(self):
        paths = (
            ADAPTERS / "codex" / "AGENTS.bootstrap.md",
            ADAPTERS / "chatgpt-web" / "custom-instructions-bootstrap.md",
            ADAPTERS / "generic-prompt" / "system-prompt.md",
        )
        for path in paths:
            with self.subTest(path=path):
                text = path.read_text(encoding="utf-8").lower()
                for token in ("[no-learn]", "[learn]", "[full-context]", "[context-audit]", "reset chat learning"):
                    self.assertIn(token, text)
                self.assertIn("capabilit", text)

    def test_platform_context_declarations_do_not_overclaim(self):
        codex = json.loads((ADAPTERS / "codex" / "platform-capabilities.yaml").read_text())
        web = json.loads((ADAPTERS / "chatgpt-web" / "platform-capabilities.yaml").read_text())
        generic = json.loads((ADAPTERS / "generic-prompt" / "platform-capabilities.example.yaml").read_text())
        self.assertTrue(codex["conversation_context"]["context_compilation"])
        self.assertTrue(codex["conversation_context"]["token_estimation"])
        self.assertFalse(web["conversation_context"]["message_list_control"])
        self.assertFalse(web["conversation_context"]["persistence_supported"])
        self.assertEqual(web["conversation_context"]["learning_scope"], "in-chat")
        self.assertFalse(generic["conversation_context"]["context_compilation"])

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

    def test_codex_registry_example_defaults_to_nonpremium_and_gates_premium(self):
        registry = json.loads((ADAPTERS / "codex" / "model-registry.example.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(registry["models"]), 2)
        ordinary = [item for item in registry["models"] if item["approval_policy"] == "none"]
        premium = [item for item in registry["models"] if item["approval_policy"] == "explicit-user-approval"]
        self.assertTrue(ordinary)
        self.assertTrue(premium)
        self.assertTrue(all(item["cost_class"] in ("low", "medium") for item in ordinary))
        self.assertTrue(all(item["cost_class"] == "high" for item in premium))
        astra = [item for item in registry["models"] if "astra" in item["model_id"].lower()]
        self.assertEqual(len(astra), 1)
        self.assertEqual(astra[0]["cost_class"], "high")
        self.assertEqual(astra[0]["approval_policy"], "explicit-user-approval")


if __name__ == "__main__":
    unittest.main()
