# Changelog

All notable changes are documented here. Versions follow Semantic Versioning.

## [0.1.1] - 2026-10-08

### Added

- Deterministic model resolver that filters availability, capability tier, context, modality, tools, and reasoning mappings before cost ranking.
- Explicit premium approval policy in the model registry schema.
- Machine-readable `selected`, `approval_required`, and `no_compatible_model` outcomes.
- Safe registry and execution-requirement examples for Codex adapters.

### Changed

- Low- and medium-cost models are now the mandatory default routing pool.
- Premium or high-cost models require a task-specific explanation and explicit approval for the exact model before dispatch.
- Retry, escalation, prior approval, urgency, and score history cannot bypass the premium gate.
- Approval does not transfer across model renames or substitutions.

## [0.1.0] - 2026-10-08

### Added

- Portable management-agent workflow for interpretation, decomposition, bounded role assignment, capability routing, verification, repair, escalation, and integration.
- Functional role archetypes for research, document analysis, structured-data analysis, synthesis, artifact production, and verification.
- Closed JSON Schemas for platform capabilities, model registries, task contracts, completion reports, and ledger events.
- Codex adapter with six model-neutral role definitions, bounded concurrency, global bootstrap, guarded installer, and workspace ledger configuration.
- Conservative ChatGPT web adapter with a skills-only plugin package and Custom Instructions bootstrap.
- Generic prompt adapter for runtimes without native worker or model controls.
- Deterministic plugin builder with fixed archive metadata and an explicit file inventory.
- Standard-library performance ledger with scoped identities, score bands, freeze events, corrections, equivalence transfers, retirement, reset generations, and atomic replacement.
- Test coverage for package reproducibility, schemas, adapters, installer safety, capability neutrality, and ledger invariants.
- GitHub-facing architecture, configuration, scoring, publishing, security, and contribution documentation.

### Security

- Excludes scripts, runtime state, development records, local paths, and ledger data from the skills-only plugin archive.
- Treats source documents and retrieved content as untrusted data rather than executable instructions.
- Prohibits sensitive content in ledger metadata and rejects unknown event fields.
