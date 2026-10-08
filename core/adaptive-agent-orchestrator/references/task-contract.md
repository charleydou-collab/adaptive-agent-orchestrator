# Task and completion contracts

Use `../schemas/task-contract.schema.json` unchanged across adapters. Portable execution requirements specify capability tier, minimum context, modalities, required tools, and minimum reasoning class. Only an adapter writes transient resolved execution: provider, model identifier, effort, worker mode, adapter, and resolution timestamp.

KPIs must be observable. Examples include required-section coverage, source support for every material claim, numeric agreement, preservation of formulas and untouched cells, successful file reopening, exact required labels, and absence of unsupported content. Do not reward verbosity or unrelated additions.

Workers return `../schemas/completion-report.schema.json`: status, deliverable, KPI results, evidence, uncertainties, blockers, and escalation recommendation. Self-reported success is evidence to inspect, not acceptance.
