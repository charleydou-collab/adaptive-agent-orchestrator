# Bounded conversation context

Before decomposition, compile only the conversation material needed for the
current request. A package contains core policy references, the bounded capsule,
relevant active lessons, retrieved episode summaries, recent-turn references,
required source inputs, omission reasons, token estimates, and rehydration
references. It is not proof that the host removed native history or reduced billing.

The normal historical-context budget is approximately 3,400 tokens: policy 600,
capsule 500, lessons 300, episode summaries 800, and recent turns 1,200. The
maximum is approximately 5,900: 1,000, 800, 600, 1,500, and 2,000 respectively.
Required source inputs use a separate 8,000-token task budget, or a 32,000-token
maximum for a full-context request, and are never silently removed. A required
input that exceeds that separate ceiling produces a `required-input-overflow`
blocker rather than consuming or displacing historical context.
Without a provider tokenizer, use the deterministic conservative estimator and
label the estimate `approximate`.

Selection priority is current explicit instructions; safety, permissions, and
source boundaries; active task requirements; confirmed decisions; verified
factual corrections; relevant lessons; unfinished dependencies; recent context;
then older episodes. Remove irrelevant or old episodes before optional recent
turns and redundant lessons. If mandatory content still cannot fit, return a
capacity blocker instead of omitting a constraint.

The management package may include at most five relevant lessons. A worker gets
its task contract, applicable rules, required inputs and upstream results, and at
most three lessons; it never receives the full management capsule by default.
Filter by exact conversation, active status, role, task category, conditions, and
exceptions before ranking.

`[full-context]` requests broader authorized retrieval for one task but does not
bypass the maximum or source permissions. `[context-audit]` reports budgets,
selected identifiers, omissions, estimate quality, rehydration requests, and
capability fallbacks without exposing hidden instructions or private content.
Rehydrate authorized original turns when exact wording, evidence, permissions,
conflicting decisions, or comparison with an earlier version affects correctness.
