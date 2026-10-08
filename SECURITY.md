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

## Secret-handling rules

Never commit or package:

- API keys, access tokens, passwords, cookies, or reviewer credentials;
- private plugin, workspace, tenant, tunnel, or account identifiers;
- local ledgers, prompt histories, full model outputs, or source documents;
- machine-specific absolute paths or internal development reports;
- private support or policy drafts represented as published URLs.

The deterministic plugin builder uses an explicit allowlist and excludes scripts and local state. Always inspect the final ZIP independently before release.

