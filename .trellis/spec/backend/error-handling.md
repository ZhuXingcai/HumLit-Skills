# Error Handling

## Output Contract

Public commands return JSON objects with a `status` field. Use the established
status vocabulary deliberately:

- `success`: the requested operation completed with usable output.
- `partial`: some requested sources/items succeeded and others failed.
- `warning`: output exists but the caller must consider a stated limitation.
- `error`: the requested operation failed and includes a stable `code` and a
  useful `message`.
- `conditional`: used by smoke evidence when a maintained integration is
  unavailable for an expected environmental reason, such as anonymous API rate
  limits.

Do not turn network errors, parsing errors, authentication failures, or rate
limits into empty result sets. Multi-source commands must preserve per-source
details in `source_statuses`.

## Exception Boundaries

- Core helpers may raise focused exceptions when callers cannot safely
  continue. `SessionDataError` is the model for a recoverable user-state
  failure with a stable code and optional artifact path.
- CLI callbacks should convert expected operational failures into structured
  JSON. The top-level entry point currently catches only `SessionDataError`;
  do not add a blanket `except Exception` there that hides programming defects.
- Catch broad exceptions only at isolation boundaries that intentionally
  aggregate independent work, such as smoke checks. Include the exception type
  and message in the resulting diagnostic.
- Cleanup handlers may suppress only cleanup failures after preserving the
  original exception. Atomic-write helpers demonstrate this pattern.

## Recovery and Evidence

- Recovery guidance must be actionable and must not claim that an action was
  performed when it was only suggested.
- CNKI failures must respect lawful institutional access and must never bypass
  authentication or CAPTCHAs.
- Download success requires validating the response as the requested artifact;
  OA PDF paths are checked for a PDF signature and non-trivial size in live
  smoke coverage.
- Agent-assisted review, writing, polishing, qualitative coding, and theory
  matching must expose evidence boundaries and human-judgment requirements.

## Anti-Patterns

- Printing a traceback or progress message to stdout before the JSON payload.
- Returning `success` because a connector module imported successfully.
- Treating `API_RATE_LIMIT`, offline state, or parse failure as `NO_RESULTS`.
- Treating a CNKI page with `captchaId`, slider text, `请稍后重试`, or a missing
  result table as verified empty. A URL leaving `/verify/` is not proof that
  the security challenge completed; propagate a structured CNKI error until
  the result table or an unambiguous empty-result page is confirmed.
- Swallowing corrupt session data and silently starting an empty session.
- Inventing bibliographic fields or academic conclusions to fill missing data.

## Scenario: CNKI Search Page State Classification

### 1. Scope / Trigger

- Trigger: CNKI search or batch-search encounters a security challenge or does
  not load the expected result DOM.

### 2. Signatures

- `CnkiSecurityError(code, message, diagnostics=None)` carries a stable error
  code plus bounded page-state diagnostics.
- `_classify_result_page(driver)` returns `results`, `verified_empty`,
  `security_gate`, or `unknown`.

### 3. Contracts

- CNKI core failures return `status=error`, stable `code`, `message`, and an
  optional `diagnostics` object.
- Diagnostics may contain a query-stripped URL, title, boolean CAPTCHA markers,
  and a fixed marker map. They must not contain cookies, credentials, complete
  page text, or challenge query values.
- CLI aggregation preserves these fields under `source_statuses.cnki`.

### 4. Validation & Error Matrix

- `/verify/`, `captchaId`, slider text, or visible CAPTCHA DOM ->
  `CNKI_SECURITY_GATE_*`.
- Result table with rows -> successful result parsing.
- Explicit empty marker without retry/security markers -> verified empty.
- Missing table, or empty marker combined with `请稍后重试` / security text ->
  `CNKI_RESULT_PAGE_UNAVAILABLE` or `CNKI_SECURITY_GATE_UNRESOLVED`.

### 5. Good/Base/Bad Cases

- Good: result rows are present and parsed.
- Base: an unambiguous empty page returns `empty`.
- Bad: a retry/challenge page never returns `NO_RESULTS`.

### 6. Tests Required

- Synthetic driver tests for `captchaId`, slider text, timeout propagation,
  verified empty, retry page, and structured diagnostics.
- A live desktop probe may confirm behavior, but it remains opt-in and cannot
  replace deterministic tests.

### 7. Wrong vs Correct

Wrong: mark verification successful as soon as the URL leaves `/verify/`, then
parse zero rows as `NO_RESULTS`.

Correct: require two consecutive clean security checks, then separately confirm
result rows or an unambiguous empty page; otherwise return a structured error.

## Reference Examples

- Structured session error: `scripts/cli/_common.py::SessionDataError`
- Per-source status handling: `scripts/core/search.py` and
  `scripts/core/search_async.py`
- Live status classification: `scripts/smoke_test.py::classify_live_status`
- Release-level contract validation: `scripts/verify_release.py`
