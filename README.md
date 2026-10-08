# Adaptive Agent Orchestrator

Adaptive Agent Orchestrator is a model-neutral orchestration skill for decomposing complex AI work, assigning bounded specialist roles, routing work by capability instead of model branding, verifying outputs against measurable KPIs, and integrating only accepted results.

The repository includes a portable core skill, adapters for Codex, ChatGPT web, and generic prompt-based systems, JSON Schemas for task and completion contracts, and a deterministic local performance ledger for platforms that support durable storage.

> Status: `0.1.3` is an early public release. The core package and tests are usable. Public ChatGPT directory submission still requires the publisher's verified identity, hosted policy/support URLs, and final portal validation.

## What it does

- Treats one management agent as accountable for interpretation, decomposition, routing, verification, and final delivery.
- Keeps simple work direct when delegation would add cost without improving quality or latency.
- Assigns complex work to functional roles such as research worker, document analyst, data analyst, synthesis worker, artifact producer, and verification auditor.
- Defines measurable task contracts and structured completion reports with closed JSON Schemas.
- Selects the least costly execution target that satisfies declared context, modality, tool, reasoning, and quality requirements.
- Defaults to low- or medium-cost targets and blocks premium dispatch until the user approves the exact proposed model after receiving a task-specific explanation.
- Runs independent tasks concurrently when the host supports native workers, with desired concurrency `3` and an authorized ceiling of `5`.
- Degrades honestly to native sequential workers, sequential role simulation, or direct execution when native parallel workers are unavailable.
- Applies one same-capability repair and one capability/reasoning escalation before asking the user to authorize further attempts.
- Relays material worker questions through the management agent with correlated choices, a recommendation, and a custom-response path, while unrelated work continues.
- Optionally maintains a local, metadata-only score ledger for reusable operational identities. Scoring never grants authority or overrides truthfulness, safety, permissions, or user intent.

## Architecture

```mermaid
flowchart LR
    U[User request] --> M[Management agent]
    M --> I[Interpret and decompose]
    I --> R[Capability router]
    R --> W1[Bounded worker role]
    R --> W2[Bounded worker role]
    R --> W3[Bounded worker role]
    W1 --> C[Structured completion reports]
    W2 --> C
    W3 --> C
    W1 -->|needs input| Q[Clarification relay]
    Q -->|choices plus custom response| U
    U -->|correlated answer| Q
    Q --> W1
    C --> V[Verification against KPIs and evidence]
    V -->|accepted| F[Integrated final result]
    V -->|repairable| X[Correction or escalation]
    X --> W1
    V -->|verified outcome| L[(Optional metadata ledger)]
```

The core contains policy and portable contracts. Each adapter declares what its host can actually do: worker delegation, model resolution, effort controls, tools, modalities, persistence, and activation. The adapter owns provider-specific model identifiers; the core never routes by model-name patterns.

The deterministic resolver at `core/adaptive-agent-orchestrator/scripts/resolve_model.py` filters a refreshed registry by availability, capability tier, context, modalities, tools, and reasoning mapping. It selects the least costly compatible non-premium target. If only premium targets qualify, it returns `approval_required` with the exact recommendation and explanation instead of dispatching.

See [Architecture](docs/ARCHITECTURE.md) for component boundaries and execution flow.

## Platform behavior

| Surface | Native subagents | Per-worker model selection | Persistent scoring | Activation |
| --- | --- | --- | --- | --- |
| Codex adapter | Declared as supported, subject to host limits | Capability registry resolves available targets | Workspace-scoped local ledger | Global bootstrap plus skill |
| ChatGPT web adapter | Conservatively declared unavailable | Not claimed | Not claimed | Custom Instructions plus explicit plugin selection |
| Generic prompt adapter | Not assumed | Not assumed | Not assumed | System/developer prompt |

The ChatGPT web adapter deliberately uses sequential role simulation unless the current surface exposes stronger capabilities. Selecting the plugin does not create hidden model controls or persistent state.

## Repository layout

```text
adaptive-agent-orchestrator/
├── adapters/
│   ├── chatgpt-web/       # Skills-only plugin manifest and Custom Instructions
│   ├── codex/             # Agent definitions, bootstrap, capability declaration
│   └── generic-prompt/    # Vendor-neutral system prompt and capability template
├── core/
│   └── adaptive-agent-orchestrator/
│       ├── SKILL.md       # Portable orchestration workflow
│       ├── references/    # Routing, roles, verification, identity, scoring
│       ├── schemas/       # Closed task, report, capability, and ledger schemas
│       └── scripts/       # Deterministic metadata ledger CLI
├── docs/                  # Technical and operational documentation
├── scripts/               # Installer and deterministic plugin builder
└── tests/                 # Standard-library unit and integration tests
```

## Quick start

### Codex

The installer copies the skill and six role definitions, appends the bounded agent configuration, adds the global bootstrap, and preserves the existing top-level model and reasoning-effort settings.

```bash
python3 scripts/install_codex.py \
  --codex-home "$HOME/.codex" \
  --agents-home "$HOME/.agents"
```

Safety behavior:

- creates `config.toml.pre-adaptive-orchestrator` before modifying configuration;
- refuses to overwrite an existing skill, role file, bootstrap block, backup, or `[agents]` table;
- never rewrites the configured main model or `model_reasoning_effort`;
- requires manual merging when an existing agent configuration is present.

Initialize a workspace ledger only if you want durable operational scoring:

```bash
mkdir -p .codex/adaptive-agent-orchestrator
python3 "$HOME/.agents/skills/adaptive-agent-orchestrator/scripts/manage_agent_ledger.py" \
  init \
  --ledger .codex/adaptive-agent-orchestrator/agent-ledger.json \
  --scope workspace
chmod 600 .codex/adaptive-agent-orchestrator/agent-ledger.json
```

Then connect the bootstrap to the paths described in [`ledger-config.example.yaml`](adapters/codex/ledger-config.example.yaml). Serialize all writes; atomic replacement prevents partial files but is not a multi-writer transaction lock.

### ChatGPT web

Build the skills-only plugin archive:

```bash
python3 scripts/build_chatgpt_plugin.py \
  --output dist/adaptive-agent-orchestrator.zip
```

Upload the ZIP through the ChatGPT plugin workflow available to your workspace. Add the contents of [`custom-instructions-bootstrap.md`](adapters/chatgpt-web/custom-instructions-bootstrap.md) to Custom Instructions for default management-agent behavior. For important tasks, explicitly select `@Adaptive Agent Orchestrator` because Custom Instructions do not guarantee plugin invocation.

The web package contains the manifest, skill, references, and schemas. It intentionally excludes the local ledger CLI and does not claim native subagents, per-worker model control, or cross-session scoring on ordinary ChatGPT web surfaces.

### Generic AI systems

Use [`system-prompt.md`](adapters/generic-prompt/system-prompt.md) as a system or developer instruction, then replace the example capability declaration with values verified for the target runtime. Do not advertise native workers, model selection, tools, or persistence unless the host actually exposes them.

## User controls

- `[direct]` — keep execution with the management agent.
- `[audit]` — show roles, routing, KPIs, verification strength, fallbacks, and genuine score events.
- `[no-score-update]` — verify normally while freezing score changes.
- `show agent scorecard` — show score metadata genuinely available on the current platform.

Premium approval is deliberately not a reusable global preference. It is bound to the current task and exact model identifier. A model rename, substitution, retry, or escalation requires a fresh routing decision and, when still premium, fresh approval.

## Verification and tests

The suite validates package structure, deterministic builds, adapter honesty, bounded concurrency, model-neutral contracts, installer safeguards, schema closure, and ledger invariants.

```bash
python3 -m unittest discover -s tests -v
```

The build is deterministic: identical source inputs produce byte-identical ZIP archives with fixed timestamps, ordering, permissions, and compression settings.

## Documentation

- [Architecture and execution lifecycle](docs/ARCHITECTURE.md)
- [Installation and configuration](docs/CONFIGURATION.md)
- [Scoring and identity model](docs/SCORING.md)
- [ChatGPT and GitHub publishing](docs/PUBLISHING.md)
- [Security policy](SECURITY.md)
- [Contributing](CONTRIBUTING.md)
- [Changelog](CHANGELOG.md)

## Important limitations

- A skill coordinates capabilities; it cannot create platform features that the host does not expose.
- The management agent remains responsible for final delivery. Worker self-reports are not acceptance evidence.
- The score ledger is local administrative metadata, not a security boundary, authorization system, tamper-evident log, or measure of consciousness.
- The default ChatGPT web declaration supports role simulation only and no persistent ledger.
- The repository does not include knowledge-base connectors, document parsers, spreadsheet engines, or image generators. It routes to those capabilities when they are separately available.
- Public GitHub availability and ChatGPT directory approval are separate. A GitHub release does not submit or approve a plugin in ChatGPT.

## License

No license has been selected yet. Until the publisher adds a license, copyright law reserves all rights. Choose and add an appropriate license before inviting third-party reuse or contributions.
