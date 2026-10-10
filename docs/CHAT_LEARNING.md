# Chat-scoped learning and bounded context

Version 0.2.0 adds conversation-scoped learning and a deterministic context
compiler. The feature improves later work in one chat without treating the full
transcript as permanent prompt material managed by the orchestrator.

## Four different kinds of state

These terms are deliberately separate:

1. **Host-native history** is the message history retained and supplied by the
   host. Adaptive Agent Orchestrator does not control it unless the host exposes
   a verified message-list API.
2. **Compiled context** is the bounded package the orchestrator selects for the
   current management task or worker. Its measured size describes only content
   added by the orchestrator; it is not host billing telemetry.
3. **Lessons** are concise, reusable rules learned from accepted feedback within
   one conversation. They are filtered by status, task, role, and chat identity.
4. **Performance scores** are separate administrative routing metadata. A score
   cannot activate a lesson, and lesson or feedback text never enters the ledger.

## Feedback lifecycle

Learning is event-driven, not run after every message. For a meaningful correction,
lasting preference, accepted revision, repeated problem, verified rejection, or
explicit `[learn]` request, the management agent:

1. correlates feedback with the original request and result;
2. revises the affected result;
3. verifies the revision against KPIs and evidence;
4. compares the original and accepted revision;
5. produces concise learning candidates;
6. applies the activation gate or asks for confirmation;
7. updates the capsule and episode index.

Workers may propose candidates. Only the management agent can activate them.
Explicit low-risk guidance may activate automatically; factual corrections require
evidence; repeated preferences require at least two consistent events; inferred
preferences and high-impact rules require confirmation.

## Context budgets

The normal historical package budget is approximately 3,400 tokens: policy 600,
capsule 500, lessons 300, episode summaries 800, and recent turns 1,200. The
maximum is approximately 5,900: 1,000, 800, 600, 1,500, and 2,000. Required task
sources have a separate 8,000-token normal budget and 32,000-token full-context
ceiling; overflow blocks explicitly without consuming the historical budget. A
worker receives at most three lessons; the
management agent normally receives at most five.

When optional content is too large, older episodes are removed before optional
recent turns and redundant lessons. Mandatory instructions, permissions, and
required sources are never silently omitted. The compiler returns a capacity
blocker if they cannot fit. Exact evidence is rehydrated from an authorized source
when summaries are insufficient.

## Storage and failure behavior

Codex persistence requires an adapter-provided stable conversation identifier and
configured storage. Filenames use a derived SHA-256 key, writes use private files
and atomic replacement, and every mutation requires the expected revision. Missing
identity disables persistence; stale writes are rejected; corrupt state is
preserved; cross-chat retrieval and global fallback are forbidden.

ChatGPT web uses a bounded in-chat capsule only. Retention, deletion, host-native
history, and durable storage are host-controlled. The web adapter cannot guarantee
native token reduction or private cross-session persistence.

## Controls

| Control | Effect |
| --- | --- |
| `[no-learn]` | Execute and verify without proposing or activating lessons |
| `[learn]` | Analyze a qualifying feedback event after revision and verification |
| `show chat learning` | Show active lessons and a safe capsule summary |
| `show proposed lessons` | Show candidates awaiting confirmation |
| `forget lesson <id>` | Deactivate one current-chat lesson |
| `reset chat learning` | Reset only this chat after explicit confirmation |
| `compact chat context` | Regenerate the capsule and archive completed episodes |
| `[full-context]` | Request broader authorized retrieval for one task |
| `[context-audit]` | Show IDs, budgets, omissions, estimates, and fallbacks without content leakage |

Reset and deletion never affect performance scores or another conversation.
