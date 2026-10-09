import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "core" / "adaptive-agent-orchestrator"
SKILL = SKILL_ROOT / "SKILL.md"


class SkillPackageTests(unittest.TestCase):
    def setUp(self):
        self.text = SKILL.read_text(encoding="utf-8")
        self.all_text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in [SKILL, *sorted((SKILL_ROOT / "references").glob("*.md"))]
        ).lower()

    def test_frontmatter_and_discovery(self):
        self.assertTrue(self.text.startswith("---\n"))
        self.assertIn("name: adaptive-agent-orchestrator", self.text)
        match = re.search(r"^description:\s*(.+)$", self.text, re.MULTILINE)
        self.assertIsNotNone(match)
        self.assertTrue(match.group(1).startswith("Use when"))

    def test_linked_resources_exist(self):
        links = re.findall(r"\[[^]]+\]\(([^)]+)\)", self.text)
        self.assertGreaterEqual(len(links), 7)
        for link in links:
            if "://" not in link:
                self.assertTrue((SKILL_ROOT / link).exists(), link)

    def test_core_is_provider_neutral(self):
        forbidden = ("gpt-", "claude-", "gemini-", "~/.codex", "spawn_agent", "openai.yaml")
        for token in forbidden:
            self.assertNotIn(token, self.all_text)

    def test_routing_and_fallback_contracts(self):
        for token in ("economy", "balanced", "advanced", "specialist", "minimal", "standard", "deep"):
            self.assertIn(token, self.all_text)
        self.assertRegex(
            self.all_text,
            re.compile(r"native parallel.*native sequential.*sequential role simulation.*direct", re.DOTALL),
        )
        self.assertIn("display-name", self.all_text)

    def test_premium_models_require_explicit_user_approval(self):
        routing = (SKILL_ROOT / "references" / "routing.md").read_text(encoding="utf-8").lower()
        skill = SKILL.read_text(encoding="utf-8").lower()
        for token in ("premium", "explicit user approval", "exact model", "low- or medium-cost"):
            self.assertIn(token, routing)
        self.assertIn("premium", skill)
        self.assertIn("approval", skill)

    def test_concurrency_and_recovery_contracts(self):
        self.assertRegex(self.all_text, r"desired concurrency[^\n]*3")
        self.assertRegex(self.all_text, r"authorized ceiling[^\n]*5")
        self.assertIn("one same-tier correction", self.all_text)
        self.assertIn("one automatic escalation", self.all_text)
        self.assertIn("user direction", self.all_text)

    def test_verification_and_scoring_contracts(self):
        for label in ("independent-worker", "independent-model", "temporally-separated-self-review", "single-pass-self-review"):
            self.assertIn(label, self.all_text)
        for token in ("initial score", "100", "200", "floor", "silence is not praise"):
            self.assertIn(token, self.all_text)

    def test_user_controls_and_visibility(self):
        for directive in ("[direct]", "[audit]", "[no-score-update]", "scorecard", "retire", "reset"):
            self.assertIn(directive, self.all_text)
        self.assertIn("silent by default", self.all_text)

    def test_chat_learning_controls_are_portable(self):
        for directive in (
            "[no-learn]", "[learn]", "show chat learning", "show proposed lessons",
            "forget lesson", "reset chat learning", "compact chat context",
            "[full-context]", "[context-audit]",
        ):
            self.assertIn(directive, self.all_text)

    def test_feedback_revision_precedes_learning_and_activation_is_management_only(self):
        learning = (SKILL_ROOT / "references" / "chat-learning.md").read_text(encoding="utf-8").lower()
        self.assertRegex(learning, re.compile(r"revise.*verify.*candidate", re.DOTALL))
        self.assertRegex(learning, r"management agent\s+alone")
        self.assertIn("workers may propose", learning)
        self.assertIn("ordinary execution continues without learning", learning)
        self.assertIn("fail closed", learning)

    def test_context_compilation_limits_workers_and_preserves_mandatory_content(self):
        context = (SKILL_ROOT / "references" / "context-compilation.md").read_text(encoding="utf-8").lower()
        for token in ("3,400", "5,900", "five", "three", "capacity blocker", "rehydrat"):
            self.assertIn(token, context)
        self.assertIn("required source inputs", context)
        self.assertIn("never silently", context)

    def test_learning_and_scoring_are_separate(self):
        scoring = (SKILL_ROOT / "references" / "scoring-policy.md").read_text(encoding="utf-8").lower()
        for token in ("lesson text", "learning candidate", "chat capsule", "must not"):
            self.assertIn(token, scoring)

    def test_examples_and_operational_boundaries(self):
        for phrase in ("document summary", "word/excel", "knowledge-base-driven image"):
            self.assertIn(phrase, self.all_text)
        for forbidden in ("fear of death", "literal permanence", "consciousness"):
            self.assertNotIn(forbidden, self.all_text)
        self.assertIn("administrative retirement", self.all_text)


if __name__ == "__main__":
    unittest.main()
