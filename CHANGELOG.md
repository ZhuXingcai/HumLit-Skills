# Changelog

## 1.0.1

### macOS Desktop Detection

- Use one shared list of standard macOS Edge/Chrome application paths for
  environment checks and the CNKI browser driver.
- Preserve PATH-based browser detection for Homebrew and custom installations.
- Keep CNKI unavailable when the browser exists but no compatible driver is
  ready, instead of reporting a false-positive desktop capability.

### Verification

- Add regression coverage for standard application paths and PATH fallback.
- Re-run the full test suite, offline end-to-end smoke, live API canary, release
  verifier, and wheel installation checks.

## 1.0.0

### Standalone Project Identity

- Publish HumLit Skills as an independent project with the `humlit-skills`
  Skill and package ID and the `humlit` console command.
- Store runtime data under `.humlit` and use `HUMLIT_*` environment variables.
- Point installation and update checks to
  `ZhuXingcai/HumLit-Skills`.
- Provide one public identity across package metadata, documentation, runtime
  paths, environment variables, and release checks.

### Capability Boundaries

- Add a machine-readable contract covering every command with maturity,
  preconditions, positive/negative use cases, outputs, failures, and smoke
  evidence.
- Separate stable offline, conditional live, conditional desktop,
  Agent-assisted, and experimental capabilities in the Skill router and docs.
- Mark BASE explicit opt-in, remove it from aggregate search and fallback, and
  remove the non-functional executable citation-suggestion workflow.

### End-to-End Reliability

- Restore NSSD against its current JSON form endpoint and share the same
  implementation between sync and async search.
- Add `--source api` for the five maintained public connectors without loading
  CNKI.
- Make DOI download save a signature-verified PDF atomically, with OpenAlex OA
  fallback and an explicit `--link-only` mode.
- Add `pypdf` to runtime metadata and locked dependencies so `pdf-meta` is
  installable rather than a dormant command.

### Verification

- Add an offline artifact smoke runner for research libraries, evidence
  scaffolds, Word/PDF I/O, thesis formatting, review signals, and humanities
  tools.
- Expand scheduled live canaries to all maintained public sources, OA DOI
  resolution, and citation networks.
- Expand positive and negative routing evaluation to general office documents,
  plagiarism-percentage claims, and official editorial decisions.
