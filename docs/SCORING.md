# Performance scoring and operational identity

## Purpose

The optional ledger records verified operational performance for reusable, narrowly scoped execution identities. It helps a future routing decision prefer a proven execution when the current task still matches its capabilities.

Scoring is not a measure of consciousness, personhood, intrinsic intelligence, employment status, or moral worth. Terms such as promotion, restriction, and retirement are administrative routing labels only.

## Identity scope

An identity key is a SHA-256 hash of:

- logical agent identity;
- adapter and platform;
- role and task category;
- capability tier;
- provider and model/version;
- tools and modalities;
- resolved effort and effort mapping;
- remaining execution-fingerprint fields.

Changing any scoped component creates a separate history. Model renames do not automatically inherit a score. A verified `equivalence_of` event can seed a new scope from a current source event, but future updates remain independent.

## Score bands

| Score | Administrative band | Routing meaning |
| ---: | --- | --- |
| 0 | Retired | Ineligible until a confirmed reset |
| 1–69 | Restricted | Avoid unless a deliberate exception is justified |
| 70–99 | Probation | Eligible with caution and stronger verification |
| 100–119 | Qualified | Normal starting and operating range |
| 120–149 | Senior | Repeated verified success in the same scope |
| 150–199 | Expert | Strong scoped history; capability checks still apply |
| 200 | Elite | Score cap; no additional authority |

New identities begin at `100`. Scores are clamped to `0–200`.

Typical reviewer guidelines are `+2` for verified first-pass KPI compliance, `+5` for an independently confirmed difficult outcome, `-5` for a recoverable verified miss, and `-20` for a material unsupported claim or attributable boundary violation. The reviewer selects the delta only after inspecting evidence and attribution.

External outages, ambiguous requirements, missing sources, and unavailable capabilities are not automatically worker failures. Use a zero delta when attribution is unresolved.

## Event contents

Each event must conform to `ledger-event.schema.json`. Store only compact metadata and opaque evidence references. Never store prompts, source documents, full outputs, credentials, secrets, or sensitive excerpts in the ledger.

`verified: true` means a verifier inspected the referenced evidence. It is an attestation, not a digital signature.

## Separation from chat learning

Performance scores and chat lessons are independent. Never place user feedback,
learning candidates, lesson text, capsule content, context packages, or
clarification answers in the ledger. A score cannot activate, confirm, transfer,
or suppress a lesson. A lesson cannot reward, deduct, promote, restrict, or retire
an identity. The same investigated outcome may justify separate events in both
systems only when each passes its own evidence and governance rules.

## Freeze, correction, equivalence, retirement, and reset

- `[no-score-update]` maps to `score_update_mode: freeze`. The proposed event remains auditable, but score and retirement status do not change.
- `correction_of` can restore at most half of the actual applied deduction, within the same scoped identity and reset generation.
- `equivalence_of` imports a one-time score snapshot into a new, verified-equivalent scope with a zero delta.
- A score reaching zero automatically retires the scope.
- Manual retirement requires `--confirm` and does not change the score.
- Reset requires the exact scoped identity key and `--confirm`; it restores that scope to active/100, increments its generation, and retains history.

## CLI

```bash
# Initialize
python3 core/adaptive-agent-orchestrator/scripts/manage_agent_ledger.py \
  init --ledger /path/to/ledger.json --scope workspace

# Validate and append an event
python3 core/adaptive-agent-orchestrator/scripts/manage_agent_ledger.py \
  record --ledger /path/to/ledger.json --event /path/to/event.json

# Inspect score metadata
python3 core/adaptive-agent-orchestrator/scripts/manage_agent_ledger.py \
  show --ledger /path/to/ledger.json

# Administrative actions
python3 core/adaptive-agent-orchestrator/scripts/manage_agent_ledger.py \
  retire --ledger /path/to/ledger.json --identity-key HASH --confirm
python3 core/adaptive-agent-orchestrator/scripts/manage_agent_ledger.py \
  reset --ledger /path/to/ledger.json --identity-key HASH --confirm
```

Commands emit JSON on standard output. Invalid input returns an error object and exit code `2`. The CLI intentionally avoids echoing input data in filesystem and type-error diagnostics.

## Storage guarantees and limitations

Writes use a private same-directory temporary file, flush and `fsync`, then atomic replacement. This protects the old ledger from a partially written replacement. It does not provide concurrent transaction isolation, cross-host synchronization, access control, encryption, signing, or tamper evidence.

Choose a trusted path, restrict filesystem permissions, serialize writers, back up according to the workspace's retention needs, and remove session-scoped ledgers when the session ends.

