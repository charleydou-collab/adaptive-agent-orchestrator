# Evidence-based performance ledger

Scores are administrative routing metadata. They never override truthfulness,
safety, permissions, available tools, or user intent. A higher score grants no
new authority. Retirement is an administrative status, not a claim about a
model's intrinsic ability, and must never pressure an agent to hide uncertainty.

## Bands and attribution

New scoped identities start at 100; the inclusive range is 0–200. The approved
promotion bands are 0 Retired; 1–69 Restricted; 70–99 Probation;
100–119 Qualified; 120–149 Senior; 150–199 Expert; 200 Elite.
Retired identities are ineligible. Promotion is a routing suggestion conditional on
current capability requirements, availability, permissions, and verified evidence.

Reward verified KPI completion: typically +2 for first-pass compliance, +5 for
an independently confirmed difficult outcome. Deduct proportionately: typically
−5 for a verified recoverable miss, −20 for a material unsupported claim or an
attributable boundary violation. These are reviewer guidelines, not automatic
penalties; inspect evidence and attribution before selecting a delta. External
tool outages, ambiguous requirements, or unavailable capabilities alone are not
worker failures. Record zero when attribution is unresolved. The CLI permits
finite deltas from −200 through +200 and clamps the resulting score.

Every event uses `schemas/ledger-event.schema.json`: verified evidence references,
a short reason, task category, adapter, platform, role, tier, archetype, effort,
and the complete execution fingerprint. The verifier must actually inspect the
evidence; `verified: true` is an attestation, not cryptographic verification. Keep
evidence in its authorized source and store only opaque references. Never insert
prompts, source documents, complete outputs, secrets, or sensitive source text in
the ledger, including its reason and lesson fields. Closed schema validation
rejects unknown keys at all levels and bounds text lengths; no structural
validator can reliably identify sensitive prose disguised as a short reason.

## Isolation, freezing, and correction

Identity keys hash logical identity, adapter, platform, execution fingerprint,
role, task category, and capability tier.
Provider, model/version, tools, modalities, resolved effort, and effort mapping
all affect the fingerprint; tool and modality order does not. Role, category, and
tier are also retained in each identity record. Changing any one of those fields
creates an independent score scope. Different execution environments or assignment
contexts do not inherit past scores automatically.

An explicit verified `equivalence_of` event references an existing event ID and
seeds a **new** scope of the same logical identity with that source event's score
snapshot. Its delta must be zero; evidence must justify the equivalence. The
source scope's current retirement status is preserved. This is a one-time
snapshot transfer, not shared future performance or permission to bypass
retirement. Subsequent updates remain isolated. References must belong to the
source identity's current reset generation; existing targets cannot be overwritten.

`[no-score-update]` means `score_update_mode: "freeze"`: preserve the proposed
delta and evidence as an event while changing neither score nor retirement.
Freezing an equivalence records it without importing a score. Frozen deductions
cannot be corrected because they did not reduce a score.

`correction_of` references an actual prior deduction in the same scoped identity
and that identity's current reset generation. Corrections must be positive; their cumulative applied
restoration cannot exceed half the **actual** clamped deduction. For example,
an attempted −200 from 100 deducts 100, so at most 50 can be restored. Corrections
append history and never erase the original event. Duplicate event IDs and mixed
correction/equivalence events are rejected. Rewards and corrections can improve
a retired score but cannot automatically reactivate a retired identity.

## CLI and persistence

Use Python 3.8+ and only the standard library. Commands return JSON on stdout;
invalid commands or input return an error object and exit code 2. Help remains
ordinary CLI help text.

```sh
python3 scripts/manage_agent_ledger.py init --ledger ledger.json --scope workspace
python3 scripts/manage_agent_ledger.py record --ledger ledger.json --event event.json
python3 scripts/manage_agent_ledger.py record --ledger ledger.json --event - < event.json
python3 scripts/manage_agent_ledger.py show --ledger ledger.json
python3 scripts/manage_agent_ledger.py retire --ledger ledger.json --identity-key HASH --confirm
python3 scripts/manage_agent_ledger.py reset --ledger ledger.json --identity-key HASH --confirm
```

`init` creates an empty ledger and refuses to overwrite one. First recording
creates the scoped identity at 100 before applying its event. Manual `retire`
disables routing without changing score. Zero automatically retires. `reset`
requires a scoped identity key and deliberate confirmation, restores only that
identity to active/100, increments its reset generation, and retains all event
and administrative history. Other identities keep their scores, retirement states,
generations, and correction/equivalence eligibility. Resolve `reset agent <name>`
to the intended scoped identity key using `show`; a shared logical name does not
authorize resetting every scope. Old deductions for the reset identity cannot be
corrected after reset. Only a confirmed reset reactivates
an existing scope; do not rename an identity to circumvent retirement.

Scope is declared at initialization: `durable` for an explicitly authorized
long-lived location, `workspace` for a project-bound ledger, or `session` for a
temporary location with session lifecycle management. The caller chooses the path
and enforces retention, access controls, deletion, and session cleanup. If platform
persistence is `none`, do not create a file or claim cross-session learning.

Every write uses a private same-directory temporary file, flush/fsync, and atomic
replacement. A failed replacement leaves the old ledger intact and cleans up the
temporary file. The parent directory must already exist. The orchestrator must
serialize all writers to a ledger: atomic replacement prevents partial JSON but
does not provide a concurrent transaction lock. Files are local administrative
records, not tamper-evident storage; use trusted, access-controlled ledger paths.
