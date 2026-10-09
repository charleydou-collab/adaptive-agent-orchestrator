#!/usr/bin/env python3
"""Build the deterministic Codex Adaptive Agent Orchestrator archive."""
import argparse
import json
from pathlib import Path
import zipfile


PROJECT = Path(__file__).resolve().parents[1]
CORE = PROJECT / 'core' / 'adaptive-agent-orchestrator'
ADAPTER = PROJECT / 'adapters' / 'codex'
MANIFEST = ADAPTER / 'plugin.json'
ROOT_NAME = 'adaptive-agent-orchestrator-codex'
CORE_SKILL = 'adaptive-agent-orchestrator'
FIXED_TIME = (2026, 1, 1, 0, 0, 0)
REFERENCES = ('chat-learning.md', 'context-compilation.md', 'identity.md', 'roles.md',
    'routing.md', 'scoring-policy.md', 'task-contract.md', 'verification.md')
SCHEMAS = ('chat-lesson.schema.json', 'chat-state-capsule.schema.json',
    'clarification-request.schema.json', 'clarification-response.schema.json',
    'completion-report.schema.json', 'context-audit.schema.json',
    'context-package.schema.json', 'conversation-scope.schema.json',
    'episode-summary.schema.json', 'learning-candidate.schema.json',
    'learning-reset-request.schema.json', 'ledger-event.schema.json',
    'model-registry.schema.json', 'platform-capabilities.schema.json',
    'retrieval-request.schema.json', 'task-contract.schema.json')
RUNTIME_SCRIPTS = ('chat_learning.py', 'chat_state.py', 'compile_context.py',
    'manage_agent_ledger.py', 'manage_chat_state.py', 'resolve_model.py')
ADAPTER_FILES = ('AGENTS.bootstrap.md', 'chat-state-config.example.yaml', 'config-snippet.toml',
    'execution-requirements.example.json', 'ledger-config.example.yaml',
    'model-registry.example.json', 'platform-capabilities.yaml')
AGENTS = ('artifact-producer.toml', 'data-analyst.toml', 'document-analyst.toml',
    'research-worker.toml', 'synthesis-worker.toml', 'verification-auditor.toml')


def source_files():
    yield MANIFEST, f'{ROOT_NAME}/plugin.json'
    yield CORE / 'SKILL.md', f'{ROOT_NAME}/skills/{CORE_SKILL}/SKILL.md'
    for name in REFERENCES:
        yield CORE / 'references' / name, f'{ROOT_NAME}/skills/{CORE_SKILL}/references/{name}'
    for name in SCHEMAS:
        yield CORE / 'schemas' / name, f'{ROOT_NAME}/skills/{CORE_SKILL}/schemas/{name}'
    for name in RUNTIME_SCRIPTS:
        yield CORE / 'scripts' / name, f'{ROOT_NAME}/skills/{CORE_SKILL}/scripts/{name}'
    for name in ADAPTER_FILES:
        yield ADAPTER / name, f'{ROOT_NAME}/codex/{name}'
    for name in AGENTS:
        yield ADAPTER / 'agents' / name, f'{ROOT_NAME}/codex/agents/{name}'


def build(output):
    manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
    if manifest.get('name') != ROOT_NAME or manifest.get('version') != '0.2.0':
        raise ValueError('Codex manifest identity or version mismatch')
    if manifest.get('coreSkill') != CORE_SKILL:
        raise ValueError('Codex manifest core skill mismatch')
    if tuple(manifest.get('runtime', {}).get('scripts', ())) != RUNTIME_SCRIPTS:
        raise ValueError('Codex runtime inventory mismatch')
    inventory = list(source_files())
    if len({relative for _, relative in inventory}) != len(inventory):
        raise ValueError('Duplicate archive path')
    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for source, relative in sorted(inventory, key=lambda item: item[1]):
            info = zipfile.ZipInfo(relative, FIXED_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, source.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    return output


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    print(build(args.output))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
