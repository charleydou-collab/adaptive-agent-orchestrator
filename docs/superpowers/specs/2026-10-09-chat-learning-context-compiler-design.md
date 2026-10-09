# Chat-Scoped Learning and Context Compiler Design

Date: 2026-10-09

Target release: v0.2.0

Status: Proposed for implementation planning after user review

## 1. Purpose

Adaptive Agent Orchestrator should improve within one conversation by learning from accepted user feedback while keeping the active model context bounded. The system must preserve relevant objectives, decisions, corrections, and preferences without repeatedly injecting the entire conversation into every management-agent and worker request.

This feature is memory-based adaptation, not model-weight training. Learning is isolated to one conversation. It must not transfer to another conversation, workspace, account, or user unless a future, separately approved design introduces an explicit export and import mechanism.

The design adds two related subsystems:

1. **Chat-scoped learning** converts meaningful feedback into validated, versioned lessons that can influence later relevant tasks in the same conversation.
2. **The context compiler** assembles a bounded prompt package from current state, relevant lessons, recent turns, and retrieved episodes instead of relying on an ever-growing history assembled by the orchestrator.

The platform host remains authoritative for its own native context handling. In particular, the ChatGPT web plugin cannot claim that it removes, truncates, or reduces native ChatGPT history unless the host exposes and verifies that control.

## 2. Goals

- Revise an affected deliverable before extracting a lesson from user feedback.
- Reuse accepted feedback on later relevant prompts in the same conversation.
- Persist learning across closing and reopening the same conversation when an adapter exposes a stable conversation identity and durable storage.
- Prevent chat learning from leaking into another conversation.
- Keep the orchestrator-added historical context within deterministic, configurable budgets.
- Give each worker only the chat rules, lessons, source material, and upstream results required for its task.
- Preserve traceability from summaries and lessons to opaque source-turn references.
- Keep chat learning independent from the operational performance ledger.
- Degrade honestly when a platform lacks conversation identity, persistence, transcript retrieval, token estimation, or message-list control.
- Produce separate Codex and ChatGPT web artifacts from one compatible portable core.
- Publish verified source, documentation, release notes, and v0.2.0 artifacts to the existing GitHub repository.
- Install the verified Codex distribution and update the existing ChatGPT web plugin without creating a duplicate entry.

## 3. Non-goals

- Training or fine-tuning model weights.
- Sharing lessons across chats by default.
- Converting performance scores into learned rules.
- Storing credentials, authentication material, complete prompts, private document bodies, or full deliverables in lesson records.
- Guaranteeing native-history token savings on ChatGPT web.
- Adding an external web storage service in v0.2.0.
- Replacing the host transcript, retention policy, billing model, or privacy controls.
- Using agent confidence or score as evidence that a proposed lesson is true.

## 4. Packaging architecture

The repository will retain one portable core and produce two independently versioned distribution artifacts.

### 4.1 Shared portable core

The shared core defines:

- conversation-scope semantics;
- chat-state capsule structure;
- learning-candidate and active-lesson contracts;
- episode-summary and source-reference contracts;
- retrieval-request and context-package contracts;
- feedback analysis and lesson activation policy;
- token-budget priorities;
- reset, deletion, conflict, and failure semantics;
- task-contract and completion-report integration;
- capability declarations required before an adapter may claim support.

The core remains provider- and model-neutral.

### 4.2 Codex distribution

The Codex artifact may include executable standard-library tooling for chat-state management, deterministic context compilation, storage inspection, compaction, reset, and cleanup. It may claim durable chat-scoped learning only when the runtime or caller supplies a stable opaque conversation identifier and a configured storage path.

The Codex adapter must not infer conversation identity from prompt content, user-visible titles, or a workspace-wide fallback. If a stable identifier is absent, the adapter operates without persistent chat learning and reports that limitation when it materially affects the request or when the user asks for an audit.

### 4.3 ChatGPT web distribution

The ChatGPT web artifact remains skills-only unless an officially supported runtime later exposes executable storage and message controls. It may define an in-chat capsule, feedback-learning workflow, retrieval instructions, controls, and capability declarations. It must not claim:

- durable private storage;
- native transcript pruning;
- deterministic token reduction;
- per-worker model selection;
- native worker independence; or
- cross-session learning beyond behavior verified on the active surface.

Its state is temporary or host-managed. It should tell the user to select the plugin explicitly when reliable activation matters.

### 4.4 Compatibility

Each artifact declares its distribution version and compatible shared-core version. The release process builds and tests both artifacts independently. The proposed public version is v0.2.0 because the change adds public schemas, controls, storage semantics, and distribution boundaries.

## 5. Components

### 5.1 Conversation Scope Resolver

The resolver validates a nonempty opaque conversation identifier supplied by the adapter. It returns one of three states:

- `durable`: stable identity and durable authorized storage are available;
- `session`: identity is stable only for the active session; or
- `none`: safe isolation cannot be established.

`none` disables persistent reads and writes. It never falls back to workspace-wide or global learning.

### 5.2 Chat State Capsule

The capsule is a revisioned compact representation of the current conversation state. It contains only concise entries for:

- objectives;
- confirmed requirements;
- user preferences;
- decisions;
- constraints;
- open tasks;
- unresolved questions; and
- important corrections.

Every entry carries one or more opaque source references. The capsule has an estimated-token count, a configured budget, a revision number, and update time. It must not contain credentials or complete source documents.

### 5.3 Episode Index

Completed or superseded conversational work becomes an episode summary. An episode records its task category, role relevance, topics, named entities when safe, outcome, decision references, applicable lesson identifiers, and opaque references to original turns or artifacts.

The core does not duplicate the full transcript by default. Original messages remain in the authorized host or adapter source. An adapter may retrieve them when exact wording or evidence is required. Any optional transcript duplication requires separate explicit authorization and is outside v0.2.0.

### 5.4 Lesson Store

An active or proposed lesson records:

- lesson identifier;
- conversation identifier or an irreversible scoped identity derived from it;
- reusable rule;
- category;
- applicable task categories;
- applicable agent roles;
- applicability conditions and exceptions;
- opaque source references;
- confidence classification;
- activation status;
- version;
- superseded lesson identifier when applicable;
- optional expiration condition; and
- timestamps.

Supported statuses are `proposed`, `active`, `disputed`, `superseded`, `expired`, and `forgotten`. Only `active` lessons are eligible for prompt inclusion.

### 5.5 Feedback Analyzer

The analyzer runs only for a meaningful learning event: explicit correction, lasting preference, verified management rejection, accepted revision, repeated problem, or explicit `[learn]` control. It compares:

1. the original request;
2. the original result;
3. user feedback;
4. the revised result; and
5. verification evidence.

The affected result is revised and verified before lesson extraction. The analyzer emits zero or more learning candidates; it never activates them.

### 5.6 Lesson Gatekeeper

The management agent owns activation. Workers may propose candidates but cannot write active lessons.

Activation rules are:

- an explicit low-risk user instruction activates automatically;
- a factual correction activates only after verification against authorized evidence;
- a repeated preference activates after consistent evidence from more than one event;
- a one-off inferred preference remains proposed until confirmed;
- permissions, external actions, premium cost, disclosure, deletion, security, and source-authority changes always require explicit confirmation.

Current explicit instructions outrank older lessons. A conflicting lesson becomes `disputed` or `superseded`; it is not silently overwritten.

### 5.7 Context Compiler

The compiler accepts a current request, platform capabilities, conversation scope, capsule revision, candidate lesson set, episode index, recent-turn references, required source inputs, and a token budget. It returns a deterministic context package containing:

- core policy references;
- the bounded capsule;
- selected lesson identifiers and concise rules;
- selected episode references and summaries;
- selected recent turns or references;
- required source inputs;
- omissions with reasons;
- estimated token use; and
- budget status.

The compiler records selection metadata, not hidden system content or sensitive prompt bodies.

### 5.8 Worker Context Packager

The management agent derives a smaller context package for each task contract. A worker normally receives its contract, applicable chat rules, no more than three relevant lessons, necessary source inputs, and required upstream results. It does not receive unrelated conversational history or the complete management capsule.

The verification role receives the result, KPIs, evidence, and applicable constraints. It does not need unrelated drafting history.

## 6. Data contracts

The portable core will add closed JSON Schemas for:

| Schema | Purpose |
| --- | --- |
| `conversation-scope.schema.json` | Opaque chat identity, persistence class, and adapter binding |
| `chat-state-capsule.schema.json` | Revisioned bounded current state with source references |
| `learning-candidate.schema.json` | Worker- or manager-proposed reusable lesson and evidence |
| `chat-lesson.schema.json` | Versioned lesson with activation, applicability, conflict, and expiration state |
| `episode-summary.schema.json` | Searchable summary with opaque original-turn references |
| `retrieval-request.schema.json` | Task, role, topics, entities, required evidence, and retrieval limits |
| `context-package.schema.json` | Selected material, omissions, estimates, and budget result |
| `context-audit.schema.json` | Non-sensitive explanation of context selection |
| `learning-reset-request.schema.json` | Confirmed conversation-scoped reset or deletion operation |

The task contract gains optional references to a compiled worker-context package and applicable lesson identifiers. The completion report gains an optional array of learning candidates. These fields are versioned so v0.1.3 contracts remain readable through an explicit compatibility path.

No scoring schema imports chat-learning content. Lesson text, user feedback, and context packages must never be copied into the performance ledger.

## 7. Processing lifecycles

### 7.1 Request lifecycle

1. Resolve and validate conversation scope.
2. Interpret the current request without allowing past lessons to override it.
3. Classify task category, roles, required evidence, and context needs.
4. Load the current capsule and eligible active lessons for that conversation.
5. Retrieve relevant episodes and original turns only when needed.
6. Compile the management-agent context within budget.
7. Decompose the task and produce role-specific worker contexts.
8. Execute, clarify, report, verify, repair, and integrate using the existing orchestration lifecycle.
9. Update task and capsule state if the result changes the conversation state.
10. Run feedback learning only when a qualifying event occurs.

### 7.2 Feedback lifecycle

1. Receive user feedback about a completed or partial result.
2. Correlate it to the affected request, result, task, and agents.
3. Revise the result against the original request and feedback.
4. Verify the revision against applicable KPIs and evidence.
5. Compare the original and accepted revision.
6. Produce concise learning candidates.
7. Apply the activation rules or ask through the existing clarification relay.
8. Add, supersede, dispute, expire, or reject lessons.
9. Update the capsule and episode index.
10. Record performance attribution separately when justified; do not place learning content in the score ledger.

## 8. Token budgets and selection policy

The default management-agent historical-context budget is:

| Component | Normal budget | Maximum |
| --- | ---: | ---: |
| Core orchestration policy | 600 | 1,000 |
| Chat-state capsule | 500 | 800 |
| Active lessons | 300 | 600 |
| Retrieved episodes and evidence | 800 | 1,500 |
| Recent turns | 1,200 | 2,000 |

The normal total is approximately 3,400 tokens and the default ceiling is approximately 5,900 tokens, excluding the current request and required task source documents. Adapters may use model-specific token estimators when available; otherwise they must label estimates as approximate and use a deterministic conservative estimator.

Large source documents use a separate task-specific budget. They must not crowd out mandatory user constraints, permissions, or active task requirements.

Selection priority is:

1. current explicit user instructions;
2. safety, permissions, and source boundaries;
3. active task requirements;
4. confirmed chat-wide decisions;
5. verified factual corrections;
6. relevant active lessons;
7. unfinished work and dependencies;
8. recent conversational context; and
9. older episodes.

Under budget pressure the compiler removes low-priority conversational detail, redundant lessons, and unrelated episodes before mandatory content. If mandatory content still cannot fit, it returns a capacity blocker instead of silently omitting a constraint.

## 9. Compaction, retrieval, and rehydration

Compaction occurs when recent-turn context exceeds its budget, a task completes and is verified, accepted feedback changes state, a decision supersedes earlier discussion, or the user requests `compact chat context`. It does not run after acknowledgements, minor questions, or incomplete tasks solely to create activity.

Retrieval ranks exact scope and active-task matches ahead of semantic or topical similarity. Lessons are filtered by status, role, task category, applicability conditions, and conversation scope before ranking. The default worker limit is three lessons; the management limit is five unless mandatory requirements justify more within budget.

The compiler must rehydrate original authorized turns when exact wording, evidence, permissions, conflicting decisions, or the user's references to an earlier version materially affect correctness. Summaries are navigation aids, not authoritative substitutes for exact evidence.

## 10. User controls

The portable controls are:

| Control | Effect |
| --- | --- |
| `[no-learn]` | Execute and verify without proposing or activating lessons |
| `[learn]` | Analyze qualifying feedback for reusable lessons |
| `show chat learning` | Display active lessons and a safe capsule summary |
| `show proposed lessons` | Display candidates awaiting confirmation |
| `forget lesson <id>` | Deactivate one lesson within the current conversation |
| `reset chat learning` | Remove current-conversation lessons and capsule after explicit confirmation |
| `compact chat context` | Regenerate the capsule and archive completed episodes |
| `[full-context]` | Request broader authorized retrieval for the current task |
| `[context-audit]` | Show budgets, selected IDs, omissions, estimates, and capability fallbacks |

Reset and deletion never affect another conversation or the performance ledger. A reset retains only the minimum administrative tombstone needed to prevent stale concurrent writes when the adapter requires it; it contains no lesson text or user content.

## 11. Persistence, privacy, and deletion

Conversation state survives closing and reopening the same chat only when a stable adapter-provided conversation identity and durable authorized storage are available. Storage is scoped by an irreversible derived key or a safe opaque identifier. Paths and logs must not expose user prompt text or chat titles.

The Codex local implementation uses closed-schema validation, restricted file permissions, private same-directory temporary files, flush and `fsync`, atomic replacement, serialized writes, and revision checks. Atomic replacement prevents partial files but is not a multi-writer transaction lock.

If the platform exposes a verified chat-deletion event, the adapter deletes associated state. If it does not, the adapter documents retention and provides explicit reset and cleanup operations. The ChatGPT web artifact must state that retention and deletion remain controlled by the host when it has no independent storage.

Learning records reject credentials, authentication data, complete prompts, full outputs, and private source bodies at known structural fields. Semantic review remains required because a closed schema cannot reliably detect secrets embedded in short prose.

## 12. Failure handling

- **Missing conversation identity:** disable persistent learning; never use global fallback.
- **Unavailable persistence:** use session or in-chat state and label the scope accurately.
- **Corrupt state:** preserve the corrupt record for recovery, stop writes, and continue the task without claiming learning.
- **Stale revision:** reject the write, reload current state, and recompute the update.
- **Retrieval failure:** use the capsule and recent context; disclose degradation when it materially affects quality.
- **Budget overflow:** reduce optional context by priority and return a blocker if mandatory content cannot fit.
- **Conflicting feedback:** dispute the affected lesson and ask through the clarification relay.
- **Bad summary:** retrieve original authorized turns, repair the capsule, and increment its revision.
- **Unsupported web behavior:** degrade to declared skills-only behavior and do not claim native context reduction or persistence.

Ordinary task execution may continue without learning when safe. Memory writes, cross-chat access, deletion, permissions, and persistence claims fail closed.

## 13. Capability declarations

The platform-capabilities schema will add declarations for:

- stable conversation identity;
- conversation-bound persistence;
- host transcript retrieval;
- native message-list control;
- token estimation;
- context compilation;
- original-turn rehydration;
- deletion-event support; and
- chat-learning scope.

An adapter may claim a feature only when the runtime evidence supports it. ChatGPT web defaults remain conservative. A model, plugin display name, or Custom Instructions text is not evidence of storage or context control.

## 14. Backward compatibility and migration

- Existing orchestration works with chat learning disabled.
- Existing v0.1.3 task contracts and completion reports remain readable through explicit version handling.
- Existing score ledgers are not migrated or rewritten.
- No score event becomes a lesson.
- Existing plugin activation and premium-model approval rules remain in force.
- Installation and upgrade must not change the primary model or global reasoning-effort setting.
- Existing Codex configuration is backed up before adapter installation changes.
- The web package remains free of local-only scripts and runtime state.

## 15. Verification and tests

The implementation must add tests for:

- strict conversation isolation;
- persistence after reopening the same conversation;
- session and no-persistence fallbacks;
- reset, deletion, and cleanup behavior;
- explicit, verified, repeated, inferred, conflicting, and high-impact lessons;
- lesson supersession, dispute, expiration, and forgetting;
- sensitive-field rejection and semantic-review boundaries;
- capsule and context token limits;
- deterministic context assembly;
- retrieval ranking and lesson limits;
- mandatory-content preservation under budget pressure;
- original-turn rehydration;
- management and worker context isolation;
- corrupt-state preservation and recovery;
- concurrent revision rejection;
- separation from scoring and clarification content;
- honest ChatGPT web capability declarations;
- deterministic builds for both distribution artifacts;
- upgrade compatibility from v0.1.3; and
- regression coverage for orchestration, routing, premium approval, clarification, verification, and scoring.

Verification should use behavioral fixtures with two or more conversation identities, conflicting feedback, long histories, oversized optional context, missing capabilities, and sensitive-looking content. The tests must prove absence of cross-chat retrieval rather than relying only on positive single-chat examples.

## 16. Acceptance criteria

The release is acceptable when:

1. One conversation can learn without changing retrieval or behavior in another conversation.
2. Accepted feedback influences a later relevant task in the same conversation.
3. Irrelevant lessons are excluded from management and worker contexts.
4. Active orchestrator-added historical context remains within the configured budget.
5. Mandatory instructions and permissions are never silently removed.
6. Users can inspect, suppress, confirm, forget, compact, and reset learning.
7. Codex state survives reopening the same conversation when a stable identity and durable storage are available.
8. Missing identity or storage disables persistence without using a broader fallback.
9. ChatGPT web does not claim native history pruning, private durable storage, or per-worker controls it cannot verify.
10. Both distribution artifacts pass their capability, privacy, compatibility, and deterministic-build tests.
11. Existing orchestration, routing, clarification, verification, and scoring behavior remains green.
12. Documentation clearly distinguishes stored chat knowledge, compiled prompt context, host-native history, and performance scoring.
13. The verified implementation, documentation, changelog, release notes, and both distribution artifacts are published to the existing GitHub repository.
14. The Codex distribution is installed only after backing up affected configuration, preserving the primary model and global reasoning-effort setting, and passing post-install verification.
15. The existing ChatGPT web plugin is updated in place to v0.2.0 when the workspace surface permits it; the deployment must not create a second plugin with the same display name.
16. Web installation and activation are reported as complete only after the installed manifest version and visible plugin identity are verified. Any required manual Custom Instructions or workspace-owner action is disclosed precisely.

## 17. Publication and installation

Publication and installation occur only after the source implementation and both artifacts pass the required tests.

### 17.1 GitHub publication

The release workflow must:

1. update the public architecture, configuration, installation, security, and scoring documentation;
2. update the changelog and repository front page for v0.2.0;
3. build deterministic Codex and ChatGPT web artifacts from explicit inventories;
4. verify that artifacts exclude runtime state, chat learning data, local paths, credentials, caches, and development-only records;
5. commit the verified implementation and push it to the existing repository;
6. confirm the repository CI result for the published commit; and
7. create or update the v0.2.0 GitHub release with checksums and platform-specific installation notes.

GitHub issues associated with the feature remain open until their acceptance criteria are verified. Resolved issues should link to the implementing commit, tests, and release rather than being closed solely because code was written.

### 17.2 Codex installation

The Codex installer must use guarded additive changes, preserve the configured primary model and global reasoning effort, back up affected configuration before editing, and refuse ambiguous merges. Installation verification must confirm:

- the expected core and Codex distribution versions;
- role and skill discovery;
- declared conversation-scope capability;
- safe behavior when no stable conversation identifier is available;
- chat-state storage permissions and isolation when persistence is enabled;
- context-compiler and learning-management command behavior; and
- continued operation of existing clarification, routing, verification, and scoring features.

The installer must not copy test fixtures, repository state, example chat data, or a development ledger into the live installation.

### 17.3 ChatGPT web installation

The web deployment should update the known existing plugin identity in place. Before upload, the package manifest, version, deterministic archive, inventory, and absence of local-only files must be verified. After upload, verification must confirm the visible plugin name, version, description, and supported controls.

If the workspace interface cannot update the existing identity, deployment stops before creating another plugin and asks for user direction. If browser or workspace permissions prevent installation or inspection, the release artifact and exact manual steps are provided, and the deployment is reported as pending rather than complete.

The Custom Instructions bootstrap may be updated to describe v0.2.0 behavior, but it cannot be presented as proof of always-on plugin activation, persistent storage, or native context pruning.

## 18. Implementation sequencing constraints

Implementation planning should keep the following dependency order:

1. Versioned schemas and capability declarations.
2. Deterministic chat-state storage primitives.
3. Lesson activation and conflict logic.
4. Episode retrieval and context compilation.
5. Task-contract and completion-report integration.
6. Codex packaging and adapter controls.
7. ChatGPT web fallback packaging and honest declarations.
8. Migration, documentation, end-to-end tests, and release artifacts.
9. GitHub publication and CI verification.
10. Guarded Codex installation and post-install verification.
11. In-place ChatGPT web plugin update and post-upload verification.

No implementation phase may claim token savings solely from shorter instructions. Measured context-package size is evidence for orchestrator-controlled context only; native host billing or context reduction requires separate host telemetry.
