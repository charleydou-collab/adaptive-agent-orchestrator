# Chat-scoped feedback learning

Learning is limited to the current conversation identity. Never use a workspace,
account, user name, or global file as a fallback conversation identity. If a
stable identity or authorized storage is missing, ordinary execution continues
without learning and the limitation is reported only when material.

## Feedback lifecycle

Run learning only for an explicit correction, lasting preference, verified
management rejection, accepted revision, repeated problem, or `[learn]` request.
First correlate the feedback to the affected request and result. Then revise the
result, verify the revision against its KPIs and evidence, compare it with the
original, and only then emit concise learning candidates. `[no-learn]` suppresses
candidate creation and activation while leaving execution and verification intact.

Workers may propose candidates in completion reports, but the management agent
alone may activate, supersede, dispute, expire, forget, or reject a lesson. Worker
identity, model tier, and performance score are never evidence that a lesson is
true. The gatekeeper applies these rules:

- explicit low-risk user guidance may activate after the revised result passes;
- factual corrections require verification against authorized evidence;
- repeated preferences require consistent evidence from at least two events;
- one-off inferred preferences remain proposed until the user confirms them;
- permissions, external actions, premium cost, disclosure, deletion, security,
  and source-authority changes always require explicit confirmation.

Current explicit instructions outrank stored lessons. Conflicting active lessons
become disputed or superseded; no rule is silently overwritten. Only active,
unexpired, same-conversation lessons are eligible for retrieval.

## Controls and failure boundaries

- `[learn]` analyzes a qualifying event for reusable lessons.
- `[no-learn]` executes and verifies without learning.
- `show chat learning` displays active lessons and a safe capsule summary.
- `show proposed lessons` displays candidates awaiting confirmation.
- `forget lesson <id>` deactivates one current-chat lesson.
- `reset chat learning` requires explicit confirmation and affects only this chat.
- `compact chat context` regenerates the capsule and episode index.

Ordinary execution continues without learning when safe. Memory writes,
cross-chat access, reset, deletion, and persistence claims fail closed. Corrupt
state is preserved for recovery; stale revisions are reloaded and recomputed.
Lesson records contain concise rules and opaque evidence references, never complete
prompts, transcripts, private source bodies, complete outputs, or credentials.
