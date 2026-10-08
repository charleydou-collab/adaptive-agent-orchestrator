# Installation and configuration

## Requirements

- Python 3.8 or newer for the installer, builder, tests, and ledger CLI.
- A host that supports skill or prompt instructions.
- Native workers only when the target host exposes them.
- Durable local storage only when persistent scoring is desired.

The core has no third-party Python dependencies.

## Codex adapter

### Automated installation

Run from the repository root:

```bash
python3 scripts/install_codex.py \
  --codex-home "$HOME/.codex" \
  --agents-home "$HOME/.agents"
```

The installer:

1. checks that `config.toml` exists;
2. refuses an existing `[agents]` table because an automatic merge would be ambiguous;
3. checks for skill, role-file, bootstrap-marker, and backup collisions;
4. copies `config.toml` to `config.toml.pre-adaptive-orchestrator`;
5. copies the core skill to `$AGENTS_HOME/skills/adaptive-agent-orchestrator`;
6. copies six role definitions to `$CODEX_HOME/agents`;
7. appends the bounded bootstrap to `$CODEX_HOME/AGENTS.md`;
8. appends the agent registry to `$CODEX_HOME/config.toml`.

The installer does not change the main `model` or `model_reasoning_effort`. Per-worker model names are intentionally absent from the bundled role definitions. The runtime should resolve available targets from verified capabilities.

### Manual merge

If `[agents]` already exists, merge [`config-snippet.toml`](../adapters/codex/config-snippet.toml) manually. Preserve existing role names and paths, and resolve collisions explicitly. Copy the core skill and only the role files you intend to register.

The bundled role files are:

- `research-worker`
- `document-analyst`
- `data-analyst`
- `synthesis-worker`
- `artifact-producer`
- `verification-auditor`

### Capability registry

[`platform-capabilities.yaml`](../adapters/codex/platform-capabilities.yaml) is a declaration template, not a live model inventory. Populate the adapter registry from the current runtime. For each target, validate:

- provider and exact model/version identifier;
- capability tier and cost rank;
- minimum and maximum context properties;
- supported tools and modalities;
- supported concrete effort settings;
- mappings from `minimal`, `standard`, and `deep` reasoning classes;
- availability in the current account, workspace, and region.

If a model is renamed or removed, refresh the registry and select a capability-equivalent target. Do not hard-code aliases in the portable core.

## Persistent ledger

Create the parent directory before initialization:

```bash
mkdir -p .codex/adaptive-agent-orchestrator
python3 core/adaptive-agent-orchestrator/scripts/manage_agent_ledger.py \
  init \
  --ledger .codex/adaptive-agent-orchestrator/agent-ledger.json \
  --scope workspace
chmod 600 .codex/adaptive-agent-orchestrator/agent-ledger.json
```

Use [`ledger-config.example.yaml`](../adapters/codex/ledger-config.example.yaml) to record portable paths. Environment placeholders are documentation conventions; the ledger CLI does not expand YAML or environment variables itself.

The orchestrator must serialize writers. Atomic replacement protects against partial JSON writes but does not lock out concurrent processes.

## ChatGPT web adapter

### Build

```bash
python3 scripts/build_chatgpt_plugin.py \
  --output dist/adaptive-agent-orchestrator.zip
```

The archive has one root directory and includes only:

- `plugin.json`;
- the core `SKILL.md`;
- references;
- JSON Schemas.

It excludes the local ledger script because ordinary ChatGPT web plugins do not provide a trustworthy local persistence path for it.

### Activate

1. Upload the ZIP using the plugin creation flow available to the workspace.
2. Add the full contents of [`custom-instructions-bootstrap.md`](../adapters/chatgpt-web/custom-instructions-bootstrap.md) to **Settings → Personalization → Custom Instructions**.
3. Explicitly select `@Adaptive Agent Orchestrator` for work where reliable activation matters.
4. Use `[audit]` to verify the actual fallback mode and exposed controls.

Custom Instructions influence default behavior but do not guarantee that a particular plugin, model, tool, or subagent will run.

## Generic adapter

Use [`system-prompt.md`](../adapters/generic-prompt/system-prompt.md) as the management instruction. Copy [`platform-capabilities.example.yaml`](../adapters/generic-prompt/platform-capabilities.example.yaml), then change only values proven by the target system.

If the platform exposes no workers, use temporally separated role simulation. If it exposes no per-task model selector, keep model resolution with the platform default. If it exposes no durable storage, disable score updates and label scoring unavailable.

## Prompt controls

| Control | Effect |
| --- | --- |
| `[direct]` | Forbids worker delegation for the request; the management agent still owns verification |
| `[audit]` | Requests role, routing, KPI, fallback, verification, persistence, and score-event details |
| `[no-score-update]` | Records a frozen event only when a ledger is available; otherwise performs no score mutation |
| `show agent scorecard` | Displays only ledger metadata accessible on the active platform |

## Uninstallation

There is no destructive automated uninstaller. Restore the backed-up configuration only after comparing it with subsequent user changes. Remove the marked bootstrap block, registered role entries, copied role files, and copied skill manually. Preserve or archive the ledger according to the workspace's retention policy.

