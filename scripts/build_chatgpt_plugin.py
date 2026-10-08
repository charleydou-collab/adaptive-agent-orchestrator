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


def source_files():
    yield MANIFEST, f"{PLUGIN_NAME}/plugin.json"
    yield COMPATIBILITY_MANIFEST, f"{PLUGIN_NAME}/.codex-plugin/plugin.json"
    yield CORE / "SKILL.md", f"{PLUGIN_NAME}/skills/{PLUGIN_NAME}/SKILL.md"
    for folder in ("references", "schemas"):
        for path in sorted((CORE / folder).glob("*")):
            if path.is_file():
                yield path, f"{PLUGIN_NAME}/skills/{PLUGIN_NAME}/{folder}/{path.name}"


def build(output):
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if manifest.get("name") != PLUGIN_NAME:
        raise ValueError("Plugin directory and manifest name must match")
    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for source, relative in source_files():
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
