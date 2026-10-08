# Publishing guide

GitHub publication and ChatGPT public-directory publication are separate release processes. A repository or GitHub Release makes source and artifacts available; it does not submit, review, approve, or list the plugin in ChatGPT.

## GitHub release checklist

1. Run the full test suite.
2. Build the ZIP from committed source.
3. Build it a second time and compare SHA-256 hashes to confirm reproducibility.
4. Inspect the archive inventory and confirm it contains one plugin root.
5. Scan tracked files and the archive for credentials, local paths, private IDs, ledger data, and development records.
6. Update `CHANGELOG.md` and the semantic version in `plugin.json`.
7. Confirm the chosen license and publisher identity.
8. Commit from a clean repository, create a signed or annotated tag, and publish the ZIP as a release asset.

Example build verification:

```bash
mkdir -p dist
python3 scripts/build_chatgpt_plugin.py --output dist/one.zip
python3 scripts/build_chatgpt_plugin.py --output dist/two.zip
shasum -a 256 dist/one.zip dist/two.zip
unzip -l dist/one.zip
```

## Public ChatGPT submission checklist

The package is skills-only, so it does not need MCP test cases, reviewer credentials, or an MCP demo solely for this plugin. Before public submission, verify the current portal requirements and complete these publisher-owned decisions:

- a selected, verified individual or business developer identity;
- `developerName` consistent with the verified identity if the portal still reads it from the ZIP;
- a public website identifying the plugin, its purpose, and publisher;
- a public support page with a working support route;
- a privacy policy covering actual data collection, processing, sharing, retention, deletion, and third-party hosting behavior;
- terms of service approved by the publisher;
- a square PNG logo at least 256×256 and a composer icon at least 48×48, each no larger than 5 MiB;
- current supported category, country targeting, release notes, and optional translations;
- inspection of the saved submission after upload, because portal ownership and locking behavior may change.

Do not use placeholder domains or guessed URLs. Every listing URL must be an absolute public HTTPS URL, accessible without a private login, and visibly serve its declared purpose.

## Manifest fields

Public listing fields belong under `extensions.com.openai.interface`:

| Field | Current repository status |
| --- | --- |
| `displayName` | Present; must remain at most 30 characters |
| `shortDescription` | Present; must remain at most 30 characters |
| `longDescription` | Present; technical behavior and limitations described |
| `developerName` | Must be set from the publisher's verified identity |
| `category` | Present; reconfirm against the current portal list |
| `defaultPrompt` | Three single-line prompts, each at most 128 characters |
| `websiteURL` | Repository URL supplied; verify public access before portal upload |
| `supportURL` | Public GitHub Issues URL supplied; verify issues remain enabled |
| `privacyPolicyURL` | Publisher must approve, host, and verify |
| `termsOfServiceURL` | Publisher must approve, host, and verify |
| `logo` and `composerIcon` | Publisher must supply or approve actual image assets |

Do not claim these fields are complete merely because documentation drafts exist in the repository.

## Release notes for 0.1.0

Suggested portal release notes:

> Initial release of a model-neutral management skill for bounded task decomposition, capability-based routing, KPI contracts, structured completion reports, verification and repair, honest platform fallback, and optional local performance scoring on supported adapters.

## Known publication boundary

This project coordinates host capabilities. It does not bundle provider models, native worker infrastructure, knowledge-base connectors, office-document engines, image generators, or cloud persistence. Listing language must not imply those capabilities are included.
