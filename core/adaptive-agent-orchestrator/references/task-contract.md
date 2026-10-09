# Task and completion contracts

Use `../schemas/task-contract.schema.json` unchanged across adapters. Portable execution requirements specify capability tier, minimum context, modalities, required tools, and minimum reasoning class. Only an adapter writes transient resolved execution: provider, model identifier, effort, worker mode, adapter, and resolution timestamp.

Premium approval is dispatch authorization, not a portable task requirement. Keep the approval reference beside resolver output and bind it to the exact proposed model. Do not place user text or sensitive approval content in the contract or ledger.

KPIs must be observable. Examples include required-section coverage, source support for every material claim, numeric agreement, preservation of formulas and untouched cells, successful file reopening, exact required labels, and absence of unsupported content. Do not reward verbosity or unrelated additions.

Workers return `../schemas/completion-report.schema.json`: status, deliverable, KPI results, evidence, uncertainties, blockers, and escalation recommendation. Self-reported success is evidence to inspect, not acceptance.

When bounded context is available, attach `context_package_ref` and only the
`applicable_lesson_ids` needed by that role. A worker completion report may carry
schema-valid `learning_candidates`; candidates are proposals and never imply
activation. Keep complete user feedback and document bodies in their authorized
sources rather than copying them into contracts.

## Clarification relay

Workers first inspect available evidence and distinguish a material ambiguity from a preference they can safely resolve. A question is material when the answer changes correctness, scope, permissions, risk, or an irreversible action. Workers do not communicate with the user directly.

When input is required, return `status: needs-input`, a null deliverable, and one `../schemas/clarification-request.schema.json`. The request carries a correlation ID, original task ID, concise question, reason, blocked scope, two to four plausible and mutually distinct options, one recommended option, an enabled custom-response path, and any safe provisional assumption with its risk.

The management agent validates the request, answers it from established context when possible, merges duplicates, and presents no more than three related blocking questions together. Each user-facing question leads with the recommended option and always leaves a custom response field. Safety, permission, premium-model approval, and irreversible-action questions are not bundled with ordinary clarifications.

Only the dependent branch waits. Independent tasks continue. Record the user's answer as `../schemas/clarification-response.schema.json`, validate that its request and task IDs match, and attach it to `clarification_responses` when resuming the same task. Prefer a follow-up to the existing worker; if the platform cannot preserve it, dispatch a replacement with the original contract, accepted work, and the response. Do not award or deduct score merely because clarification was requested, and never place question or answer content in the ledger.
