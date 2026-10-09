#!/usr/bin/env python3
"""Install or safely upgrade the Codex Adaptive Agent Orchestrator adapter."""
import argparse
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile


PROJECT = Path(__file__).resolve().parents[1]
CORE = PROJECT / 'core' / 'adaptive-agent-orchestrator'
ADAPTER = PROJECT / 'adapters' / 'codex'
START = '<!-- adaptive-agent-orchestrator:start -->'
END = '<!-- adaptive-agent-orchestrator:end -->'
VERSION = '0.2.0'
LEGACY_VERSION = '0.1.3'
AGENT_NAMES = ('artifact-producer.toml', 'data-analyst.toml', 'document-analyst.toml',
    'research-worker.toml', 'synthesis-worker.toml', 'verification-auditor.toml')


def _block():
    return f"{START}\n{(ADAPTER / 'AGENTS.bootstrap.md').read_text(encoding='utf-8').strip()}\n{END}\n"


def _unique_backup(path, label):
    base = path.with_name(path.name + '.pre-adaptive-orchestrator-' + label)
    candidate, serial = base, 0
    while candidate.exists():
        serial += 1
        candidate = path.with_name(base.name + '.' + str(serial))
    shutil.copy2(path, candidate)
    return candidate


def _atomic_text(path, text):
    descriptor, temporary = tempfile.mkstemp(prefix='.' + path.name + '.', suffix='.tmp', dir=path.parent)
    temporary_path = Path(temporary)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


def _stage_skill(parent):
    staging_root = Path(tempfile.mkdtemp(prefix='.adaptive-agent-orchestrator.', dir=parent))
    staged = staging_root / 'adaptive-agent-orchestrator'
    shutil.copytree(CORE, staged)
    config = staged / 'config'
    config.mkdir()
    shutil.copy2(ADAPTER / 'chat-state-config.example.yaml', config / 'chat-state-config.example.yaml')
    shutil.copy2(ADAPTER / 'ledger-config.example.yaml', config / 'ledger-config.example.yaml')
    (staged / '.adaptive-agent-orchestrator-version').write_text(VERSION + '\n', encoding='utf-8')
    return staging_root, staged


def _validate_upgrade(config_text, skill_target, agent_target, bootstrap_target):
    snippet = (ADAPTER / 'config-snippet.toml').read_text(encoding='utf-8').strip()
    complete = (skill_target.is_dir() and bootstrap_target.is_file()
        and all((agent_target / name).is_file() for name in AGENT_NAMES)
        and config_text.count('[agents]') == 1 and snippet in config_text)
    if not complete:
        raise ValueError('ambiguous or partial adaptive orchestrator installation')
    bootstrap = bootstrap_target.read_text(encoding='utf-8')
    if bootstrap.count(START) != 1 or bootstrap.count(END) != 1 or bootstrap.index(START) > bootstrap.index(END):
        raise ValueError('ambiguous or partial adaptive orchestrator installation')
    marker = skill_target / '.adaptive-agent-orchestrator-version'
    if marker.exists():
        if marker.read_text(encoding='utf-8').strip() != LEGACY_VERSION:
            raise ValueError('upgrade requires an exact v0.1.3 installation')
    else:
        legacy_files = ('SKILL.md', 'references/identity.md', 'references/roles.md',
            'references/routing.md', 'references/scoring-policy.md',
            'references/task-contract.md', 'references/verification.md',
            'scripts/manage_agent_ledger.py', 'scripts/resolve_model.py')
        if not all((skill_target / name).is_file() for name in legacy_files):
            raise ValueError('ambiguous or partial adaptive orchestrator installation')
        if (skill_target / 'references/chat-learning.md').exists():
            raise ValueError('upgrade requires an exact v0.1.3 installation')
    return bootstrap


def _fresh_install(codex_home, agents_home, config, config_text):
    skill_target = agents_home / 'skills' / 'adaptive-agent-orchestrator'
    agent_target = codex_home / 'agents'
    bootstrap_target = codex_home / 'AGENTS.md'
    if re.search(r'(?m)^\[agents\]\s*$', config_text):
        raise ValueError('config.toml already contains [agents]; merge manually')
    if skill_target.exists():
        raise ValueError('adaptive-agent-orchestrator skill already exists')
    collisions = [name for name in AGENT_NAMES if (agent_target / name).exists()]
    if collisions:
        raise ValueError('custom agent files already exist: ' + ', '.join(collisions))
    existing_bootstrap = bootstrap_target.read_text(encoding='utf-8') if bootstrap_target.exists() else ''
    if START in existing_bootstrap or END in existing_bootstrap:
        raise ValueError('adaptive orchestration bootstrap already exists')

    skill_target.parent.mkdir(parents=True, exist_ok=True)
    agent_target.mkdir(parents=True, exist_ok=True)
    backup = codex_home / 'config.toml.pre-adaptive-orchestrator'
    if backup.exists():
        raise ValueError('configuration backup already exists')
    shutil.copy2(config, backup)
    staging_root, staged = _stage_skill(skill_target.parent)
    try:
        os.replace(staged, skill_target)
    finally:
        shutil.rmtree(staging_root, ignore_errors=True)
    for name in AGENT_NAMES:
        shutil.copy2(ADAPTER / 'agents' / name, agent_target / name)
    prefix = existing_bootstrap.rstrip()
    _atomic_text(bootstrap_target, (prefix + '\n\n' if prefix else '') + _block())
    snippet = (ADAPTER / 'config-snippet.toml').read_text(encoding='utf-8').strip()
    _atomic_text(config, config_text.rstrip() + '\n\n' + snippet + '\n')
    return {'skill': str(skill_target), 'agents': str(agent_target),
        'bootstrap': str(bootstrap_target), 'config_backup': str(backup),
        'version': VERSION, 'mode': 'fresh'}


def _upgrade(codex_home, agents_home, config, config_text):
    skill_target = agents_home / 'skills' / 'adaptive-agent-orchestrator'
    agent_target = codex_home / 'agents'
    bootstrap_target = codex_home / 'AGENTS.md'
    old_bootstrap = _validate_upgrade(config_text, skill_target, agent_target, bootstrap_target)
    config_backup = _unique_backup(config, 'upgrade-' + VERSION)
    bootstrap_backup = _unique_backup(bootstrap_target, 'upgrade-' + VERSION)

    staging_root, staged = _stage_skill(skill_target.parent)
    old_root = Path(tempfile.mkdtemp(prefix='.adaptive-agent-orchestrator-old.', dir=skill_target.parent))
    old_skill = old_root / 'adaptive-agent-orchestrator'
    try:
        os.replace(skill_target, old_skill)
        try:
            os.replace(staged, skill_target)
        except Exception:
            os.replace(old_skill, skill_target)
            raise
        shutil.rmtree(old_skill)
    finally:
        shutil.rmtree(staging_root, ignore_errors=True)
        shutil.rmtree(old_root, ignore_errors=True)

    agent_stage = Path(tempfile.mkdtemp(prefix='.adaptive-agent-agents.', dir=agent_target))
    try:
        for name in AGENT_NAMES:
            staged_agent = agent_stage / name
            shutil.copy2(ADAPTER / 'agents' / name, staged_agent)
            os.replace(staged_agent, agent_target / name)
    finally:
        shutil.rmtree(agent_stage, ignore_errors=True)

    pattern = re.compile(re.escape(START) + r'.*?' + re.escape(END) + r'\n?', re.DOTALL)
    replaced, count = pattern.subn(_block(), old_bootstrap)
    if count != 1:
        raise ValueError('ambiguous managed bootstrap block')
    _atomic_text(bootstrap_target, replaced)
    return {'skill': str(skill_target), 'agents': str(agent_target),
        'bootstrap': str(bootstrap_target), 'config_backup': str(config_backup),
        'bootstrap_backup': str(bootstrap_backup), 'version': VERSION, 'mode': 'upgrade'}


def install(codex_home: Path, agents_home: Path, upgrade: bool = False) -> dict:
    codex_home = Path(codex_home).resolve()
    agents_home = Path(agents_home).resolve()
    config = codex_home / 'config.toml'
    if not config.is_file():
        raise ValueError('Codex config.toml does not exist')
    config_text = config.read_text(encoding='utf-8')
    return (_upgrade(codex_home, agents_home, config, config_text) if upgrade
        else _fresh_install(codex_home, agents_home, config, config_text))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--codex-home', type=Path, required=True)
    parser.add_argument('--agents-home', type=Path, required=True)
    parser.add_argument('--upgrade', action='store_true')
    args = parser.parse_args(argv)
    try:
        result = install(args.codex_home, args.agents_home, args.upgrade)
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    for key, value in result.items():
        print(f'{key}: {value}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
