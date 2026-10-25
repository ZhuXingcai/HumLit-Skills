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

If a `captchaId` query parameter remains after the challenge UI has disappeared,
do not treat the parameter alone as a permanent gate. A visible challenge still
wins, but an actually available search/result DOM is evidence that the retained
parameter is stale and the workflow may continue.

## Scenario: CNKI Retrieval Condition Contract

### 1. Scope / Trigger

- Trigger: a CNKI search builds retrieval conditions, a professional expression,
  or must report whether the submitted query actually took effect.

### 2. Signatures

- Core model: `core/cnki/query.py` — `CnkiCondition`, `parse_condition`,
  `validate_conditions`, `validate_professional_expression`, `CnkiQueryError`.
- Driver: `search.py::_advanced_search(driver, conditions) -> dict` with
  `{"ok", "applied", "rows", "error"}`; `_professional_search`,
  `_verify_applied_conditions`, `_read_total_hits`.
- Output: `retrieval` object on the search payload plus `meta` out-parameter
  used by `search_cnki` / `batch_search_cnki`.

### 3. Contracts

- Every requested condition must be verified as applied (field select, logic,
  match mode, and written value) **before** submitting the search.
- A partially applied multi-condition query is a failure, never a success.
- `retrieval.verified` is `true` (read-back matched), `false` (mismatch, must
  carry `CNKI_RETRIEVAL_MISMATCH`), or `null` (page cannot be read). `null`
  never means verified.
- `ADV_SEARCH_FALLBACK` is limited to "form unavailable and a keyword exists".
  It must not swallow per-condition application failures.

### 4. Validation & Error Matrix

- Unknown field / unspaced `* + -` / unbalanced quotes or parentheses / value
  over 120 chars / match mode on 主题 -> `CNKI_INVALID_EXPRESSION`.
- More than 10 conditions -> `CNKI_TOO_MANY_CONDITIONS`.
- Condition not applied -> `CNKI_CONDITION_NOT_APPLIED`.
- Read-back mismatch -> `CNKI_RETRIEVAL_MISMATCH`.
- Retrieval arguments on a non-CNKI source -> `CNKI_OPTION_SOURCE_MISMATCH`.

### 5. Tests Required

- `tests/test_cnki_query.py` (pure parsing/validation) and
  `tests/test_cnki_advanced_contract.py` (fake driver: partial fill, read-back
  mismatch, unreadable page) must stay offline and deterministic.

## Reference Examples

- Structured session error: `scripts/cli/_common.py::SessionDataError`
- Per-source status handling: `scripts/core/search.py` and
  `scripts/core/search_async.py`
- Live status classification: `scripts/smoke_test.py::classify_live_status`

## Scenario: CNKI Manual Institution Selection and Local Session Isolation

### 1. Scope / Trigger

- Trigger: `auth-cnki` is used by different people or on a shared workstation,
  where an existing browser profile must not silently select or expose the
  previous user's institution session.

### 2. Signatures

- Core: `authenticate_cnki(..., institution: Optional[str] = None,
  reuse_session: bool = False, force: bool = False) -> dict`
- CLI: `auth-cnki [--institution NAME] [--reuse-session] [--force]`

### 3. Contracts

- Omitting `--institution` leaves institution selection to the user in the
  visible browser. No user document, path, conversation context, or repository
  fixture may populate this argument.
- Omitting `--reuse-session` starts a fresh manual authentication flow and
  clears CNKI/auth-origin cookies and web storage in the dedicated local
  profile. It does not delete the profile directory or any downloaded papers.
- `--reuse-session` is the only opt-in path that loads the local cookies/profile
  before checking for `already_authenticated`.
- Successful output includes `session_reused`, `session_reset`,
  `local_session_exists`, and `institution_selected`; it must not include
  cookies, credentials, or institution data inferred from private input.
- Cookies/profile remain under the ignored local `.humlit/` directory and are
  never part of public repository state.

### 4. Validation & Error Matrix

- No explicit institution -> `institution_selected=false`; browser remains
  available for manual selection.
- Explicit `--institution NAME` -> auto-selection may be attempted; failure to
  find it is recoverable and instructs the user to select manually.
- Existing local session without `--reuse-session` -> do not return
  `already_authenticated`; reset the relevant browser-origin state and prompt
  for manual authentication.
- `--reuse-session` with valid institution access -> `already_authenticated=true`
  and `session_reused=true`.
- CAPTCHA/security challenge -> browser is shown in the foreground and remains
  visible after verification; unresolved challenges return structured CNKI
  errors rather than empty results.
- A driver connected through the active project `DevToolsActivePort` is a shared
  user-visible browser; commands save cookies but must not call `quit()` on it.
  Only a browser created for the current command may be closed automatically.

### 5. Good/Base/Bad Cases

- Good: a new student runs `auth-cnki`, manually picks their school, completes
  login, and receives `session_reused=false`.
- Base: the same student later runs `auth-cnki --reuse-session` and receives a
  local-session reuse result without re-entering credentials.
- Bad: an agent derives a school from a thesis PDF and passes `--institution`
  without user instruction, or silently reuses a prior user's cookies.

### 6. Tests Required

- Assert `_select_cnki_institution(driver, None)` does not navigate.
- Assert default authentication does not call `_load_cookies`, clears only
  browser-origin state, and opens the generic auth URL.
- Assert `reuse_session=True` is required for `already_authenticated`.
- Assert CAPTCHA success does not call `_hide_browser` and the browser is
  brought to the foreground.
- Assert public fixtures contain synthetic names/institutions only.

### 7. Wrong vs Correct

#### Wrong

```text
auth-cnki  -> load previous cookies -> infer a school -> auto-select -> hide browser
```

#### Correct

```text
auth-cnki  -> show browser -> user selects institution and authenticates
auth-cnki --reuse-session  -> explicitly reuse the current local session
```

### 8. Authentication-to-Action Handoff

- `auth-cnki` is a prerequisite, not completion of a search/download request.
- After a successful manual login, continue the original CNKI action using the
  saved local state. Do not invoke default authentication or `--force` again.
- If authentication polling times out while the user confirms that the retained
  browser is logged in, run the intended search once and use its structured page
  classification as the deciding probe. Re-authenticate only after that action
  reports an authentication or unresolved-security error.
- A focused security exception raised while polling must propagate; swallowing
  it and navigating to the verification page again creates duplicate challenge
  cycles and loses the actual failure state.
- Release-level contract validation: `scripts/verify_release.py`
