# 修复 CNKI 安全验证状态与空结果误分类

## Goal

修复 CNKI 浏览器检索链路中可能将尚未解决的安全验证或异常页面误判为“验证完成”，并进一步错误输出 `NO_RESULTS` 的问题；同时保留足够的结构化诊断，使用户能够区分真实空结果、验证码/认证未完成、页面结构变化与本地执行超时。

## What I already know

- 真实命令曾进入 `/verify/` 安全验证页，随后跳到带 `captchaId` 的检索 URL。
- 当前 `_show_browser_for_captcha` 只要发现 URL 离开 `/verify/` 就立即判定验证成功，没有确认页面是否已进入可用检索状态。
- 同一次命令最终返回 `NO_RESULTS`，但该零结果尚不能证明 CNKI 真实无匹配文献。
- 长命令的最终 JSON 当时没有及时呈现，属于独立的执行可观测性问题。
- 不允许绕过验证码、机构认证、付费墙或 CNKI 的访问限制。

## Requirements

- 安全验证完成必须由页面状态共同确认，不能只依赖 URL 不含 `/verify/`。
- 含 `captchaId` 的中间 URL 或仍存在验证码元素的页面不得判为验证完成。
- 结果表格等待超时后，必须重新识别页面状态；安全验证未解决、页面结构异常和真实无结果必须返回不同的结构化错误/状态。
- CNKI 连接器失败必须沿 CLI `source_statuses` 传播，不能降级成 `empty` 或顶层 `NO_RESULTS`。
- 公共 CLI stdout 仍须保持单一 JSON 文档；诊断日志写 stderr，不泄露 cookie、凭据或敏感查询参数。
- 用脱敏的合成 driver/fixture 建立回归测试，默认测试套件不依赖实时 CNKI。

## Acceptance Criteria

- [ ] `/verify/` 跳转到 `/kns8s/search?captchaId=...` 时不会立即记录验证成功。
- [ ] 只有安全验证标记消失且页面达到可用状态时，验证码等待才成功返回。
- [ ] 验证未解决或超时时返回稳定结构化错误，不会变成 `NO_RESULTS`。
- [ ] 结果页缺少预期表格且无法确认真实空结果时返回页面/解析错误。
- [ ] 已确认的正常空结果仍保持 `empty`/`NO_RESULTS` 语义。
- [ ] 定向回归测试、完整 pytest、架构验证和离线 smoke 均有真实执行记录。
- [ ] 真实复现命令、最终 JSON、stderr 和根因分类记录在本任务 `research/` 中。

## Definition of Done

- 代码与回归测试完成，并通过适用质量门禁。
- CNKI 失败分类和诊断边界写入项目规范，避免同类问题再次被隐藏。
- 不提交真实论文、cookie、机构信息、完整页面内容或机器私有状态。
- 未经用户确认不 commit、不 push。

## Technical Approach

1. 先用宽关键词和明确存在的题名进行真实复现，捕获 stdout/stderr，并记录最终页面状态。
2. 提取或加强 CNKI 页面状态判定：安全门、中间挑战页、可用搜索页、结果页、明确空结果页和未知页面。
3. 让验证码等待与搜索结果等待复用该状态，未知或挑战状态以稳定错误码终止。
4. 先增加最小合成回归测试，再做局部修复；不扩大到登录流程重构或验证码自动处理。

## Decision (ADR-lite)

**Context**: 单一 URL 变化不能证明 CNKI 人机验证已经完成，而空解析结果会被 CLI 自动包装为 `NO_RESULTS`。

**Decision**: 采用“显式页面状态 + 结构化失败传播”的保守策略。只有页面证据充分时才返回成功或真实空结果；不确定状态宁可报告可恢复错误，也不伪装为空结果。

**Consequences**: 某些 CNKI 改版后会更早暴露为页面状态错误，需要更新选择器，但不会再把服务异常错误解释成研究空白。

## Out of Scope

- 自动绕过或破解验证码。
- 自动获取/伪造机构授权。
- 重写整个 CNKI 连接器或更换浏览器自动化框架。
- 在本任务中继续论文选题筛选或据此下学术结论。
- 未经用户确认执行 commit 或 push。

## Technical Notes

- 重点文件：`scripts/core/cnki/driver.py`、`scripts/core/cnki/search.py`、`scripts/cli/search_cmd.py`。
- 现有测试：`tests/test_cnki_auth_flow.py`、`tests/test_api_contract_fixtures.py`。
- 适用规范：backend directory structure、error handling、logging、quality guidelines，以及 shared cross-layer guide。
