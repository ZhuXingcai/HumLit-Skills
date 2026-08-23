# Directory Structure

## Repository Layout

```text
HumLit-Skills/
├── scripts/
│   ├── literature.py          # unified entry point and lazy command loading
│   ├── cli/                   # argparse registration and command orchestration
│   ├── core/                  # reusable deterministic/domain logic
│   ├── smoke_test.py          # offline and opt-in live end-to-end probes
│   └── verify_*.py            # architecture and release gates
├── tests/                     # pytest suite and fixtures
├── static/
│   ├── core/                  # always-loaded Skill rules
│   └── fragments/task/        # task-specific prompt fragments
├── references/               # on-demand operational and academic references
├── evals/                    # capability contracts and evaluation evidence
├── manifest.yaml             # routing and capability source of truth
├── SKILL.md                  # generated discovery/router surface
└── pyproject.toml             # package metadata and pytest configuration
```

## Module Boundaries

- `scripts/literature.py` detects the command, lazily imports the owning
  `scripts/cli/*_cmd.py` module, parses arguments, and catches only top-level
  session corruption errors. Keep it small and free of domain logic.
- `scripts/cli/registry.py` maps every public command name to one command
  module. Adding or moving a command requires updating the registry and the
  related command registration tests.
- `scripts/cli/*_cmd.py` owns argparse definitions and orchestration. Shared
  session, JSON emission, and report helpers live in `scripts/cli/_common.py`.
- `scripts/core/` owns reusable behavior. Feature families with multiple
  focused modules use subpackages, for example `core/cnki/`,
  `core/thesis_format/`, and `core/blind_review/`.
- `static/fragments/task/*.md` contains task-specific Agent instructions.
  Do not move execution logic into prompt files.
- `references/` is loaded on demand. Keep high-frequency routing rules in
  `manifest.yaml`/fragments and detailed operational material in references.

## Placement Rules

- Add a public CLI command to the closest existing `cli/*_cmd.py`; create a
  new command module only for a distinct capability family.
- Put reusable parsing, validation, formatting, I/O, and connector logic in
  `core/`, not in argparse callbacks.
- Add tests under `tests/test_<capability>.py`. End-to-end command coverage
  commonly uses subprocesses against `scripts/literature.py`, while focused
  units import `core` or `cli` helpers directly.
- Put stable fake upstream responses in `tests/fixtures/`; use pytest temp
  directories for generated artifacts.
- Do not commit runtime `.humlit/` state, downloaded `papers/`, caches, build
  output, or local virtual environments.

## Naming and Imports

- Modules, functions, variables, and JSON keys use `snake_case`; classes use
  `PascalCase`; constants use `UPPER_SNAKE_CASE`.
- New Python modules should use `from __future__ import annotations` when
  consistent with the neighboring module.
- Prefer `pathlib.Path` for paths and explicit UTF-8 for text files.
- Keep imports package-local in the established style (`from core...`,
  `from cli...`) because `literature.py` adds `scripts/` to `sys.path` and the
  package maps `scripts` as its module root.

## Reference Examples

- Lazy entry point: `scripts/literature.py`
- Command mapping: `scripts/cli/registry.py`
- Shared CLI/session helpers: `scripts/cli/_common.py`
- Split feature package: `scripts/core/thesis_format/`
- Offline end-to-end scenarios: `scripts/smoke_test.py`

