# Capability routing

## Requirements before names

Classify each task by capability tier (`economy`, `balanced`, `advanced`, or `specialist`), abstract reasoning (`minimal`, `standard`, or `deep`), minimum context, required modalities, and required tools. Ask the adapter to select the lowest-cost available target satisfying every mandatory requirement. Model display-name matching is not capability evidence.

Use `specialist` for a required domain executor or modality such as image generation. Express image work as `required_modality: image_generation` plus `quality_class: draft` or `production`; do not treat a visual generator as a general reasoning tier.

If a preferred target is renamed or unavailable, refresh the adapter registry, require declared capability equivalence, and choose the least costly qualifying target. If none qualifies, report the missing capability instead of fabricating support. Fixed-effort platforms may declare one actual effort string and map all supported abstract classes to it; null means no compatible mapping, not a selectable effort.

## Worker mode and concurrency

Resolve modes in this order: native parallel, native sequential, sequential role simulation, direct. Role simulation uses temporally separated passes and must not be described as independent workers.

Desired concurrency is 3. The management agent may raise it to the authorized ceiling of 5 only when at least four tasks are genuinely independent, parallel work materially reduces latency, outputs cannot conflict, adapter and workspace limits permit it, and the expected benefit justifies token use. Effective concurrency is the minimum of desired concurrency, adapter limit, workspace limit, and dependency-safe task count.

The adapter, not the core, owns provider identifiers, effort mappings, tool bindings, activation behavior, and storage backends.
