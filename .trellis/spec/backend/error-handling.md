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
- Swallowing corrupt session data and silently starting an empty session.
- Inventing bibliographic fields or academic conclusions to fill missing data.

## Reference Examples

- Structured session error: `scripts/cli/_common.py::SessionDataError`
- Per-source status handling: `scripts/core/search.py` and
  `scripts/core/search_async.py`
- Live status classification: `scripts/smoke_test.py::classify_live_status`
- Release-level contract validation: `scripts/verify_release.py`

