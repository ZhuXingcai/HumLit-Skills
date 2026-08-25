# Quality Guidelines

## Required Development Loop

1. Search for an existing command, core helper, output field, manifest entry,
   and test pattern before adding a new one.
2. Add focused tests for changed behavior, including error and boundary paths.
3. Run the smallest relevant pytest selection while iterating.
4. Before completion, run the full repository gates appropriate to the change.

## Repository Gates

```powershell
python -m pytest
python scripts/verify_skill_architecture.py
python scripts/smoke_test.py --mode offline
```

For release or routing changes, also run the relevant release/evaluation gates
documented in `.github/workflows/ci.yml`, `scripts/verify_release.py`, and
`evals/README.md`. Live probes are opt-in because network services, API quotas,
CNKI browser state, and institutional authorization are conditional.

## Required Patterns

- Keep `manifest.yaml`, generated `SKILL.md` routes, task fragments, command
  registry, capability contract, and tests consistent.
- Regenerate derived content with `scripts/generate_skill_index.py`; do not
  hand-edit a generated block and leave its source unchanged.
- Preserve lazy command imports so API-only commands do not load Selenium or
  CNKI code. Tests in `test_lazy_import.py`, `test_registry.py`, and
  `test_cmd_modules.py` protect this boundary.
- Use deterministic fixtures for upstream responses. Keep real live calls in
  opt-in tests or smoke probes.
- Make file operations explicit, UTF-8 aware, and safe on Windows Chinese
  paths. Platform-adversarial tests are part of the project contract.
- Test both the returned JSON contract and observable artifact contents for
  commands that write files.

## Academic and Safety Review

- Verify that code never fabricates missing metadata or upgrades heuristic
  signals into scholarly conclusions.
- Preserve the difference between deterministic program output and semantic
  interpretation performed by an Agent or researcher.
- Confirm paywall, authentication, CAPTCHA, privacy, and copyright boundaries
  for retrieval/download changes.
- Real thesis and research materials are local user data. Do not commit them or
  include identifying excerpts in tests, logs, or Trellis task artifacts.

### End-to-End Academic Trial Convention

真实学术试运行必须把以下四类证据分开记录：`metadata-only`（仅题录）、
`abstract`（摘要）、`fulltext`（全文）和 `citation metadata`（可格式化题录）。
题录只能作为待核对线索，摘要只能支持摘要明确涉及的对象/方法/结果线索，
不能因为 `review` 或 `validate` 的词项匹配而升级为全文论断。

公开 live、OA 下载和 CNKI 桌面能力必须作为条件层单独报告：保存每个来源的
`source_statuses`、错误码和时间；HTTP 403、429、HTML 登录页、认证未完成或
连接器未运行都不能写成 `empty` 或“没有文献”。离线测试、架构验证和 smoke
门禁独立验收，避免外部服务波动掩盖仓库回归。

真实论文、PDF、`.humlit/` 和临时产物留在仓库外；Trellis 记录只保留脱敏的
输入角色、数量、命令、状态、失败分类和人工核验点。

## Review Checklist

- Does every public path still emit one valid JSON document?
- Are success, partial, warning, conditional, empty, and error states honest?
- Are all changed commands registered and covered by help/registry tests?
- Are generated artifacts and their source hashes consistent?
- Are Windows, Unicode paths, temporary files, and cleanup paths covered?
- Did the change affect offline smoke, capability contracts, Skill routing,
  release identity, or evaluation evidence?
- Are tests isolated from local `.humlit/` state and private research files?
- For browser authentication flows, does the test cover the transition from
  authenticated state to the originally requested action without a second
  login cycle?

## Forbidden Patterns

- Incidental stdout prints or non-JSON public output.
- Catch-all error conversion that masks programming defects.
- Network-dependent unit tests in the default suite.
- Manual edits to generated routing content without regeneration and checks.
- Committing cookies, API keys, downloaded papers, thesis files, `.humlit/`,
  or local virtual environments.
