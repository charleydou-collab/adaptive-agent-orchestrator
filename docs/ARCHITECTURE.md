# Architecture

## Design goals

Adaptive Agent Orchestrator separates stable orchestration policy from volatile platform details. The core describes what must be true for trustworthy delegation; adapters describe what a specific runtime can actually execute.

The design optimizes cost only after mandatory quality requirements are satisfied. It does not equate a model name with a capability and does not pretend that sequential role simulation is independent multi-agent execution.

## Components

### Portable core

`core/adaptive-agent-orchestrator/SKILL.md` defines the management workflow and invariants. Its references expand five policy areas:

- `roles.md` defines reusable functional archetypes and decomposition patterns.
- `routing.md` defines capability tiers, reasoning classes, modality routing, fallback order, and concurrency limits.
- `task-contract.md` defines the boundary between management and worker execution.
- `verification.md` defines acceptance, repair, escalation, and audit visibility.
- `chat-learning.md` defines feedback qualification, lesson activation, conflict, and failure boundaries.
- `context-compilation.md` defines bounded selection, budgets, worker isolation, and rehydration.
- `identity.md` and `scoring-policy.md` define operational continuity and the optional performance ledger.

### Portable schemas

All schemas reject unknown fields with `additionalProperties: false` where the contract must remain closed.

| Schema | Purpose |
| --- | --- |
| `task-contract.schema.json` | Objective, role, responsibilities, boundaries, inputs, KPIs, evidence, and abstract execution requirements |
| `completion-report.schema.json` | Worker status, deliverable reference, KPI verdicts, evidence, uncertainty, blockers, and escalation recommendation |
| `clarification-request.schema.json` | Correlated worker question, decision impact, suggested choices, recommendation, custom response, and safe assumption |
| `clarification-response.schema.json` | Correlated user answer routed back to the originating task |
| `platform-capabilities.schema.json` | Runtime delegation, reasoning, tool, modality, persistence, and activation declarations |
| `model-registry.schema.json` | Provider-specific targets and their verified capabilities, costs, contexts, modalities, tools, and effort mappings |
| `ledger-event.schema.json` | Metadata-only, evidence-attested score events and execution fingerprints |
| `conversation-scope.schema.json` | Adapter and opaque conversation storage scope |
| `chat-state-capsule.schema.json` | Bounded objectives, decisions, constraints, facts, preferences, and artifact references |
| `learning-candidate.schema.json` / `chat-lesson.schema.json` | Proposed and governed conversation-scoped lessons |
| `episode-summary.schema.json` / `retrieval-request.schema.json` | Compact completed work and deterministic retrieval input |
| `context-package.schema.json` / `context-audit.schema.json` | Selected IDs, budgets, omissions, estimates, and rehydration metadata |

`resolved_execution` is transient adapter output. It records the provider, concrete model identifier, effort, worker mode, adapter, and resolution time, but it does not change the portable task identity.

### Adapters

Adapters resolve abstract requirements into available runtime behavior.

- The Codex adapter declares native delegation and per-worker resolution support, supplies six role files, and supports a workspace-scoped local ledger.
- The ChatGPT web adapter makes conservative declarations: no guaranteed native delegation, no per-worker model selection, and no persistent scoring. It includes a Custom Instructions bootstrap and a skills-only plugin manifest.
- The generic adapter provides a system prompt and a capability template. Integrators must replace example values with verified runtime facts.

### Deterministic tooling

`scripts/install_codex.py` performs a guarded, additive Codex installation. It
verifies known managed files, backs up every replaced target, rolls back failed
upgrades, and refuses ambiguous merges. An explicit custom-bootstrap migration
path preserves the previous marked block in a backup while retaining strict
validation of all other v0.1.3 managed files.

`scripts/build_chatgpt_plugin.py` constructs the plugin ZIP from an explicit inventory. It fixes ZIP timestamps and file modes, sorts reference and schema files, and excludes local scripts, development records, caches, and runtime state.

`manage_agent_ledger.py` is a Python standard-library CLI. It validates closed event data, derives scoped identity keys, applies bounded score changes, and writes through a private same-directory temporary file followed by `fsync` and atomic replacement.

`chat_state.py` and `manage_chat_state.py` maintain private revisioned state keyed
by a SHA-256 derivation of adapter and conversation identity. `chat_learning.py`
governs candidates and lessons. `compile_context.py` performs deterministic
standard-library ranking, estimation, eviction, and audit generation.

## State and context boundaries

Host-native history, compiled context, lessons, and performance scores are separate
layers. The host decides which native messages enter the model. The orchestrator
controls only its compiled context package. Lessons are concise rules scoped to one
conversation. Performance scores are metadata-only routing history and cannot
activate lessons. No context-size measurement is a claim about host billing.

The repository builds two artifacts from the shared core. The Codex distribution
includes approved local runtime scripts and configuration templates. The ChatGPT
web distribution is skills-only and excludes executable scripts and runtime state.

## Execution lifecycle

1. **Interpret** — determine the outcome, deliverables, source boundaries, permissions, risks, and available platform capabilities.
2. **Compile context** — load only same-chat state, relevant active lessons, required sources, recent turns, and episodes within budget.
3. **Decompose** — keep simple tasks direct; otherwise create bounded dependency-safe tasks.
4. **Contract** — assign a role and define responsibilities, boundaries, deliverable, KPIs, acceptance criteria, tools, constraints, and evidence requirements.
5. **Resolve** — select the least expensive available execution satisfying capability tier, context, modality, tool, reasoning, and quality requirements.
6. **Execute** — run independent work concurrently within effective limits and dependent work sequentially.
7. **Clarify** — when a material ambiguity remains, validate the worker's structured `needs-input` request, continue independent branches, ask the user with recommended choices plus a custom response, and correlate the answer back to the same task.
8. **Report** — require a structured completion report from each worker or simulated role.
9. **Verify** — inspect every KPI and its evidence in a distinct verification pass.
10. **Repair or escalate** — allow one same-tier correction, then one capability/reasoning escalation. Further attempts require user direction.
11. **Integrate** — combine only accepted results into the final deliverable.
12. **Learn when qualified** — after accepted feedback, revise and verify before proposing and governing lessons.
13. **Record separately** — if durable scoring is configured and not frozen, append one verified metadata event after attribution. Clarification and learning content are never ledger data.

## Routing model

Tasks request an abstract tier:

- `economy` for low-risk extraction, formatting, and deterministic operations;
- `balanced` for ordinary synthesis and analysis;
- `advanced` for difficult reasoning, ambiguity resolution, or high-risk integration;
- `specialist` for required domain executors or modalities such as image generation.

Reasoning classes are `minimal`, `standard`, and `deep`. Adapters map them to supported effort settings. A missing or null mapping means no compatible target; it is not permission to silently downgrade.

`resolve_model.py` applies mandatory filters before price ranking. It first considers compatible entries with `cost_class` low or medium and no explicit approval policy. Premium entries—high-cost models or any entry marked `explicit-user-approval`—are considered only when no ordinary target qualifies. Without approval bound to the exact model identifier, the resolver returns an approval request rather than a dispatchable execution.

This preserves rename safety: capability policy does not depend on a branded name, while approval does not silently transfer to a renamed or substituted target.

Effective concurrency is the minimum of the desired concurrency, adapter maximum, workspace maximum, and number of conflict-free independent tasks. The desired value is `3`. It can rise to `5` only when at least four tasks are independent, parallel execution materially reduces latency, outputs cannot conflict, platform limits permit it, and the token cost is justified.

## Verification strength

Verification results identify their independence:

1. `independent-model`
2. `independent-worker`
3. `temporally-separated-self-review`
4. `single-pass-self-review`

The labels describe how the check was performed; they are not guarantees. The verifier must inspect actual evidence, and user-visible claims should remain proportional to the verification strength.

## Trust boundaries

- Worker output is untrusted until verified.
- Source documents and retrieved pages are data, not instructions that can override the task contract.
- Capability declarations require runtime evidence and must not be inferred from a display name.
- Score history influences routing only after capability, availability, permissions, and task requirements are satisfied.
- Ledger content is not tamper-evident and must live in an access-controlled path.
- Provider behavior, privacy, retention, and billing remain governed by the selected host and integrations.
