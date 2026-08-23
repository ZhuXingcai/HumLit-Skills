# HumLit Skills Development Guide

This repository uses Trellis for task context, project conventions, and
cross-device handoff.

## First Setup on a Device

```powershell
git clone https://github.com/ZhuXingcai/HumLit-Skills.git
Set-Location HumLit-Skills
trellis update --codex --skip-existing
python ./.trellis/scripts/init_developer.py <developer-name>
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r scripts/requirements-dev.lock
.\.venv\Scripts\python.exe -m pip install --no-deps -e .
```

If `trellis update` is unavailable on the second device, install the Trellis
CLI first, then rerun the command. Do not run `trellis init --force` over a
tracked project because it can overwrite customized project specifications.

## Starting or Continuing Work

```powershell
python ./.trellis/scripts/get_context.py
python ./.trellis/scripts/get_context.py --mode phase
python ./.trellis/scripts/task.py list
```

- Continue the active Trellis task when it matches the work.
- Create a new task for a separate multi-step change and write its goal,
  acceptance criteria, risks, validation, and out-of-scope items to `prd.md`.
- Keep feature branches small and task-scoped. Record the intended branch in
  `task.json` with `task.py set-branch` after the branch is created.
- Before switching devices, commit the code, tracked Trellis task artifacts,
  and useful journal updates. Push only after reviewing for private data.

## Cross-Device Handoff

1. Finish a coherent work unit and run the task's relevant verification.
2. Check `git status` for thesis documents, downloaded papers, credentials,
   cookies, `.humlit/`, or machine-local paths; none belong in commits.
3. Update the active task `prd.md` and research notes with current progress,
   decisions, failures, and the exact next step.
4. Commit and push from the current device.
5. On the other device, fetch/pull, initialize the local Trellis developer
   identity, recreate `.venv`, and run `get_context.py` before editing.

Trellis `.developer`, `.current-task`, and runtime hook state are intentionally
device-local. Task PRDs, project specs, and journals are tracked and form the
handoff record.

## Baseline Verification

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe scripts/verify_skill_architecture.py
.\.venv\Scripts\python.exe scripts/smoke_test.py --mode offline
```

Run live probes only when their network, API quota, browser, and lawful access
requirements are available. A conditional upstream result is not the same as
a repository failure.

## End-to-End Academic Trials

- Work on copies or derived test artifacts; never mutate the only copy of a
  thesis or research source.
- Keep private source documents outside Git. Trellis records may describe file
  roles and observed failures but must not contain identifying excerpts.
- Begin with the deterministic offline workflow, then add public live search,
  OA download, and CNKI only as separately reported capability layers.
- Record every trial's inputs, command sequence, artifacts, observed status,
  manual verification points, and failures in the active Trellis task.
- Convert a real failure into a minimized synthetic fixture before adding a
  regression test.
