# CNKI 失败分析（2026-08-24）

## 复现命令

```text
\.venv\Scripts\python.exe scripts/literature.py search "人工智能广告 品牌信任" --source cnki --field 主题 --year-from 2019 --limit 20 --pages 1
```

## 已观察到的过程

- 网络预检报告 CNKI 可访问，浏览器正常启动。
- 浏览器进入 CNKI 安全验证页。
- 日志先输出安全验证提示，随后输出：

  `已离开验证页 → https://kns.cnki.net/kns8s/search?captchaId=...`

- 临时输出文件最终包含一个 JSON 文档，核心内容为：

  - `status: warning`
  - `code: NO_RESULTS`
  - `count: 0`
  - `source_statuses.cnki.status: empty`

## 当前证据边界

这次不能据此断言该关键词在 CNKI 没有结果。现有代码在 `_show_browser_for_captcha` 中只检查 URL 是否离开 `/verify/`；带 `captchaId` 的 URL 可能仍是验证中间状态。搜索页随后等待结果表格超时，但代码仍继续解析，空解析最终被 CLI 归类为 `empty/NO_RESULTS`。

因此至少存在两个互相独立的问题：

1. **技能状态识别缺陷（高可能）**：验证中间页可能被过早判断为已完成。
2. **失败传播/解析缺陷（已可见）**：结果表格未确认可用时仍允许空列表进入 `NO_RESULTS` 分支。

此外还有一个执行层问题：当时终端等待窗口结束，没有及时展示最终 JSON；后续通过临时文件才找回结果。这不能掩盖技能层的分类问题。

## 需要区分的根因分类

| 分类 | 含义 | 当前证据 |
|---|---|---|
| 外部服务 | CNKI 安全验证、IP、机构权限或页面改版 | 已出现安全验证，但尚未单独证明 |
| 技能代码 | 把 `captchaId` 中间页当作验证成功 | 代码逻辑直接支持，待回归测试确认 |
| 查询/解析 | 页面正常但关键词无结果，或结果 DOM 改版 | 尚未排除 |
| 执行可观测性 | 长命令最终 JSON 未及时呈现 | 已确认 |

## 修复方向

- 不以“URL 离开 `/verify/`”单独作为成功条件。
- 将 `captchaId`、安全验证标记、验证码 DOM、搜索框、结果表格/明确空结果标记纳入状态识别。
- 结果表格等待失败且页面状态未知时，返回稳定错误（例如 `CNKI_SECURITY_GATE_UNRESOLVED` 或 `CNKI_RESULT_PAGE_UNAVAILABLE`），禁止降级为 `NO_RESULTS`。
- 保存 URL（脱敏）、页面标题、状态标记和等待阶段等诊断字段，不保存 cookie 或完整页面正文。

## 复现后的确认结论

宽查询 `人工智能` 在同一设备成功加载结果表格并解析出 20 条结果，说明 CNKI、浏览器和结果解析器并非整体不可用。

原组合查询的页面诊断同时出现：

- `抱歉，暂无数据，请稍后重试。`
- `拖动下方拼图完成验证`
- `安全验证`
- 结果表格数量为 0

因此旧版输出的 `NO_RESULTS` 不是可信空结果，而是安全验证/重试页被误分类。修复后同一查询不再继续解析空列表，而是在等待 180 秒后返回：

- `status: error`
- `code: CNKI_SECURITY_GATE_TIMEOUT`
- 脱敏后的 URL、标题、验证码状态和有限 body markers

这证明失败已从“隐藏为空结果”改为可见、可追踪的结构化错误；脚本没有绕过或自动完成验证码。

## 真实查询复现计划

使用不带年份和窄组合词的宽查询，逐次保存 stdout/stderr：

- `人工智能`
- `生成式人工智能`
- 一个已知存在的明确中文题名

只有当页面状态确认正常且来源状态为成功时，零结果才可作为真实空结果解释。

## Bug Analysis: CNKI 安全验证被误报为空结果

### 1. Root Cause Category

- **Category**: B / E / D — Cross-Layer Contract、Implicit Assumption、Test Coverage Gap
- **Specific Cause**: driver 层假设“URL 离开 `/verify/` 即验证成功”；搜索层假设“结果表格超时仍可继续解析”；CLI 层再把空列表统一包装成 `empty/NO_RESULTS`。三层各自看似可恢复，组合后却隐藏了真实失败。

### 2. Why Fixes Failed

1. 只观察浏览器已跳转：这是表面状态，未验证页面仍含拼图验证文案。
2. 只读取最终 `NO_RESULTS`：执行输出没有及时保留，且未核对 `source_statuses` 背后的页面证据。
3. 原测试只覆盖网络不可达和 driver 启动失败，没有覆盖挑战页到 CLI 空结果的跨层路径。

### 3. Prevention Mechanisms

| Priority | Mechanism | Specific Action | Status |
|---|---|---|---|
| P0 | Runtime | 显式识别 `captchaId`、拼图文案、验证码 DOM 和未知结果页 | DONE |
| P0 | Error contract | 使用稳定 CNKI 安全验证/结果页错误码并沿 CLI 传播 | DONE |
| P0 | Test coverage | 增加合成 driver 回归测试，覆盖超时不吞错和伪空结果 | DONE |
| P1 | Documentation | 更新 error-handling code-spec 和错误码参考 | DONE |
| P1 | Process | 真实 live 命令保存完整 stdout/stderr，不能只看等待窗口 | DONE |

### 4. Systematic Expansion

- **Similar Issues**: `_handle_captcha` 同时服务详情和下载流程；本次改为不吞错后，这些路径会诚实暴露安全验证失败，但后续仍应分别补详情/下载的结构化错误断言。
- **Design Improvement**: 页面状态应先分类，再决定继续解析、报告空结果或失败；不能由“缺少结果行”倒推出空结果。
- **Process Improvement**: 所有条件式 live 能力都要同时保存最终 JSON、stderr 和页面状态摘要。

### 5. Knowledge Capture

- [x] 更新 `.trellis/spec/backend/error-handling.md`
- [x] 更新 `references/error-codes.md`
- [x] 建立独立 Trellis 修复任务与真实复现记录
- [x] 补定向测试、全量测试、架构验证和离线 smoke
