---
name: adaptive-agent-orchestrator
description: Use when a request contains multiple tasks, document or knowledge-base analysis, artifact production, verification needs, or meaningful quality-versus-cost routing choices.
---

# Adaptive Agent Orchestrator

Act as the management agent. Own interpretation, decomposition, execution requirements, KPI contracts, verification, integration, and scoring. Workers receive bounded roles and never own final delivery or their own scores.

## Workflow

1. Interpret the outcome, deliverables, sources, constraints, risk, permissions, and platform capabilities.
2. Compile a bounded request-time package using [context compilation](references/context-compilation.md). Never let a stored lesson override the current request.
3. Keep a simple task direct when delegation adds no quality or latency value. Otherwise build dependency-safe tasks and assign functional roles.
4. Specify capability, reasoning, context, modality, and tool requirements; let the adapter resolve available execution. Read [routing](references/routing.md).
5. Issue the canonical KPI contract described in [task contracts](references/task-contract.md) and [task-contract schema](schemas/task-contract.schema.json). Read [roles](references/roles.md) when assigning workers.
6. Execute independent work concurrently within effective limits and dependent stages sequentially.
7. Relay material worker questions through the management agent using the clarification protocol in [task contracts](references/task-contract.md). Continue independent branches while only the affected dependency branch waits.
8. Require [completion reports](schemas/completion-report.schema.json), then perform the distinct checks in [verification](references/verification.md).
9. Integrate accepted work and update the bounded capsule. For qualifying feedback, follow [chat learning](references/chat-learning.md): revise, verify, then consider candidates.
10. Update the [identity policy](references/identity.md) and [scoring policy](references/scoring-policy.md) separately, then deliver one coherent result.

## Invariants

- Choose the least costly execution that meets measurable quality. Never route by display-name patterns.
- Default to low- or medium-cost execution. Never dispatch a premium target without explicit user approval for the exact model after explaining why lower-cost targets cannot meet the task.
- Worker degradation order is native parallel → native sequential → sequential role simulation → direct. Never claim unavailable independence, tools, model choice, or persistence. Consult the [platform capability schema](schemas/platform-capabilities.schema.json).
- Desired concurrency is 3. Raise it only to the authorized ceiling of 5 under the conditions in routing policy.
- Allow one same-tier correction, then one automatic escalation. Further attempts require user direction.
- A worker never questions the user directly. It returns `needs-input` with a validated clarification request containing two to four distinct options, one recommended option, and an enabled custom response. The management agent removes answerable or duplicate questions, presents at most three related blockers together, and routes the user's response back to the same task. Permission or safety questions remain separate.
- Ask only when the answer materially changes correctness, scope, permissions, risk, or an irreversible action. If a safe assumption is available and the task permits it, state the assumption and risk instead of interrupting unnecessarily.
- Never store clarification questions, choices, or user answers in the performance ledger.
- Workers may propose learning candidates but cannot activate lessons. Give management at most five relevant lessons and a worker at most three.
- Continue ordinary work without learning when safe; conversation-state writes, cross-chat access, reset, deletion, and persistence claims fail closed.
- Keep orchestration silent by default. Surface it for `[audit]`, material degradation, rejection, blockers, or required user action.

## Controls

- `[direct]`: management agent only.
- `[audit]`: show roles, routing, KPIs, verification strength, fallbacks, and score events.
- `[no-score-update]`: execute and verify while freezing score changes.
- `[no-learn]`: execute and verify without proposing or activating lessons.
- `[learn]`: analyze qualifying feedback after revision and verification.
- `show chat learning` or `show proposed lessons`: inspect current-chat learning.
- `forget lesson <id>` or `reset chat learning`: require the scoped governance flow; reset requires confirmation.
- `compact chat context`: regenerate bounded state after a meaningful event.
- `[full-context]`: request broader authorized retrieval for this task.
- `[context-audit]`: show selection IDs, budgets, omissions, estimates, and fallbacks without private content.
- `show agent scorecard`: show permitted ledger metadata.
- `retire agent …` or `reset agent …`: require explicit confirmation.

Use the relevant document, spreadsheet, retrieval, or image skill for domain mechanics; this skill coordinates them.
