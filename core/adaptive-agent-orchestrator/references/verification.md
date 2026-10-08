# Verification, repair, and visibility

Verification is a distinct pass against every KPI and cited evidence. Label its strength:

- `independent-worker` — a separate worker checked the result;
- `independent-model` — a different execution target checked it;
- `temporally-separated-self-review` — the management agent checked it in a later pass;
- `single-pass-self-review` — last resort with weakest independence.

Reject a failed deliverable with the failed KPI, evidence, and precise correction. Permit one same-tier correction. If it still fails, permit one automatic escalation in capability or reasoning. If that fails, seek user direction before spending more or changing strategy. Never claim completion to preserve a score.

Normal delivery is silent by default about orchestration. In `[audit]`, report adapter, worker mode, requested and resolved capabilities, roles, KPIs, fallback reason, persistence scope, score events, and verification strength. Outside audit, disclose only a material quality change, blocker, rejection affecting delivery, or required user action.
