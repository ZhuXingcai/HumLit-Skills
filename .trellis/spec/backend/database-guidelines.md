# State and Persistence

## Current Architecture

HumLit Skills has no database, ORM, migration system, or remote persistence.
State is deliberately local and file-backed under `.humlit/`, resolved through
`scripts/core/paths.py`. Project-specific research sessions live under
`.humlit/projects/<safe-name>/`.

## Persistence Rules

- Resolve runtime locations through `state_path()` and related helpers instead
  of hard-coding a repository-relative `.humlit` path.
- Sanitize user-provided project names before using them as directory names;
  follow `_safe_project_name()` in `scripts/cli/_common.py`.
- Version persistent JSON payloads. Session data currently uses
  `SESSION_SCHEMA_VERSION` and validates the root shape before use.
- Use UTF-8 and `ensure_ascii=False` for user-facing Chinese data.
- Use atomic replacement for durable JSON writes: create a temp file in the
  target directory, flush and `fsync`, then `os.replace` it. See
  `_save_session()` and `scripts/evaluate_routing.py::_atomic_json_write()`.
- On corrupt user state, preserve evidence before reporting failure. Current
  session loading copies the invalid file to a timestamped `.bak` and raises
  `SessionDataError` with the backup path.
- Merge records by stable scholarly identity where possible: normalized DOI,
  source identifier, URL, then normalized title. Do not deduplicate solely by
  list position.

## Generated and User-Owned Files

- Commands that create or patch documents must write to an explicit output
  path and report that path in JSON.
- Tests must create state and documents in pytest `tmp_path` or the smoke
  runner's temporary directory.
- Never use real thesis materials as mutable fixtures. Copy or synthesize a
  minimized, non-sensitive fixture before committing it to the repository.
- `.humlit/`, `papers/`, caches, and local environment files remain ignored.

## Non-Applicable Database Practices

Do not introduce database schemas, migrations, or an ORM for a local feature
without a separate architectural decision. The existing product contract is a
portable CLI with inspectable local files.

## Scenario: Register One Checkout with Multiple Agent Clients

### 1. Scope / Trigger

This applies when `scripts/register_skill.py` exposes one checkout under one or
more client Skill directories. The operation is filesystem infrastructure: it
must not duplicate the repository or overwrite an existing target.

### 2. Signatures

```python
register_skill(source: Path, home: Path, clients: Iterable[str]) -> dict
```

CLI:

```text
python scripts/register_skill.py --source <checkout> --client <client> [...]
```

### 3. Contracts

- `source/SKILL.md` must exist.
- Supported clients are the keys in `CLIENT_SKILL_DIRS`.
- The target is `<home>/<client-skill-root>/humlit-skills`.
- POSIX and privileged Windows environments may use a directory symlink.
- Windows without symlink privilege falls back to an NTFS directory junction.
- Re-registering the same resolved source returns `already_registered`.
- A different existing target is never overwritten.

### 4. Validation and Error Matrix

| Condition | Result |
|---|---|
| Missing `SKILL.md` | `INVALID_SKILL_SOURCE` |
| Unknown client | per-client `UNKNOWN_CLIENT` |
| Existing target resolves to source | `already_registered` |
| Existing target resolves elsewhere | `TARGET_EXISTS` |
| Symlink and Windows junction both fail | `LINK_CREATE_FAILED` |

The aggregate status is `success`, `partial`, or `error` based on per-client
results. Broken links must be detected with `os.path.lexists`, not mistaken for
an absent target.

### 5. Good / Base / Bad Cases

- Good: register one checkout for Codex, Claude, and TRAE; all targets resolve
  to the same source and no repository copy is created.
- Base: run the same registration twice; the second call is successful and
  idempotent.
- Bad: a real directory already exists at a target; return `TARGET_EXISTS` and
  preserve its contents.

### 6. Tests Required

- Multi-client registration asserts `registered == 3` and every target resolves
  to the source.
- Link assertions accept a directory symlink or Windows junction.
- Idempotency asserts `already_registered` on the second call.
- Existing-target coverage asserts the marker file remains unchanged.
- Run these tests on Windows where junction fallback is required, plus the full
  pytest and platform-adversarial suite.

### 7. Wrong vs Correct

Wrong: assume `Path.symlink_to()` is universally available on Windows and
return `LINK_CREATE_FAILED` when Developer Mode or elevated privilege is absent.

Correct: attempt the symlink first, fall back to a native junction on Windows,
then compare the resolved target to preserve one-checkout semantics.
