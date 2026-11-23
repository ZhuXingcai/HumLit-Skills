# Changelog

## Unreleased

### Local Library, Long-Document Slicing, Offline Venue Screening & Writing Tools

- Add `zotero` command (`scripts/core/zotero.py`): zero-dependency read-only SQLite snapshot reader (never locks a running Zotero client, never writes back) with collection filtering and local PDF attachment mapping into `.humlit` project sessions.
- Add long-document TOC & chapter slicing (`scripts/core/sections.py`): `read-paper` gains `--numbered`, `--toc`, `--section`, `--max-chars`, and PDF text-layer extraction (with explicit `observability` boundaries); `read-detail` gains `--toc`, `--section`, `--max-chars`, and offline local PDF extraction.
- Add offline international core & CAS Early Warning screening (`scripts/core/venues.py` + `scripts/core/data/venue_index.json.gz`, 30,300+ ISSN): `search` supports `--exclude-warning` and international `--core` tokens (`SCI`, `SSCI`, `AHCI`, `ESCI`, `CCF-A/B/C`); `journal-check` supports optional `--journal-name` offline index signals.
- Upgrade `cite` and `export` (`scripts/core/formatter.py`): add `gbt7714-author-year`, `chinese-econ`, pure-ASCII BibTeX citekeys, `--indices`, `--from-file`, `--rewrite-output`, `--bibtex-output`, and `--in-text`.
- Add `data-table` and `rebuttal` commands (`scripts/core/research_tools.py`, `scripts/cli/research_cmd.py`): deterministic summary/correlation/regression/comparison tables (Markdown, LaTeX `booktabs`, Word three-line `.docx`) and structured peer-review comment parsing with manuscript `[Pn]` anchor linking and `patch-docx` templates.

### CNKI Advanced Retrieval

- Add `--condition` (repeatable, up to 10), `--professional`, `--match` and
  `--cross-language` to `search`; `batch-search` gains `--match` and
  `--cross-language`. Existing arguments keep their behavior.
- Add `retrieval` to the JSON payload: requested vs applied conditions,
  `verified`, the submitted professional expression, and `total_hits`.
- Add `references/search/cnki-advanced-retrieval.md` (concept-group method,
  field and match-mode selection, iteration strategy, anti-patterns) and
  `references/search/cnki-professional-syntax.md` (official CNKI professional
  search grammar).

### Behavior Change (intentional)

- Structured conditions are compiled into a CNKI professional-search expression
  and executed on the professional search page
  (`/kns8s/AdvSearch?type=expert`). Live verification showed the advanced-search
  form uses custom dropdowns with no native `<select>`, so programmatic filling
  could not reliably set field/logic/match controls; the professional page is a
  single textarea that can be written and read back.
- `AND`/`OR`/`NOT` share the same precedence in professional search, so `或者`/
  `不含` are compiled with explicit parentheses against the neighbouring
  condition. Without this, `A AND B OR C` evaluates left-to-right.
- The submitted expression is read back after results render and compared with
  the request; a mismatch returns `CNKI_RETRIEVAL_MISMATCH`. When readback is
  impossible, `retrieval.verified` is `null` rather than claiming success.
- Verified-empty result pages now report `retrieval.total_hits = 0`. CNKI's real
  empty page reads `抱歉，暂无数据，请稍后重试。`, so `请稍后重试` can no longer
  veto an explicit "暂无数据" marker — otherwise a legitimate 0-hit query was
  misreported as an unusable page.
- Local WebDriver connections now bypass `HTTP_PROXY`/`HTTPS_PROXY` by adding
  loopback hosts to `NO_PROXY`. In proxied sandboxes Selenium's request to the
  local driver port was sent to the proxy, which replied `unhandled request`,
  failing every CNKI command with an unrelated-looking error.
- New error codes: `CNKI_INVALID_EXPRESSION`, `CNKI_TOO_MANY_CONDITIONS`,
  `CNKI_CONDITION_NOT_APPLIED`, `CNKI_RETRIEVAL_MISMATCH`,
  `CNKI_OPTION_SOURCE_MISMATCH`.

## 1.0.2

### CNKI First-Run Readiness

- Treat an available Selenium Manager as an on-demand driver provider instead
  of rejecting a clean machine because ChromeDriver is not cached yet.
- Preserve side-effect-free environment checks: the matching driver is
  downloaded only when a real CNKI browser operation starts.
- Return `DRIVER_MISSING` when Selenium Manager cannot provision a driver, and
  validate empty CNKI queries before network or browser startup.

### Live API Reliability

- Send the configured Semantic Scholar API key on citation-network requests.
- Propagate rate limits and source failures instead of returning an empty
  citation graph as a partial success.
- Add opt-in pytest canaries for maintained public APIs and real CNKI network
  and desktop search.

### Verification

- Verify clean-cache ChromeDriver provisioning against Chrome 151 on macOS.
- Complete a real CNKI desktop search and retain deterministic regression
  coverage for preflight, error classification, and empty-input behavior.

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
