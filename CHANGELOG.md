# Changelog

All notable changes are documented here. Versions follow Semantic Versioning.

## [0.2.0] - 2026-10-10

### Added

- Closed schemas for conversation scope, capsules, learning candidates, lessons,
  episodes, retrieval requests, compiled packages, audits, and reset requests.
- Conversation-isolated local state with derived filenames, private permissions,
  expected-revision checks, corrupt-state preservation, and atomic replacement.
- Governed feedback learning with evidence gates, confirmation boundaries,
  conflict supersession, expiration, forgetting, and management-only activation.
- Deterministic bounded context compilation with normal and maximum component
  budgets, role-specific lesson limits, rehydration references, and blockers when
  mandatory content cannot fit.
- Separate deterministic Codex and ChatGPT web plugin archives.
- Guarded Codex v0.1.3-to-v0.2.0 upgrade with non-overwriting backups and runtime-state preservation.

### Changed

- The shared core now compiles request-time context before decomposition and runs
  learning only after the affected result has been revised and verified.
- ChatGPT web uses an honest bounded in-chat fallback and does not claim durable
  private storage, native history pruning, or guaranteed token reduction.
- Performance scoring is explicitly isolated from lesson, feedback, capsule, and
  context-package content.

### Security

- Added defenses and guidance for cross-chat leakage, path traversal-looking
  identifiers, stale revisions, corrupt records, feedback prompt injection,
  secret capture, and unsupported capability claims.

## [0.1.3] - 2026-10-08

### Added

- Structured clarification request and response schemas with task correlation.
- A `needs-input` completion state for workers that encounter material ambiguity.
- Management-agent question consolidation with two to four choices, a recommended option, and a custom-response path.
- Branch-local pausing so independent work can continue while a dependent task waits for user input.

### Changed

- Codex, ChatGPT web, and generic adapters now route worker questions through the management agent and return answers to the same task.
- Clarification content is explicitly excluded from persistent scoring metadata.

## [0.1.2] - 2026-10-08

### Changed

- Classifies the current Astra model family as premium/high-cost in the Codex adapter.
- Requires refreshed capability and cost metadata when provider model names change instead of transferring an earlier approval.
- Aligns the active global bootstrap, registry example, configuration documentation, GitHub source, and release package version.

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
