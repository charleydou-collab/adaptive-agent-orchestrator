#!/usr/bin/env python3
"""Install the portable skill and Codex adapter without changing main model settings."""

import argparse
from pathlib import Path
import re
import shutil
import sys


PROJECT = Path(__file__).resolve().parents[1]
CORE = PROJECT / "core" / "adaptive-agent-orchestrator"
ADAPTER = PROJECT / "adapters" / "codex"
START = "<!-- adaptive-agent-orchestrator:start -->"
END = "<!-- adaptive-agent-orchestrator:end -->"


def install(codex_home, agents_home):
    codex_home = Path(codex_home).resolve()
    agents_home = Path(agents_home).resolve()
    config = codex_home / "config.toml"
    if not config.is_file():
        raise ValueError("Codex config.toml does not exist")
    config_text = config.read_text(encoding="utf-8")
    if re.search(r"(?m)^\[agents\]\s*$", config_text):
        raise ValueError("config.toml already contains [agents]; merge manually")

    skill_target = agents_home / "skills" / "adaptive-agent-orchestrator"
    agent_target = codex_home / "agents"
    bootstrap_target = codex_home / "AGENTS.md"
    if skill_target.exists():
        raise ValueError("adaptive-agent-orchestrator skill already exists")
    collisions = [source.name for source in (ADAPTER / "agents").glob("*.toml") if (agent_target / source.name).exists()]
    if collisions:
        raise ValueError("custom agent files already exist: " + ", ".join(sorted(collisions)))
    existing_bootstrap = bootstrap_target.read_text(encoding="utf-8") if bootstrap_target.exists() else ""
    if START in existing_bootstrap or END in existing_bootstrap:
        raise ValueError("adaptive orchestration bootstrap already exists")

    codex_home.mkdir(parents=True, exist_ok=True)
    skill_target.parent.mkdir(parents=True, exist_ok=True)
    agent_target.mkdir(parents=True, exist_ok=True)
    backup = codex_home / "config.toml.pre-adaptive-orchestrator"
    if backup.exists():
        raise ValueError("configuration backup already exists")
    shutil.copy2(config, backup)

    shutil.copytree(CORE, skill_target)
    for source in sorted((ADAPTER / "agents").glob("*.toml")):
        shutil.copy2(source, agent_target / source.name)

    block = f"{START}\n{(ADAPTER / 'AGENTS.bootstrap.md').read_text(encoding='utf-8').strip()}\n{END}\n"
    prefix = existing_bootstrap.rstrip()
    bootstrap_target.write_text((prefix + "\n\n" if prefix else "") + block, encoding="utf-8")
    snippet = (ADAPTER / "config-snippet.toml").read_text(encoding="utf-8").strip()
    config.write_text(config_text.rstrip() + "\n\n" + snippet + "\n", encoding="utf-8")
    return {"skill": str(skill_target), "agents": str(agent_target), "bootstrap": str(bootstrap_target), "config_backup": str(backup)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex-home", type=Path, required=True)
    parser.add_argument("--agents-home", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = install(args.codex_home, args.agents_home)
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    for key, value in result.items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
