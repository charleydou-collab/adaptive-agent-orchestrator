# Chat-Scoped Learning and Context Compiler Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add conversation-isolated feedback learning and bounded context compilation, ship separate Codex and ChatGPT web distributions, publish v0.2.0, and install both verified distributions.

**Architecture:** One provider-neutral core defines closed contracts for conversation scope, capsules, lessons, episodes, retrieval, and compiled contexts. The Codex adapter adds a standard-library local state runtime and deterministic context compiler when stable conversation identity is available; the ChatGPT web adapter remains skills-only and declares host-controlled persistence and history behavior honestly. Learning, clarification, and performance scoring remain independent data paths.

**Tech Stack:** Python 3.8+ standard library, JSON Schema Draft 2020-12 documents, JSON-compatible YAML declarations, `unittest`, deterministic ZIP archives, Markdown, GitHub CLI, Codex installer, and the existing ChatGPT workspace plugin workflow.

**Spec:** `docs/superpowers/specs/2026-10-09-chat-learning-context-compiler-design.md`

## Global Constraints

- Target public version is `0.2.0`; existing v0.1.3 contracts remain readable through optional, version-compatible fields.
- Use only Python 3.8+ standard-library dependencies in repository tooling.
- Chat learning is isolated by a stable opaque conversation identity; absence of that identity disables persistent reads and writes.
- Never fall back from conversation scope to workspace-wide or global learning.
- Do not store credentials, authentication material, complete prompts, private document bodies, full deliverables, or learning content in the performance ledger.
- Revise and verify an affected deliverable before extracting lessons from feedback.
- Only the management agent activates lessons; workers may return candidates only.
- Explicit low-risk instructions may activate automatically; inferred and high-impact lessons follow the approved gatekeeping rules.
- Default management historical-context budget is 3,400 tokens with a 5,900-token ceiling, excluding the current request and required source documents.
- The default management lesson limit is five and the default worker lesson limit is three.
- Mandatory instructions, permissions, task requirements, and evidence constraints must never be silently omitted under budget pressure.
- ChatGPT web must not claim durable private storage, native transcript pruning, deterministic native token reduction, native worker independence, or per-worker model control without verified host support.
- Existing model selection, premium approval, concurrency, clarification, verification, and scoring invariants remain unchanged.
- Installation and upgrade must preserve the configured primary model and global `model_reasoning_effort`.
- Build artifacts must exclude runtime state, chat data, ledgers, local paths, credentials, caches, and development-only records.

## Review Focus

- A low-entropy or malicious conversation identifier must remain data, produce a fixed safe path key, and never escape the configured state root; Task 2 tests this.
- A required item larger than the remaining budget must return a capacity blocker rather than disappear or cause an unbounded package; Task 4 tests this.
- Concurrent writers using the same expected revision must allow exactly one update and reject the stale update without state loss; Task 2 tests this.
- Conflicting explicit feedback must dispute or supersede the old lesson deterministically and must not leave both rules active; Task 3 tests this.
- A v0.1.3 installation with existing ledger and chat-independent user configuration must upgrade without deletion, duplicate bootstrap blocks, model changes, or duplicate web plugin creation; Tasks 7 and 10 test this.

---

### Task 1: Portable Schemas and Capability Contracts

**Files:**
- Create: `core/adaptive-agent-orchestrator/schemas/conversation-scope.schema.json`
- Create: `core/adaptive-agent-orchestrator/schemas/chat-state-capsule.schema.json`
- Create: `core/adaptive-agent-orchestrator/schemas/learning-candidate.schema.json`
- Create: `core/adaptive-agent-orchestrator/schemas/chat-lesson.schema.json`
- Create: `core/adaptive-agent-orchestrator/schemas/episode-summary.schema.json`
- Create: `core/adaptive-agent-orchestrator/schemas/retrieval-request.schema.json`
- Create: `core/adaptive-agent-orchestrator/schemas/context-package.schema.json`
- Create: `core/adaptive-agent-orchestrator/schemas/context-audit.schema.json`
- Create: `core/adaptive-agent-orchestrator/schemas/learning-reset-request.schema.json`
- Modify: `core/adaptive-agent-orchestrator/schemas/platform-capabilities.schema.json`
- Modify: `core/adaptive-agent-orchestrator/schemas/task-contract.schema.json`
- Modify: `core/adaptive-agent-orchestrator/schemas/completion-report.schema.json`
- Modify: `tests/test_contracts.py`

**Interfaces:**
- Consumes: Existing closed-schema vocabulary and the v0.1.3 task/completion contracts.
- Produces: Nine closed schemas; optional `context_package_ref` and `applicable_lesson_ids` task fields; optional `learning_candidates` report field; platform `conversation_context` capability declaration.

- [ ] **Step 1: Extend schema fixtures and write failing contract tests**

Add fixtures for every new schema and tests named `test_chat_contracts_are_closed_and_provider_neutral`, `test_platform_context_capabilities_are_coherent`, `test_v013_contracts_remain_valid`, `test_task_accepts_compiled_context_references`, and `test_report_accepts_candidates_without_activating_them`. Assert unknown and sensitive structural fields are rejected.

- [ ] **Step 2: Run the contract tests and verify RED**

Run: `/usr/bin/python3 -B -m unittest tests.test_contracts -v`

Expected: FAIL because the nine schemas and new fields do not exist.

- [ ] **Step 3: Implement the nine schemas and optional integration fields**

Use Draft 2020-12, `additionalProperties: false`, bounded text fields, opaque reference arrays, explicit enums from the spec, and no provider or local-path names. Add `conversation_context` to platform capabilities with exact booleans for stable identity, conversation persistence, transcript retrieval, message-list control, token estimation, compilation, rehydration, deletion events, and an enum scope of `durable`, `session`, or `none`.

- [ ] **Step 4: Run contract and adapter-schema tests and verify GREEN**

Run: `/usr/bin/python3 -B -m unittest tests.test_contracts tests.test_adapters -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/adaptive-agent-orchestrator/schemas tests/test_contracts.py
git commit -m "Add chat learning and context schemas"
```

### Task 2: Conversation-Isolated State Store

**Files:**
- Create: `core/adaptive-agent-orchestrator/scripts/chat_state.py`
- Create: `core/adaptive-agent-orchestrator/scripts/manage_chat_state.py`
- Create: `tests/test_chat_state.py`

**Interfaces:**
- Consumes: Task 1 schemas and opaque adapter/conversation identifiers.
- Produces: `conversation_key(adapter: str, conversation_id: str) -> str`; `state_path(root: Path, key: str) -> Path`; `init_state(root: Path, scope: dict) -> dict`; `load_state(root: Path, adapter: str, conversation_id: str) -> dict`; `update_state(root: Path, adapter: str, conversation_id: str, expected_revision: int, operation: Callable[[dict], None]) -> dict`; and a JSON-output CLI.

- [ ] **Step 1: Write failing storage and CLI tests**

Cover deterministic SHA-256 scoped keys using `adapter + "\0" + conversation_id`, fixed 64-hex filenames, two-conversation isolation, low-entropy and path-traversal-looking IDs, mode `0600`, no overwrite on initialization, atomic replacement, corrupt-state preservation, and stale-revision rejection where the first writer succeeds and the second fails without mutation.

- [ ] **Step 2: Run the state tests and verify RED**

Run: `/usr/bin/python3 -B -m unittest tests.test_chat_state -v`

Expected: FAIL because the state module and CLI are absent.

- [ ] **Step 3: Implement state primitives**

The state document has `version: 1`, `scope`, `revision`, `capsule`, `lessons`, `episodes`, `administrative_events`, and timestamps. Use private same-directory temporary files, flush, `fsync`, atomic link for creation, atomic replacement for updates, and revision increment only after a valid mutation. Diagnostics must not echo conversation IDs or file contents.

- [ ] **Step 4: Implement management CLI operations**

Expose `init`, `show`, `apply-capsule`, `propose`, `activate`, `forget`, `compact`, `reset`, and `delete`. Require `--confirm` for reset and delete, and `--expected-revision` for every mutation. Accept structured payloads by file or stdin. Return JSON on stdout and a sanitized JSON error with exit code `2` on invalid input.

- [ ] **Step 5: Run state tests and verify GREEN**

Run: `/usr/bin/python3 -B -m unittest tests.test_chat_state -v`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add core/adaptive-agent-orchestrator/scripts/chat_state.py core/adaptive-agent-orchestrator/scripts/manage_chat_state.py tests/test_chat_state.py
git commit -m "Add isolated chat state storage"
```

### Task 3: Feedback Learning and Lesson Governance

**Files:**
- Create: `core/adaptive-agent-orchestrator/scripts/chat_learning.py`
- Create: `tests/test_chat_learning.py`
- Modify: `core/adaptive-agent-orchestrator/scripts/manage_chat_state.py`

**Interfaces:**
- Consumes: Task 1 candidate/lesson schemas and Task 2 revisioned state.
- Produces: `activation_decision(candidate: Dict[str, Any], existing_lessons: List[Dict[str, Any]], corroboration_count: int) -> Dict[str, Any]`; `apply_candidate(state: Dict[str, Any], candidate: Dict[str, Any], decision: Dict[str, Any]) -> str`; `forget_lesson(state: Dict[str, Any], lesson_id: str) -> None`; and `expire_lessons(state: Dict[str, Any], now: str) -> List[str]`, using Python 3.8-compatible `typing` imports.

- [ ] **Step 1: Write failing lesson-policy tests**

Test automatic activation for explicit low-risk instructions, evidence-required factual corrections, two-event repeated preferences, proposed status for one-off inference, confirmation-required status for high-impact categories, no activation by worker identity or score, exact conversation matching, expiration, forgetting, and deterministic conflict handling that leaves only the newest verified rule active.

- [ ] **Step 2: Run learning tests and verify RED**

Run: `/usr/bin/python3 -B -m unittest tests.test_chat_learning -v`

Expected: FAIL because lesson governance is absent.

- [ ] **Step 3: Implement activation and conflict logic**

Use the schema enums and priority order from the spec. The returned decision contains `action`, `status`, `reason_code`, `requires_confirmation`, and conflicting lesson IDs; it contains no full prompt or feedback text. `apply_candidate` validates the candidate, creates a versioned lesson, and marks prior conflicting lessons `disputed` or `superseded` in one state revision.

- [ ] **Step 4: Connect CLI lesson operations**

Make `propose`, `activate`, and `forget` call the governance functions. `activate` requires explicit confirmation when the decision says so. Clarification answers and lesson text remain absent from the score ledger.

- [ ] **Step 5: Run learning and state tests and verify GREEN**

Run: `/usr/bin/python3 -B -m unittest tests.test_chat_learning tests.test_chat_state -v`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add core/adaptive-agent-orchestrator/scripts/chat_learning.py core/adaptive-agent-orchestrator/scripts/manage_chat_state.py tests/test_chat_learning.py
git commit -m "Add feedback lesson governance"
```

### Task 4: Deterministic Context Compiler

**Files:**
- Create: `core/adaptive-agent-orchestrator/scripts/compile_context.py`
- Create: `tests/test_context_compiler.py`

**Interfaces:**
- Consumes: Task 1 retrieval/context schemas and Task 2 state documents.
- Produces: `estimate_tokens(value: str) -> int`; `rank_lessons(request: Dict[str, Any], lessons: List[Dict[str, Any]]) -> List[Dict[str, Any]]`; `rank_episodes(request: Dict[str, Any], episodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]`; `compile_context(request: Dict[str, Any], platform: Dict[str, Any], state: Dict[str, Any], recent_turns: List[Dict[str, Any]], required_inputs: List[Dict[str, Any]], limits: Optional[Dict[str, int]] = None) -> Dict[str, Any]`; and a JSON-input/output CLI, using Python 3.8-compatible `typing` imports.

- [ ] **Step 1: Write failing compiler tests**

Test deterministic ordering, only-active and same-conversation filtering, management maximum five, worker maximum three, role/task/topic relevance, default component budgets of 600/500/300/800/1,200 and maxima of 1,000/800/600/1,500/2,000, approximate-estimate labeling, required-input preservation, optional-content eviction order, original-turn rehydration request flags, and a capacity blocker when a mandatory item cannot fit.

- [ ] **Step 2: Run compiler tests and verify RED**

Run: `/usr/bin/python3 -B -m unittest tests.test_context_compiler -v`

Expected: FAIL because the compiler is absent.

- [ ] **Step 3: Implement deterministic estimation and ranking**

Use a conservative standard-library estimator based on UTF-8 byte length and label it `approximate`. Rank exact conversation, task category, role, topic, entity, active-state, and recency matches with stable identifier tie-breaking. Do not add embeddings or third-party dependencies in v0.2.0.

- [ ] **Step 4: Implement compilation and audit output**

Preserve the priority order from the spec. Emit selected IDs and concise content, omissions with reason codes, component estimates, total estimate, budget status, and required rehydration references. Never emit hidden system content in the audit object.

- [ ] **Step 5: Run compiler tests and verify GREEN**

Run: `/usr/bin/python3 -B -m unittest tests.test_context_compiler -v`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add core/adaptive-agent-orchestrator/scripts/compile_context.py tests/test_context_compiler.py
git commit -m "Add deterministic chat context compiler"
```

### Task 5: Orchestration Workflow Integration

**Files:**
- Create: `core/adaptive-agent-orchestrator/references/chat-learning.md`
- Create: `core/adaptive-agent-orchestrator/references/context-compilation.md`
- Modify: `core/adaptive-agent-orchestrator/SKILL.md`
- Modify: `core/adaptive-agent-orchestrator/references/task-contract.md`
- Modify: `core/adaptive-agent-orchestrator/references/roles.md`
- Modify: `core/adaptive-agent-orchestrator/references/verification.md`
- Modify: `core/adaptive-agent-orchestrator/references/scoring-policy.md`
- Modify: `adapters/codex/AGENTS.bootstrap.md`
- Modify: `adapters/chatgpt-web/custom-instructions-bootstrap.md`
- Modify: `adapters/generic-prompt/system-prompt.md`
- Modify: `tests/test_skill_package.py`
- Modify: `tests/test_adapters.py`

**Interfaces:**
- Consumes: Tasks 1-4 contracts and CLI behavior.
- Produces: Management workflow for request compilation, post-revision learning, worker candidate reporting, portable user controls, and capability-honest degradation.

- [ ] **Step 1: Write failing behavioral package tests**

Add assertions for `[no-learn]`, `[learn]`, `show chat learning`, `show proposed lessons`, `forget lesson`, `reset chat learning`, `compact chat context`, `[full-context]`, and `[context-audit]`; revision-before-learning; management-only activation; worker lesson limits; score separation; and web non-claims.

- [ ] **Step 2: Run skill and adapter tests and verify RED**

Run: `/usr/bin/python3 -B -m unittest tests.test_skill_package tests.test_adapters -v`

Expected: FAIL because the workflow and references are missing.

- [ ] **Step 3: Add portable policy references and update the core lifecycle**

Add request-time context compilation before decomposition and event-driven feedback learning after revision and verification. State that ordinary execution continues without learning when safe, while writes, cross-chat access, reset, deletion, and persistence claims fail closed.

- [ ] **Step 4: Update all adapter bootstraps**

Codex instructions call the local runtime only when stable conversation identity and configured storage exist. ChatGPT web uses a bounded in-chat capsule and explicitly labels native history and persistence as host-controlled. Generic instructions require capability declarations before making claims.

- [ ] **Step 5: Run behavioral tests and verify GREEN**

Run: `/usr/bin/python3 -B -m unittest tests.test_skill_package tests.test_adapters -v`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add core/adaptive-agent-orchestrator adapters tests/test_skill_package.py tests/test_adapters.py
git commit -m "Integrate chat learning into orchestration"
```

### Task 6: Separate Codex and ChatGPT Web Distribution Builds

**Files:**
- Create: `adapters/codex/plugin.json`
- Create: `scripts/build_codex_plugin.py`
- Create: `tests/test_codex_plugin_build.py`
- Modify: `adapters/chatgpt-web/plugin/plugin.json`
- Modify: `adapters/chatgpt-web/plugin/.codex-plugin/plugin.json`
- Modify: `scripts/build_chatgpt_plugin.py`
- Modify: `tests/test_plugin_build.py`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: Shared core, Codex adapter, web adapter, and v0.2.0 version.
- Produces: `dist/adaptive-agent-orchestrator-codex-0.2.0.zip` and `dist/adaptive-agent-orchestrator-chatgpt-web-0.2.0.zip`, each built from an explicit deterministic inventory.

- [ ] **Step 1: Write failing dual-build tests**

Assert both archives are byte-identical across repeated builds, have one expected root, declare version `0.2.0`, contain compatible core metadata, and exclude `.git`, caches, tests, design records, ledgers, chat state, absolute local paths, and unrelated adapter files. Assert the web archive excludes executable local scripts while the Codex archive includes only approved runtime scripts.

- [ ] **Step 2: Run build tests and verify RED**

Run: `/usr/bin/python3 -B -m unittest tests.test_plugin_build tests.test_codex_plugin_build -v`

Expected: FAIL because the Codex builder and v0.2.0 manifests are absent.

- [ ] **Step 3: Implement the Codex manifest and deterministic builder**

Use fixed ZIP timestamps, sorted explicit inventories, regular-file modes, one distribution root, and manifest/core compatibility checks. Include the skill, references, schemas, approved scripts, Codex roles, bootstrap, capability declaration, and configuration templates.

- [ ] **Step 4: Update the web builder and manifests**

Keep the existing web plugin identity for in-place update, change version and descriptions to `0.2.0`, include shared references and schemas, and continue excluding local scripts and runtime state.

- [ ] **Step 5: Run build tests and verify GREEN**

Run: `/usr/bin/python3 -B -m unittest tests.test_plugin_build tests.test_codex_plugin_build -v`

Expected: PASS with deterministic archives at temporary test paths.

- [ ] **Step 6: Commit**

```bash
git add adapters/codex/plugin.json adapters/chatgpt-web scripts/build_codex_plugin.py scripts/build_chatgpt_plugin.py tests/test_codex_plugin_build.py tests/test_plugin_build.py .gitignore
git commit -m "Build separate Codex and web plugins"
```

### Task 7: Safe Codex Upgrade and Chat-State Configuration

**Files:**
- Create: `adapters/codex/chat-state-config.example.yaml`
- Modify: `scripts/install_codex.py`
- Modify: `tests/test_codex_install.py`
- Modify: `adapters/codex/ledger-config.example.yaml`

**Interfaces:**
- Consumes: v0.2.0 Codex distribution and Task 2 state runtime.
- Produces: `install(codex_home: Path, agents_home: Path, upgrade: bool = False) -> dict` supporting guarded fresh install and exact existing-install upgrade while preserving unrelated configuration and runtime state.

- [ ] **Step 1: Write failing upgrade tests**

Add tests for upgrading a v0.1.3 skill and marked bootstrap, refusing ambiguous partial installs, preserving main model and reasoning effort byte-for-byte, retaining existing ledger and chat-state directories, producing a non-overwriting backup, avoiding duplicate `[agents]` and bootstrap blocks, and installing the v0.2.0 core and configuration template.

- [ ] **Step 2: Run installer tests and verify RED**

Run: `/usr/bin/python3 -B -m unittest tests.test_codex_install -v`

Expected: FAIL because upgrade mode and chat-state configuration are absent.

- [ ] **Step 3: Implement guarded upgrade behavior**

Add `--upgrade`. Require the complete known existing installation markers, stage replacement files in private temporary paths, back up every modified configuration file without overwriting prior backups, replace only managed blocks/files, and leave runtime data untouched. Fresh-install behavior remains collision-safe.

- [ ] **Step 4: Add portable state configuration**

Document `${WORKSPACE_ROOT}` and adapter-provided `${CONVERSATION_ID}` as conventions, not implicit shell expansion. The installed runtime must refuse persistence when no stable conversation identity is supplied.

- [ ] **Step 5: Run installer and state tests and verify GREEN**

Run: `/usr/bin/python3 -B -m unittest tests.test_codex_install tests.test_chat_state -v`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add adapters/codex/chat-state-config.example.yaml adapters/codex/ledger-config.example.yaml scripts/install_codex.py tests/test_codex_install.py
git commit -m "Add safe Codex v0.2 upgrade"
```

### Task 8: Public Documentation, Versioning, and Release Guidance

**Files:**
- Create: `docs/CHAT_LEARNING.md`
- Modify: `README.md`
- Modify: `CHANGELOG.md`
- Modify: `docs/ARCHITECTURE.md`
- Modify: `docs/CONFIGURATION.md`
- Modify: `docs/PUBLISHING.md`
- Modify: `docs/SCORING.md`
- Modify: `SECURITY.md`
- Modify: `CONTRIBUTING.md`
- Modify: `tests/test_adapters.py`
- Modify: `tests/test_plugin_build.py`

**Interfaces:**
- Consumes: Implemented behavior and artifact names from Tasks 1-7.
- Produces: Source-backed v0.2.0 public documentation and exact installation, upgrade, control, limitation, and release instructions.

- [ ] **Step 1: Write failing documentation assertions**

Test that the README links both artifacts and `docs/CHAT_LEARNING.md`; version references are `0.2.0`; documentation distinguishes host history, compiled context, lessons, and scores; web limitations are explicit; upgrade instructions preserve model settings; and every documented control exists in the core skill.

- [ ] **Step 2: Run documentation-facing tests and verify RED**

Run: `/usr/bin/python3 -B -m unittest tests.test_adapters tests.test_plugin_build tests.test_skill_package -v`

Expected: FAIL because v0.2.0 documentation is incomplete.

- [ ] **Step 3: Update front page and technical documentation**

Document the shared-core/two-plugin architecture, feedback lifecycle, token budgets, storage boundaries, controls, failure modes, upgrade path, artifact contents, GitHub release process, and exact distinction between orchestrator-controlled context size and host-native billing or context behavior.

- [ ] **Step 4: Update changelog and security guidance**

Add v0.2.0 entries for schemas, state runtime, learning gates, compiler, dual packaging, and safe upgrade. Add threat guidance for cross-chat leakage, path traversal, prompt injection in feedback, secret capture, stale writes, corrupt state, and unsupported capability claims.

- [ ] **Step 5: Run documentation tests and link checks and verify GREEN**

Run: `/usr/bin/python3 -B -m unittest tests.test_adapters tests.test_plugin_build tests.test_skill_package -v`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add README.md CHANGELOG.md CONTRIBUTING.md SECURITY.md docs tests/test_adapters.py tests/test_plugin_build.py
git commit -m "Document chat learning and dual plugins"
```

### Task 9: End-to-End Acceptance and Release Artifacts

**Files:**
- Create: `tests/test_chat_learning_e2e.py`
- Modify: `.github/workflows/ci.yml`
- Modify: `scripts/build_codex_plugin.py`
- Modify: `scripts/build_chatgpt_plugin.py`
- Build: `dist/adaptive-agent-orchestrator-codex-0.2.0.zip`
- Build: `dist/adaptive-agent-orchestrator-chatgpt-web-0.2.0.zip`

**Interfaces:**
- Consumes: All Tasks 1-8.
- Produces: End-to-end evidence, deterministic release artifacts, and CI coverage for both distributions.

- [ ] **Step 1: Write failing end-to-end scenarios**

Exercise two conversation IDs with conflicting preferences, accepted feedback affecting only the source conversation, worker-specific lesson filtering, long optional history under budget pressure, a mandatory oversized item producing a blocker, reset isolation, corrupt-state recovery, no score-ledger mutation, and web capability fallback.

- [ ] **Step 2: Run the end-to-end test and verify RED**

Run: `/usr/bin/python3 -B -m unittest tests.test_chat_learning_e2e -v`

Expected: FAIL until all integrated paths and fixtures are connected.

- [ ] **Step 3: Add only the integration wiring required by the scenarios**

Connect state, lesson, compiler, and adapter fixtures without adding a network service or third-party dependency. Update CI to run every `unittest` module and build both archives.

- [ ] **Step 4: Run the complete local suite**

Run: `/usr/bin/python3 -B -m unittest discover -s tests -v`

Expected: PASS with no skipped v0.2.0 acceptance tests.

- [ ] **Step 5: Build and compare release artifacts**

Run: `/usr/bin/python3 -B scripts/build_codex_plugin.py --output dist/adaptive-agent-orchestrator-codex-0.2.0.zip`

Run: `/usr/bin/python3 -B scripts/build_chatgpt_plugin.py --output dist/adaptive-agent-orchestrator-chatgpt-web-0.2.0.zip`

Run each build a second time to temporary paths and compare SHA-256 hashes byte-for-byte. Inspect archive inventories for excluded state and local paths.

Expected: both repeated builds match their corresponding release artifact and contain only approved files.

- [ ] **Step 6: Commit**

```bash
git add .github/workflows/ci.yml tests/test_chat_learning_e2e.py scripts/build_codex_plugin.py scripts/build_chatgpt_plugin.py dist/adaptive-agent-orchestrator-codex-0.2.0.zip dist/adaptive-agent-orchestrator-chatgpt-web-0.2.0.zip
git commit -m "Verify adaptive orchestrator v0.2.0"
```

### Task 10: GitHub Publication and Verified Installation

**Files:**
- No product-source files expected after Task 9; any source change restarts relevant verification.
- External targets: existing GitHub repository, local Codex installation, and existing ChatGPT workspace plugin identity.

**Interfaces:**
- Consumes: Clean verified v0.2.0 commit and both release artifacts.
- Produces: Pushed GitHub source, passing CI, v0.2.0 release, upgraded Codex installation, updated web plugin, and evidence-linked issue status.

- [ ] **Step 1: Perform the pre-publication audit**

Run the full suite again, verify `git status --short` is empty, inspect `git diff` from the prior public release, scan tracked files and both archives for credentials and absolute local paths, and record artifact SHA-256 values.

Expected: clean tree, all tests pass, no secret or local-state findings, and two recorded checksums.

- [ ] **Step 2: Push the verified commit and confirm CI**

Push `main` to the existing `charleydou-collab/adaptive-agent-orchestrator` repository. Confirm the remote head equals the local verified commit and the GitHub Actions run concludes successfully.

- [ ] **Step 3: Create the v0.2.0 GitHub release**

Publish release notes derived from the changelog, attach both artifacts, include checksums and platform-specific limitations, and verify the release page and downloads. Attach the pull request if the execution workflow creates one.

- [ ] **Step 4: Update GitHub issues with evidence**

Comment on relevant open issues with the implementing commit, test result, release URL, and verified platform boundaries. Close only issues whose acceptance criteria are satisfied; keep host-dependent web limitations open.

- [ ] **Step 5: Upgrade the Codex installation**

Run the guarded installer in upgrade mode against the actual Codex and agents homes. Verify backups, installed version, skill and role discovery, unchanged primary model and reasoning effort, existing ledger preservation, state permissions, conversation isolation, context compilation, and all legacy orchestration controls.

- [ ] **Step 6: Update the existing ChatGPT web plugin in place**

Resolve the known existing plugin identity before upload. Upload the v0.2.0 web artifact through the supported workspace UI, never create a second identity on update failure, and verify the visible name, manifest version, description, and controls. Update Custom Instructions only if necessary and preserve unrelated user instructions.

- [ ] **Step 7: Report verified completion or precise pending actions**

Report GitHub commit, CI, release, checksums, Codex backup and verification results, web plugin identity/version, and remaining host limitations. If browser or workspace permissions block web installation, provide the artifact and exact manual steps and label web deployment pending rather than complete.
