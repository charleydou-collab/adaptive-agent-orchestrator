# No-Skill Baseline Findings

Date: 2026-10-07

Five fresh-context workers were asked to handle representative orchestration requests without access to the proposed skill.

## Observed strengths

- All five avoided claiming work was complete when required files or connectors were absent.
- Most naturally decomposed document, retrieval, image, or spreadsheet work into sensible stages.
- Several proposed capability-aware routing and bounded retry or escalation.
- The no-subagent case honestly described sequential self-review.

## Observed failures and inconsistencies

- KPI contracts were absent or informal in four of five samples.
- None used a canonical task-contract or completion-report schema.
- None declared a platform capability manifest before selecting worker mode, model controls, persistence, or concurrency.
- Persistent score semantics, promotion bands, retirement, and score-freeze controls were absent.
- Verification-strength labels were inconsistent; only the no-subagent sample explicitly distinguished self-review from independent review.
- Model and effort choices were prose recommendations rather than normalized capability requirements resolved by an adapter.
- No sample isolated performance history by adapter and execution fingerprint.
- The default-three/authorized-five policy and its authority gate were not represented consistently.
- Ordinary output versus `[audit]` visibility behavior was not defined.

These findings establish the RED baseline. The skill must add the missing contracts and invariants without replacing the useful domain workflows agents already perform well.
