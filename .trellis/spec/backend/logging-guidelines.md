# Observability and Diagnostics

## Current Convention

The project does not use a logging framework. Its primary observability
surface is structured JSON on stdout, consumed by agents, tests, and shell
automation. Human-readable argparse help and fatal interpreter diagnostics may
use the normal terminal streams.

## Stdout Rules

- A successful public command emits exactly one parseable JSON document to
  stdout through `_output()`/`emit()` or an equivalent final serializer.
- Preserve UTF-8 output on Windows; `scripts/literature.py` reconfigures stdio
  where supported.
- Do not add debug prints, progress bars, library banners, or subprocess noise
  to stdout. `scripts/smoke_test.py::_run_cli()` treats polluted stdout as a
  contract failure.
- Include useful counts, output paths, source status, warnings, and evidence
  fields in the JSON payload instead of narrating them separately.

## Stderr Rules

- Use stderr for diagnostics that cannot be represented in the final payload,
  such as an unexpected subprocess failure or argparse's own usage error.
- Never write credentials, cookies, institution session values, complete
  sensitive document contents, or private filesystem state to either stream.
- When reporting a command or URL, redact secrets and query parameters that may
  contain tokens.

## Test and CI Observability

- Subprocess tests should capture both streams and include them in assertion
  messages when a command fails.
- Smoke results record each check by stable ID with `success`, `conditional`,
  or `error`, then summarize passed/conditional/failed counts.
- CI should retain enough structured output to distinguish repository defects
  from conditional upstream availability.

## Future Logging

If a logging framework becomes necessary, it must default to stderr and remain
disabled or non-polluting for machine-readable CLI calls. Adding it requires
tests proving that stdout remains a single JSON document.

