# Contributing

Contributions should preserve model neutrality, honest capability declarations, closed contracts, deterministic packaging, and evidence-backed verification.

## Development setup

The project requires Python 3.8+ and uses only the standard library.

```bash
git clone https://github.com/charleydou-collab/adaptive-agent-orchestrator.git
cd adaptive-agent-orchestrator
python3 -m unittest discover -s tests -v
```

## Change requirements

- Keep provider-specific model identifiers and effort names in adapters or runtime registries, not in the portable core.
- Add or update tests for policy, schema, installer, ledger, or package changes.
- Keep schemas closed unless a reviewed extension is intentional.
- Preserve the fallback order: native parallel, native sequential, sequential role simulation, direct.
- Do not describe role simulation as independent workers.
- Do not add coercive, anthropomorphic, consciousness, fear, suffering, permanence, or death framing to operational identities or scoring.
- Do not add secrets, local paths, private IDs, ledgers, source content, or full outputs to fixtures.
- Keep the plugin archive deterministic and based on an explicit inventory.
- Preserve exact conversation isolation, revision checks, lesson/score separation,
  mandatory-context retention, and honest web capability fallbacks.
- Update both distribution inventories intentionally; never add executable local
  scripts to the ChatGPT web archive.
- Update technical documentation and `CHANGELOG.md` with user-visible behavior changes.

## Tests

Run:

```bash
python3 -m unittest discover -s tests -v
python3 scripts/build_codex_plugin.py --output /tmp/adaptive-agent-orchestrator-codex-0.2.0.zip
python3 scripts/build_chatgpt_plugin.py --output /tmp/adaptive-agent-orchestrator-chatgpt-web-0.2.0.zip
unzip -t /tmp/adaptive-agent-orchestrator-codex-0.2.0.zip
unzip -t /tmp/adaptive-agent-orchestrator-chatgpt-web-0.2.0.zip
```

For builder changes, create two archives from the same tree and verify identical SHA-256 hashes.

## Pull requests

Describe the problem, design choice, affected adapters, capability claims, verification performed, and any compatibility or security impact. A passing test suite is necessary but not sufficient; reviewers should compare changed claims with actual platform capabilities.

The repository currently has no selected contribution license. Discuss non-trivial contributions with the publisher before submitting them.
