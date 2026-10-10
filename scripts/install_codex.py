#!/usr/bin/env python3
"""Install or safely upgrade the Codex Adaptive Agent Orchestrator adapter."""
import argparse
import hashlib
import json
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
LEGACY_SKILL_SHA256 = {
    'SKILL.md': '550bd6ffdb11f791f8edd97f354d1586bf35b4491b8d72cfe617a87bece8c397',
    'references/identity.md': '3dff1256d23c17dabe922735667954f88d605e9aecb4928fad686fe56e2d9835',
    'references/roles.md': '527f01e053898bf1015f09cc186ef57949513d318524d208ca2c857a6df0fb5e',
    'references/routing.md': '49b2f649b3e2f704ec66f9f4c557f913167d37632187b8d22a7693099a6aacc3',
    'references/scoring-policy.md': '033b2c2ed693d7e701f86049d84b2584b9d48ac08ba85cfa14ca946f026b9671',
    'references/task-contract.md': 'c5ae72da92533163876aad146f4d8fb489684d440c04e3c56721173c66d7288f',
    'references/verification.md': '474b4d34030147b5bba3f1ab514c48c5e1323e696c680bb5d9f44a7da97c63c1',
    'schemas/clarification-request.schema.json': '407154e18a2cfdb7d3951d4548e7d5aec64fe116233ae596d78257a23899f24f',
    'schemas/clarification-response.schema.json': 'cf34791766763477cfb52c21e5cc6661fe31c5d56d2474542a28680fb9ccb047',
    'schemas/completion-report.schema.json': '6e747f520ac2ff53d19b25a02d190898c87e537a8e8616479531fb32a49a9341',
    'schemas/ledger-event.schema.json': '9bff02c585f15c9eb0926299163665c04fb641418f9b9c874e862beca10338a3',
    'schemas/model-registry.schema.json': '732b246cb7985ad424388b4d4965e9d4f3281dce93e472529947d355790ca362',
    'schemas/platform-capabilities.schema.json': '5369f15b6d274d5a591850b545e274034bdb7e6727948b8d0e45573d2791e852',
    'schemas/task-contract.schema.json': 'ef7c243a3199707e3080e3bfdb259567f973764960e635027e3789db95ad82ea',
    'scripts/manage_agent_ledger.py': '33f35784048bcbe7dceb73a0d9216ed950078e41064d8d10b8f534fee02a268d',
    'scripts/resolve_model.py': 'cac4f1a1edc73208580cffda37e6c806877592f62bcf3c731d00dfc5ff47b20a',
}
LEGACY_AGENT_SHA256 = {
    'artifact-producer.toml': 'd5830011ba3b56d6e8ae1b6a0b699b74b23c9f70de9ca4db5f84b83c104c9911',
    'data-analyst.toml': '4dec9d8e9c61d738d502b731f288e15b5c801e97ac499ab57d46a1be600f4b86',
    'document-analyst.toml': 'e713261f58a6f393b64fda9af0c1853d238e13dd2d91bff1394cc8a8ded50557',
    'research-worker.toml': '877d36219b3a5c9f5dbf051ac3081d9e37709720b35626d24f9d5a782b433697',
    'synthesis-worker.toml': 'd8bc40aefbafdf6e58d4cf8d1a13a44c90e13f8854fab8ad6aa6b7525b676b91',
    'verification-auditor.toml': '8b6f4c592f6d664d595fdc563c8d027a4a5d914e04d8c39e67de2ee04d08d387',
}
LEGACY_BOOTSTRAP_SHA256 = '16778c4fc706e2fc18fd8c9a8a915ef1243a7ae13fdbeb66424795c5d0095b42'


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


def _unique_tree_backup(path, label):
    base = path.with_name(path.name + '.pre-adaptive-orchestrator-' + label)
    candidate, serial = base, 0
    while candidate.exists():
        serial += 1
        candidate = path.with_name(base.name + '.' + str(serial))
    shutil.copytree(path, candidate)
    return candidate


def _sha256_bytes(value):
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path):
    return _sha256_bytes(path.read_bytes())


def _managed_digest(path, relative):
    if relative.endswith('.json'):
        value = json.loads(path.read_text(encoding='utf-8'))
        canonical = json.dumps(value, ensure_ascii=False, separators=(',', ':'),
            sort_keys=True).encode('utf-8')
        return _sha256_bytes(canonical)
    return _sha256_file(path)


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


def _validate_upgrade(config_text, skill_target, agent_target, bootstrap_target,
        allow_modified_bootstrap=False):
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
    actual_skill_files = {
        path.relative_to(skill_target).as_posix()
        for path in skill_target.rglob('*')
        if path.is_file()
        and path != marker
        and '__pycache__' not in path.parts
        and path.suffix != '.pyc'
    }
    if actual_skill_files != set(LEGACY_SKILL_SHA256):
        raise ValueError('upgrade refused: modified or unexpected v0.1.3 skill files')
    for relative, expected in LEGACY_SKILL_SHA256.items():
        if _managed_digest(skill_target / relative, relative) != expected:
            raise ValueError('upgrade refused: modified v0.1.3 skill file: ' + relative)
    for name, expected in LEGACY_AGENT_SHA256.items():
        if _sha256_file(agent_target / name) != expected:
            raise ValueError('upgrade refused: modified v0.1.3 agent file: ' + name)
    inner = bootstrap[bootstrap.index(START) + len(START):bootstrap.index(END)].strip() + '\n'
    if (not allow_modified_bootstrap
            and _sha256_bytes(inner.encode('utf-8')) != LEGACY_BOOTSTRAP_SHA256):
        raise ValueError('upgrade refused: modified v0.1.3 bootstrap block')
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


def _upgrade(codex_home, agents_home, config, config_text,
        allow_modified_bootstrap=False):
    skill_target = agents_home / 'skills' / 'adaptive-agent-orchestrator'
    agent_target = codex_home / 'agents'
    bootstrap_target = codex_home / 'AGENTS.md'
    old_bootstrap = _validate_upgrade(config_text, skill_target, agent_target,
        bootstrap_target, allow_modified_bootstrap)
    pattern = re.compile(re.escape(START) + r'.*?' + re.escape(END) + r'\n?', re.DOTALL)
    replaced, count = pattern.subn(_block(), old_bootstrap)
    if count != 1:
        raise ValueError('ambiguous managed bootstrap block')

    config_backup = _unique_backup(config, 'upgrade-' + VERSION)
    bootstrap_backup = _unique_backup(bootstrap_target, 'upgrade-' + VERSION)
    skill_backup = _unique_tree_backup(skill_target, 'upgrade-' + VERSION)
    agent_backup = _unique_tree_backup(agent_target, 'upgrade-' + VERSION)

    staging_root, staged = _stage_skill(skill_target.parent)
    skill_transaction = Path(tempfile.mkdtemp(
        prefix='.adaptive-agent-orchestrator-old.', dir=skill_target.parent))
    old_skill = skill_transaction / 'adaptive-agent-orchestrator'
    agent_stage = Path(tempfile.mkdtemp(prefix='.adaptive-agent-agents-new.', dir=agent_target))
    agent_transaction = Path(tempfile.mkdtemp(prefix='.adaptive-agent-agents-old.', dir=agent_target))
    for name in AGENT_NAMES:
        shutil.copy2(ADAPTER / 'agents' / name, agent_stage / name)

    try:
        os.replace(skill_target, old_skill)
        os.replace(staged, skill_target)
        for name in AGENT_NAMES:
            os.replace(agent_target / name, agent_transaction / name)
            os.replace(agent_stage / name, agent_target / name)
        _atomic_text(bootstrap_target, replaced)
    except Exception:
        rollback_errors = []
        try:
            _atomic_text(bootstrap_target, old_bootstrap)
        except Exception as exc:
            rollback_errors.append('bootstrap: ' + str(exc))
        for name in reversed(AGENT_NAMES):
            original = agent_transaction / name
            if original.exists():
                try:
                    replacement = agent_target / name
                    if replacement.exists():
                        os.replace(replacement, agent_stage / (name + '.failed'))
                    os.replace(original, replacement)
                except Exception as exc:
                    rollback_errors.append(name + ': ' + str(exc))
        if old_skill.exists():
            try:
                if skill_target.exists():
                    os.replace(skill_target, staging_root / 'failed-adaptive-agent-orchestrator')
                os.replace(old_skill, skill_target)
            except Exception as exc:
                rollback_errors.append('skill: ' + str(exc))
        if rollback_errors:
            raise OSError('upgrade failed and rollback was incomplete: '
                + '; '.join(rollback_errors))
        raise
    finally:
        shutil.rmtree(agent_stage, ignore_errors=True)
        shutil.rmtree(agent_transaction, ignore_errors=True)
        shutil.rmtree(staging_root, ignore_errors=True)
        shutil.rmtree(skill_transaction, ignore_errors=True)
    return {'skill': str(skill_target), 'agents': str(agent_target),
        'bootstrap': str(bootstrap_target), 'config_backup': str(config_backup),
        'bootstrap_backup': str(bootstrap_backup), 'skill_backup': str(skill_backup),
        'agent_backup': str(agent_backup), 'version': VERSION, 'mode': 'upgrade',
        'custom_bootstrap_migrated': bool(allow_modified_bootstrap)}


def install(codex_home: Path, agents_home: Path, upgrade: bool = False,
        allow_modified_bootstrap: bool = False) -> dict:
    codex_home = Path(codex_home).resolve()
    agents_home = Path(agents_home).resolve()
    config = codex_home / 'config.toml'
    if not config.is_file():
        raise ValueError('Codex config.toml does not exist')
    config_text = config.read_text(encoding='utf-8')
    if allow_modified_bootstrap and not upgrade:
        raise ValueError('--migrate-custom-bootstrap requires --upgrade')
    return (_upgrade(codex_home, agents_home, config, config_text,
        allow_modified_bootstrap) if upgrade
        else _fresh_install(codex_home, agents_home, config, config_text))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--codex-home', type=Path, required=True)
    parser.add_argument('--agents-home', type=Path, required=True)
    parser.add_argument('--upgrade', action='store_true')
    parser.add_argument('--migrate-custom-bootstrap', action='store_true',
        help='replace a customized v0.1.3 managed bootstrap after backing it up; '
             'all other managed v0.1.3 files must still match exactly')
    args = parser.parse_args(argv)
    try:
        result = install(args.codex_home, args.agents_home, args.upgrade,
            args.migrate_custom_bootstrap)
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    for key, value in result.items():
        print(f'{key}: {value}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
