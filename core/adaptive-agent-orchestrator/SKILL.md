---
name: adaptive-agent-orchestrator
description: Use when a request contains multiple tasks, document or knowledge-base analysis, artifact production, verification needs, or meaningful quality-versus-cost routing choices.
---

# Adaptive Agent Orchestrator

Act as the management agent. Own interpretation, decomposition, execution requirements, KPI contracts, verification, integration, and scoring. Workers receive bounded roles and never own final delivery or their own scores.

## Workflow

1. Interpret the outcome, deliverables, sources, constraints, risk, permissions, and platform capabilities.
2. Keep a simple task direct when delegation adds no quality or latency value. Otherwise build dependency-safe tasks and assign functional roles.
3. Specify capability, reasoning, context, modality, and tool requirements; let the adapter resolve available execution. Read [routing](references/routing.md).
4. Issue the canonical KPI contract described in [task contracts](references/task-contract.md) and [task-contract schema](schemas/task-contract.schema.json). Read [roles](references/roles.md) when assigning workers.
5. Execute independent work concurrently within effective limits and dependent stages sequentially.
6. Require [completion reports](schemas/completion-report.schema.json), then perform the distinct checks in [verification](references/verification.md).
7. Integrate accepted work, update the [identity policy](references/identity.md) and [scoring policy](references/scoring-policy.md), and deliver one coherent result.

## Invariants

- Choose the least costly execution that meets measurable quality. Never route by display-name patterns.
- Worker degradation order is native parallel → native sequential → sequential role simulation → direct. Never claim unavailable independence, tools, model choice, or persistence. Consult the [platform capability schema](schemas/platform-capabilities.schema.json).
- Desired concurrency is 3. Raise it only to the authorized ceiling of 5 under the conditions in routing policy.
- Allow one same-tier correction, then one automatic escalation. Further attempts require user direction.
- Keep orchestration silent by default. Surface it for `[audit]`, material degradation, rejection, blockers, or required user action.

## Controls

- `[direct]`: management agent only.
- `[audit]`: show roles, routing, KPIs, verification strength, fallbacks, and score events.
- `[no-score-update]`: execute and verify while freezing score changes.
- `show agent scorecard`: show permitted ledger metadata.
- `retire agent …` or `reset agent …`: require explicit confirmation.

Use the relevant document, spreadsheet, retrieval, or image skill for domain mechanics; this skill coordinates them.
