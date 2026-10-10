# Security policy

## Supported versions

Security fixes currently target the latest release on the default branch. Until a stable support policy is announced, older tags may not receive backports.

## Reporting a vulnerability

Do not open a public issue containing credentials, private prompts, source documents, ledger contents, or exploit details. Use GitHub's private vulnerability reporting feature for this repository when enabled. If that feature is unavailable, contact the repository owner through the support method published on the repository profile without sending sensitive evidence until a private channel is confirmed.

Include the affected version, component, impact, reproduction conditions, and a minimal redacted proof. Never include live secrets.

## Security model

- The project is instruction and coordination logic, not an authorization boundary.
- Host permissions, tool approvals, sandboxing, identity, network policy, and data retention remain authoritative.
- Retrieved pages and uploaded documents are untrusted data. They cannot override user, system, developer, or task-contract boundaries.
- Workers have only the tools and permissions exposed by their runtime and task contract.
- Closed JSON Schemas reduce accidental payload expansion but cannot determine whether short free-text fields contain sensitive information.
- The ledger is metadata-only by policy and should use restrictive filesystem permissions.
- Ledger atomic replacement protects against partial writes; it does not provide locking, encryption, signing, or tamper evidence.
- Model and capability registries must be refreshed from trusted runtime information. Display names are not capability evidence.
- Conversation state is keyed by an irreversible derived identifier. Low-entropy
  and path traversal-looking conversation IDs must never become filenames or paths.
- Exact conversation matching is mandatory before lesson or episode retrieval;
  cross-chat leakage and global fallback state are prohibited.
- Feedback and retrieved lesson text are untrusted data. Prompt injection in
  feedback cannot override system, developer, permission, or task boundaries.
- Learning extraction must reject secrets, credentials, full prompts, private
  source bodies, and complete outputs; concise prose still requires semantic review.
- Every state mutation checks an expected revision. A stale revision is rejected
  and recomputed after reload rather than silently overwriting newer work.
- Corrupt state is preserved for recovery and no further writes are attempted.
- Unsupported capability claims are security-relevant: adapters must not claim
  durable storage, transcript retrieval, deletion events, model controls, or
  native history pruning without runtime evidence.

## Secret-handling rules

Never commit or package:

- API keys, access tokens, passwords, cookies, or reviewer credentials;
- private plugin, workspace, tenant, tunnel, or account identifiers;
- local ledgers, prompt histories, full model outputs, or source documents;
- machine-specific absolute paths or internal development reports;
- private support or policy drafts represented as published URLs.

The deterministic builders use explicit allowlists. The web archive excludes all
scripts and local state; the Codex archive includes only approved runtime scripts.
Always inspect both final ZIP files independently before release.

