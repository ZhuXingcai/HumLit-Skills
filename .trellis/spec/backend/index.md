# HumLit Python Development Guidelines

These guidelines describe the repository as it exists today. Read this index
and the guides relevant to the files being changed before implementation.

## Pre-Development Checklist

- Read [Directory Structure](./directory-structure.md) for every code change.
- Read [Error Handling](./error-handling.md) when touching CLI output, network
  calls, file parsing, or recovery behavior.
- Read [Quality Guidelines](./quality-guidelines.md) for every code or test
  change.
- Read [State and Persistence](./database-guidelines.md) when touching
  `.humlit/`, project sessions, caches, generated files, or atomic writes.
- Read [Observability](./logging-guidelines.md) when adding diagnostics or
  changing stdout/stderr behavior.

## Guides

| Guide | Scope |
|---|---|
| [Directory Structure](./directory-structure.md) | CLI registration, command modules, deterministic core logic, static Skill content, and tests |
| [State and Persistence](./database-guidelines.md) | File-backed state; this project has no database or ORM |
| [Error Handling](./error-handling.md) | JSON status contracts, source-level failures, recoverability, and exceptions |
| [Observability](./logging-guidelines.md) | Machine-readable stdout and human diagnostics |
| [Quality Guidelines](./quality-guidelines.md) | Tests, architecture checks, smoke tests, generated artifacts, and review gates |

## Core Contracts

1. `manifest.yaml` is the routing source of truth; generated route content in
   `SKILL.md` must stay byte-consistent with it.
2. CLI stdout is a JSON interface. Incidental prints are compatibility bugs.
3. A connector existing is not proof that a live source worked. Preserve
   `source_statuses` and distinguish success, empty results, conditional
   availability, and errors.
4. Agent-assisted academic outputs remain scaffolds or signals until a human
   verifies source texts and makes the scholarly judgment.
5. Runtime state and downloaded papers stay outside version control.
