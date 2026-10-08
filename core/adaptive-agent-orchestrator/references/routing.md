# Capability routing

## Requirements before names

Classify each task by capability tier (`economy`, `balanced`, `advanced`, or `specialist`), abstract reasoning (`minimal`, `standard`, or `deep`), minimum context, required modalities, and required tools. Ask the adapter to select the lowest-cost available target satisfying every mandatory requirement. Model display-name matching is not capability evidence.

Use `specialist` for a required domain executor or modality such as image generation. Express image work as `required_modality: image_generation` plus `quality_class: draft` or `production`; do not treat a visual generator as a general reasoning tier.

If a preferred target is renamed or unavailable, refresh the adapter registry, require declared capability equivalence, and choose the least costly qualifying target. If none qualifies, report the missing capability instead of fabricating support. Fixed-effort platforms may declare one actual effort string and map all supported abstract classes to it; null means no compatible mapping, not a selectable effort.

## Premium approval boundary

Low- or medium-cost targets are the default. A target is premium when its registry entry has `cost_class: high` or `approval_policy: explicit-user-approval`; never infer this from a display name. High-cost registry entries must use the explicit approval policy.

First select among compatible non-premium targets. A standing preference, prior approval, high score, retry, or escalation must not displace a compatible lower-cost default. If only premium targets satisfy the mandatory requirements, stop before dispatch and ask for explicit user approval for the exact model. Explain its cost class, the requested effort, why the task needs it, and which capability, context, modality, tool, or reasoning requirement the lower-cost choices cannot satisfy.

Approval is task- and model-specific. Record an opaque approval reference and the approved model identifier; do not transfer approval after a rename or substitution. If approval is declined or absent, offer a lower-cost strategy with its material quality limitation when one exists, or report the blocker. Never silently downgrade a mandatory requirement or silently escalate to premium.

Adapters with executable registries should use `scripts/resolve_model.py`. `selected` permits dispatch, `approval_required` requires user interaction, and `no_compatible_model` requires a truthful blocker or revised task contract. The resolver output is a recommendation and dispatch input; actual runtime model telemetry remains platform-owned.

## Worker mode and concurrency

Resolve modes in this order: native parallel, native sequential, sequential role simulation, direct. Role simulation uses temporally separated passes and must not be described as independent workers.

Desired concurrency is 3. The management agent may raise it to the authorized ceiling of 5 only when at least four tasks are genuinely independent, parallel work materially reduces latency, outputs cannot conflict, adapter and workspace limits permit it, and the expected benefit justifies token use. Effective concurrency is the minimum of desired concurrency, adapter limit, workspace limit, and dependency-safe task count.

The adapter, not the core, owns provider identifiers, effort mappings, tool bindings, activation behavior, and storage backends.
