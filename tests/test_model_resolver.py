import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "core/adaptive-agent-orchestrator/scripts/resolve_model.py"


def model(model_id, *, tiers=("balanced",), cost="low", approval="none",
          context=32000, modalities=("text",), tools=("read",), availability="available",
          mapping=None):
    mapping = mapping or {"minimal": "low", "standard": "medium", "deep": None}
    efforts = sorted({value for value in mapping.values() if value is not None})
    return {
        "provider": "provider-a",
        "model_id": model_id,
        "version": "1",
        "capability_tiers": list(tiers),
        "capabilities": ["analysis"],
        "cost_class": cost,
        "approval_policy": approval,
        "context_window": context,
        "modalities": list(modalities),
        "tools": list(tools),
        "supported_efforts": efforts,
        "reasoning_mapping": mapping,
        "availability": availability,
    }


def requirements(**updates):
    value = {
        "capability_tier": "balanced",
        "minimum_context": 8000,
        "modalities": ["text"],
        "required_tools": ["read"],
        "minimum_reasoning_class": "standard",
    }
    value.update(updates)
    return value


class ModelResolverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("model_resolver", SCRIPT)
        cls.resolver = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.resolver)

    def test_selects_lowest_cost_compatible_nonpremium_model(self):
        registry = {"models": [
            model("medium-model", cost="medium"),
            model("low-model", cost="low"),
            model("premium-model", cost="high", approval="explicit-user-approval"),
        ]}
        result = self.resolver.resolve(registry, requirements(), adapter="codex-local")
        self.assertEqual(result["status"], "selected")
        self.assertEqual(result["resolved_execution"]["model_id"], "low-model")
        self.assertEqual(result["resolved_execution"]["effort"], "medium")
        self.assertFalse(result["premium_used"])

    def test_premium_requires_explanation_and_exact_model_approval(self):
        registry = {"models": [model(
            "premium-model", tiers=("advanced",), cost="high",
            approval="explicit-user-approval", mapping={"minimal": "low", "standard": "medium", "deep": "high"},
        )]}
        needs = requirements(capability_tier="advanced", minimum_reasoning_class="deep")
        blocked = self.resolver.resolve(registry, needs, adapter="codex-local")
        self.assertEqual(blocked["status"], "approval_required")
        self.assertEqual(blocked["recommended_model"]["model_id"], "premium-model")
        self.assertIn("Why it is recommended", blocked["user_prompt"])
        self.assertIn("higher-cost", blocked["user_prompt"])
        self.assertNotIn("resolved_execution", blocked)

        wrong = self.resolver.resolve(
            registry, needs, adapter="codex-local",
            approval={"model_id": "old-model-name", "reference": "user-approved-turn-7"},
        )
        self.assertEqual(wrong["status"], "approval_required")

        approved = self.resolver.resolve(
            registry, needs, adapter="codex-local",
            approval={"model_id": "premium-model", "reference": "user-approved-turn-8"},
        )
        self.assertEqual(approved["status"], "selected")
        self.assertTrue(approved["premium_used"])
        self.assertEqual(approved["approval_reference"], "user-approved-turn-8")

    def test_premium_approval_never_overrides_compatible_lower_cost_default(self):
        registry = {"models": [
            model("medium-model", cost="medium"),
            model("premium-model", cost="high", approval="explicit-user-approval"),
        ]}
        result = self.resolver.resolve(
            registry, requirements(), adapter="codex-local",
            approval={"model_id": "premium-model", "reference": "user-approved-turn-9"},
        )
        self.assertEqual(result["resolved_execution"]["model_id"], "medium-model")
        self.assertFalse(result["premium_used"])

    def test_filters_every_mandatory_requirement_and_reports_no_match(self):
        registry = {"models": [
            model("unavailable", availability="unavailable"),
            model("small-context", context=4000),
            model("wrong-modality", modalities=("image",)),
            model("missing-tool", tools=()),
            model("no-deep", mapping={"minimal": "low", "standard": "medium", "deep": None}),
        ]}
        result = self.resolver.resolve(
            registry,
            requirements(minimum_reasoning_class="deep"),
            adapter="codex-local",
        )
        self.assertEqual(result["status"], "no_compatible_model")
        self.assertEqual(result["compatible_count"], 0)
        self.assertIn("availability", result["rejection_summary"])
        self.assertIn("reasoning", result["rejection_summary"])

    def test_model_rename_requires_fresh_approval_but_not_policy_changes(self):
        needs = requirements(capability_tier="advanced", minimum_reasoning_class="deep")
        first = {"models": [model(
            "premium-v1", tiers=("advanced",), cost="high", approval="explicit-user-approval",
            mapping={"minimal": "low", "standard": "medium", "deep": "high"},
        )]}
        renamed = json.loads(json.dumps(first))
        renamed["models"][0]["model_id"] = "premium-v2"
        result = self.resolver.resolve(
            renamed, needs, adapter="codex-local",
            approval={"model_id": "premium-v1", "reference": "approval-before-rename"},
        )
        self.assertEqual(result["status"], "approval_required")
        self.assertEqual(result["recommended_model"]["model_id"], "premium-v2")

    def test_cli_status_codes_are_machine_readable(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            registry_path = base / "registry.json"
            requirements_path = base / "requirements.json"
            registry_path.write_text(json.dumps({"models": [model(
                "premium-model", tiers=("advanced",), cost="high", approval="explicit-user-approval",
                mapping={"minimal": "low", "standard": "medium", "deep": "high"},
            )]}), encoding="utf-8")
            requirements_path.write_text(json.dumps(requirements(
                capability_tier="advanced", minimum_reasoning_class="deep"
            )), encoding="utf-8")
            command = [sys.executable, str(SCRIPT), "--registry", str(registry_path),
                       "--requirements", str(requirements_path), "--adapter", "codex-local"]
            blocked = subprocess.run(command, text=True, capture_output=True)
            self.assertEqual(blocked.returncode, 3)
            self.assertEqual(json.loads(blocked.stdout)["status"], "approval_required")
            approved = subprocess.run(command + ["--approved-model-id", "premium-model",
                                                  "--approval-ref", "user-approved-turn-10"],
                                      text=True, capture_output=True)
            self.assertEqual(approved.returncode, 0)
            self.assertEqual(json.loads(approved.stdout)["status"], "selected")


if __name__ == "__main__":
    unittest.main()
