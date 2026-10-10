#!/usr/bin/env python3
"""Build a deterministic skills-only Agent Plugin archive."""

import argparse
import json
from pathlib import Path
import zipfile


PROJECT = Path(__file__).resolve().parents[1]
MANIFEST = PROJECT / "adapters" / "chatgpt-web" / "plugin" / "plugin.json"
COMPATIBILITY_MANIFEST = PROJECT / "adapters" / "chatgpt-web" / "plugin" / ".codex-plugin" / "plugin.json"
CORE = PROJECT / "core" / "adaptive-agent-orchestrator"
PLUGIN_NAME = "adaptive-agent-orchestrator"
FIXED_TIME = (2026, 1, 1, 0, 0, 0)
REFERENCES = ("chat-learning.md", "context-compilation.md", "identity.md", "roles.md",
    "routing.md", "scoring-policy.md", "task-contract.md", "verification.md")
SCHEMAS = ("chat-lesson.schema.json", "chat-state-capsule.schema.json",
    "clarification-request.schema.json", "clarification-response.schema.json",
    "completion-report.schema.json", "context-audit.schema.json",
    "context-package.schema.json", "conversation-scope.schema.json",
    "episode-summary.schema.json", "learning-candidate.schema.json",
    "learning-reset-request.schema.json", "ledger-event.schema.json",
    "model-registry.schema.json", "platform-capabilities.schema.json",
    "retrieval-request.schema.json", "task-contract.schema.json")


def source_files():
    yield MANIFEST, f"{PLUGIN_NAME}/plugin.json"
    yield COMPATIBILITY_MANIFEST, f"{PLUGIN_NAME}/.codex-plugin/plugin.json"
    yield CORE / "SKILL.md", f"{PLUGIN_NAME}/skills/{PLUGIN_NAME}/SKILL.md"
    for name in REFERENCES:
        yield CORE / "references" / name, f"{PLUGIN_NAME}/skills/{PLUGIN_NAME}/references/{name}"
    for name in SCHEMAS:
        yield CORE / "schemas" / name, f"{PLUGIN_NAME}/skills/{PLUGIN_NAME}/schemas/{name}"


def build(output):
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if manifest.get("name") != PLUGIN_NAME:
        raise ValueError("Plugin directory and manifest name must match")
    compatibility = json.loads(COMPATIBILITY_MANIFEST.read_text(encoding="utf-8"))
    if compatibility.get("name") != PLUGIN_NAME or compatibility.get("version") != manifest.get("version"):
        raise ValueError("Compatibility manifest identity or version mismatch")
    extension = manifest.get("extensions", {}).get(
        "org.suncbs.adaptive-agent-orchestrator", {})
    if extension.get("sharedCore") != {
            "name": PLUGIN_NAME, "version": manifest.get("version")}:
        raise ValueError("Compatibility manifest core version mismatch")
    inventory = list(source_files())
    if len({relative for _, relative in inventory}) != len(inventory):
        raise ValueError("Duplicate archive path")
    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for source, relative in sorted(inventory, key=lambda item: item[1]):
            info = zipfile.ZipInfo(relative, FIXED_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, source.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    return output


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    print(build(args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
