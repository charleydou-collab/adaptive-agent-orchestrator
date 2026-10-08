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
- `identity.md` and `scoring-policy.md` define operational continuity and the optional performance ledger.

### Portable schemas

All schemas reject unknown fields with `additionalProperties: false` where the contract must remain closed.

| Schema | Purpose |
| --- | --- |
| `task-contract.schema.json` | Objective, role, responsibilities, boundaries, inputs, KPIs, evidence, and abstract execution requirements |
| `completion-report.schema.json` | Worker status, deliverable reference, KPI verdicts, evidence, uncertainty, blockers, and escalation recommendation |
| `platform-capabilities.schema.json` | Runtime delegation, reasoning, tool, modality, persistence, and activation declarations |
| `model-registry.schema.json` | Provider-specific targets and their verified capabilities, costs, contexts, modalities, tools, and effort mappings |
| `ledger-event.schema.json` | Metadata-only, evidence-attested score events and execution fingerprints |

`resolved_execution` is transient adapter output. It records the provider, concrete model identifier, effort, worker mode, adapter, and resolution time, but it does not change the portable task identity.

### Adapters

Adapters resolve abstract requirements into available runtime behavior.

- The Codex adapter declares native delegation and per-worker resolution support, supplies six role files, and supports a workspace-scoped local ledger.
- The ChatGPT web adapter makes conservative declarations: no guaranteed native delegation, no per-worker model selection, and no persistent scoring. It includes a Custom Instructions bootstrap and a skills-only plugin manifest.
- The generic adapter provides a system prompt and a capability template. Integrators must replace example values with verified runtime facts.

### Deterministic tooling

`scripts/install_codex.py` performs a guarded, additive Codex installation. It backs up the configuration and refuses ambiguous merges.

`scripts/build_chatgpt_plugin.py` constructs the plugin ZIP from an explicit inventory. It fixes ZIP timestamps and file modes, sorts reference and schema files, and excludes local scripts, development records, caches, and runtime state.

`manage_agent_ledger.py` is a Python standard-library CLI. It validates closed event data, derives scoped identity keys, applies bounded score changes, and writes through a private same-directory temporary file followed by `fsync` and atomic replacement.

## Execution lifecycle

1. **Interpret** — determine the outcome, deliverables, source boundaries, permissions, risks, and available platform capabilities.
2. **Decompose** — keep simple tasks direct; otherwise create bounded dependency-safe tasks.
3. **Contract** — assign a role and define responsibilities, boundaries, deliverable, KPIs, acceptance criteria, tools, constraints, and evidence requirements.
4. **Resolve** — select the least expensive available execution satisfying capability tier, context, modality, tool, reasoning, and quality requirements.
5. **Execute** — run independent work concurrently within effective limits and dependent work sequentially.
6. **Report** — require a structured completion report from each worker or simulated role.
7. **Verify** — inspect every KPI and its evidence in a distinct verification pass.
8. **Repair or escalate** — allow one same-tier correction, then one capability/reasoning escalation. Further attempts require user direction.
9. **Integrate** — combine only accepted results into the final deliverable.
10. **Record** — if durable scoring is configured and not frozen, append one verified metadata event after attribution.

## Routing model

Tasks request an abstract tier:

- `economy` for low-risk extraction, formatting, and deterministic operations;
- `balanced` for ordinary synthesis and analysis;
- `advanced` for difficult reasoning, ambiguity resolution, or high-risk integration;
- `specialist` for required domain executors or modalities such as image generation.

Reasoning classes are `minimal`, `standard`, and `deep`. Adapters map them to supported effort settings. A missing or null mapping means no compatible target; it is not permission to silently downgrade.

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

