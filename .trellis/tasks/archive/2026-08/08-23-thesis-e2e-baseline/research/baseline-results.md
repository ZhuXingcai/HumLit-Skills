# Baseline Trial Results

Date: 2026-08-23
Developer: ZhuXingcai

## Environment

- OS: Windows
- Python: 3.12.10
- HumLit Skills: 1.0.2
- pytest: 8.4.2
- Trellis: 0.5.19
- Dependencies: installed in repository-local `.venv` from
  `scripts/requirements-dev.lock`
- `humlit check`: success; Selenium Manager is available on demand, public API
  connectors are present but not live-verified by this check.

## Repository Gates

### First run

- `python -m pytest`: 304 passed, 9 skipped, 2 failed.
- `python scripts/verify_skill_architecture.py`: success.
- `python scripts/smoke_test.py --mode offline`: success, 5/5 checks.

The two failures were the same Windows portability defect in
`tests/test_register_skill.py`: `scripts/register_skill.py` only attempted a
directory symlink. This machine does not grant symlink creation by default, so
multi-client registration and idempotency returned `LINK_CREATE_FAILED`.

### Fix and targeted verification

`register_skill` now falls back to a Windows directory junction when symlink
creation is unavailable, without copying the checkout or overwriting an
existing target. The target comparison uses `os.path.lexists` so broken links
are not mistaken for absent paths.

- `python -m pytest tests/test_register_skill.py -vv`: 3 passed.
- The test accepts either a directory symlink or junction and still checks that
  the resolved path is the one source checkout.
- `python -m pytest`: 306 passed, 9 skipped.
- `python scripts/verify_skill_architecture.py`: success.
- `python scripts/smoke_test.py --mode offline`: success, 5/5 checks.
- `git diff --check`: no whitespace errors.

The 9 skipped tests are the repository's opt-in public-live/CNKI checks, not
failures. Their environment variables and lawful access prerequisites remain
unconfigured for this baseline turn.

## Offline Smoke

`python scripts/smoke_test.py --mode offline` succeeded with:

- research library: 2 imported records, 2 evidence records, 1 topic hypothesis;
- document I/O: DOCX write/read/patch and PDF metadata passed;
- format/review: 2 format signals, 9 human-judgment items;
- humanities tools: 9 polish signals, 2 anonymity leaks, 2 code matches,
  2 theory candidates;
- workflow routing: 10 workflows listed and 3 steps rendered.

These are deterministic program signals, not semantic academic judgments.

## Real DOCX Read-Only Trial

Input role: one representative academic DOCX sample from a repository-external
local directory.
The exact filename and path are intentionally omitted from tracked records.

All output files were written under an OS temporary directory outside the
repository and are not part of the Git diff.

| Command | Status | Non-sensitive observation |
|---|---|---|
| `read-paper <docx>` | success | 24,025 text characters; observed body, tables, and footers |
| `review-signals <docx>` | success | 4 signal groups; output remains a signal report |
| `journal-check <docx>` | success | 5 deterministic issues; no anonymity leaks detected |
| `polish-signals <docx>` | success | 6 `weak_transition` signals |

`read-paper` explicitly reported four unobserved areas: embedded objects,
images without OCR, drawing semantics, and tracked deletions. The output also
contained one observability warning. A later Agent/researcher must not claim
that the returned text represents every visual or revision layer of the DOCX.

`review-signals` exposed four `needs_human_judgment` groups (2, 2, 3, and 2
items respectively). The trial therefore confirms that the current boundary is
appropriate: scripts measure and expose signals; the researcher verifies
source text and decides what matters.

## Live and Conditional Work

No public live search, OA download, or CNKI desktop action was run in this
baseline turn. The repository suite intentionally skips live tests unless the
corresponding environment variables and lawful access are enabled. These should
be separate follow-up checks so network conditions are not mixed with offline
regression evidence.

## Next Actions

1. Rerun the full pytest suite after the Windows registration fix.
2. Run a synthetic, non-sensitive `review`/`write`/`validate` chain and record
   only output schemas and counts.
3. Optionally run public live probes (`openalex`, `semantic`, `arxiv`, `nssd`,
   `dblp`, OA DOI, citations) with each result classified as success,
   conditional, empty, or error.
4. If a deterministic defect remains, create a separate Trellis child task
   with a minimized fixture and a narrow acceptance criterion.

## Resume on Another Device

```powershell
git fetch origin
git pull --ff-only
trellis update --codex --skip-existing
python ./.trellis/scripts/init_developer.py <developer-name>
python ./.trellis/scripts/get_context.py
python ./.trellis/scripts/task.py current --source
```

Recreate `.venv` from `DEVELOPMENT.md`; do not copy runtime state or thesis
materials into the checkout.
