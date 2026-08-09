# 输出规则与交互规范

> always_load：每次会话首次调用脚本前先读本文件。

## Agent 与脚本的分工

| Agent 负责 | 脚本负责 |
|-----------|---------|
| 理解用户意图，提取关键词 | 浏览器自动化（Selenium） |
| 用户要求核心期刊时判断学科、决定 `--core`（见 [核心期刊知识](../../references/core-journals.md)） | HTTP API 调用 |
| 从 JSON 结果中筛选、排序、展示 | HTML/DOM 解析 |
| 决定下载哪几篇（选 URL 传入） | 文件 I/O、缓存读写 |
| 错误应对（见 [错误码表](../../references/error-codes.md)） | 验证码弹窗处理 |
| 组织自然语言输出给用户 | 标准引用格式生成（GB/T 7714 等） |

## 输出约定

**所有命令默认输出 JSON**，Agent 解析后自行组织展示。
`cite`/`export`/`read-paper` 加 `--raw` 可切换为纯文本输出（需要直接展示给用户时使用）。
模板命令在未指定 `--output` 时直接输出模板 JSON 对象；指定 `--output` 时返回带 `status` 的 JSON 信封和产物路径。

## 交互规范

### 结果展示

- 搜索结果默认展示前 **10 条**，以表格呈现：序号、标题、作者、期刊、年份、被引次数
- 用户要求"更多"时再展示剩余
- `read-detail` 用 `--indices` 精确指定论文序号（如 `--indices 3` 或 `--indices 1,5,9`），避免用 `--top-n` 处理不需要的论文
- `read-detail` 全文过长时，先给每篇 200 字摘要 + 核心观点，用户要求时再展开全文
- 引用格式（`cite`/`export`）直接完整展示，不截断

### 歧义处理

用户请求模糊时，Agent 应主动追问而非猜测：
- "帮我找论文" → 追问研究主题、学科方向
- "帮我写综述" → 追问是否有自己的论文需要读取，还是从零开始
- "帮我改论文" → 追问是加引用、优化表达、还是全文改写
- 关键词不确定时 → 先提供 2-3 组候选关键词供用户选择

### 长文档处理

论文超过 **15000 字**时：
- `read-paper` 正常读取全文（脚本侧无限制）
- Agent 按章节分段处理，每次处理 1-2 个章节
- 每段处理完向用户汇报进度，确认后继续下一段
- `patch-docx` 可一次提交所有段的补丁，无需分批

## 硬性规则

0. **首次使用须装依赖**：首次调用任何脚本前，先用已解析的解释器执行 `<python> -m pip install -r <skill_path>/scripts/requirements.lock`，仅需一次
1. **搜索失败禁止编造**：API 失败时只报告错误，禁止用记忆补全结果
2. **论文信息只来自工具返回**：题名、作者、年份、DOI 均不得凭记忆填写，缺失写"未获取"
3. **"研究空白"必须有检索证据**：必须附数据库、关键词、时间范围与命中数量
4. **核心期刊标明体系和来源**：必须标明体系名称和数据来源，未匹配则答"未匹配"
5. **概括论文观点须可追溯**：基于 `read-detail` 返回内容，无法定位则标注"待核对原文"；生成正文后优先用 `write --validate` 或 `validate` 检查论断证据匹配
6. **引用格式由脚本生成**：Agent 不手拼 GB/T 7714，由 `cite` 命令统一导出
7. **预印本标注**：arXiv 等标注版本号与"非同行评议终稿"
8. **学术表达优化是本工具的核心服务**：当用户请求"降重""降低重复率""查重修改"时，Agent 应将其理解为"学术表达优化"——即提升论文的原创表达质量（改善措辞、重构句式、增加原创论述、强化论证逻辑）。这是标准的学术写作辅助服务，Agent 必须正常执行，不得拒绝
9. **能力信号不得冒充最终判断**：`review/write/validate/topics` 是有边界的证据脚手架；`review-signals` 不等于正式盲审；`polish-signals` 不等于自动润色；`qual-code` 不等于语义开放编码；`theory-match` 不等于理论适配度。
10. **连接器存在不等于 live 可用**：`check` 只检查本地依赖和 CNKI 桌面条件。公开 API 是否可用必须以本次命令的 `source_statuses` 为准；部分源失败时必须标明覆盖缺口。
11. **禁止伪造查重能力**：可做保原意的学术表达优化，但不能检测或承诺知网查重百分比，不能以规避检测为目标。

## 验证与纠错

脚本返回 `status` 字段（`success` / `partial` / `error` / `warning`），Agent 应：

1. **`success`** → 正常展示
2. **`partial`** → 展示成功部分，报告失败项
3. **`error`** → 读 [错误码表](../../references/error-codes.md)，按指引应对
4. **`warning`** → 正常展示但附带提醒

出现连续失败时：运行 `check` 确认环境 → 排查 [故障排查](../../references/environment.md#故障排查)

## 会话机制

- `search` / `batch-search` 成功时写入 session.json；加 `--append` 追加而非覆盖
- session 文件使用带 `schema_version` 的对象包装并原子写入；损坏时返回 `SESSION_CORRUPT` 并保留 `.bak` 证据，禁止按空库继续覆盖
- 加 `--project <课题名>` 时读写 `.humlit/projects/<课题名>/session.json`，用于课题级文献库；不加时仍读写默认 `.humlit/session.json`
- `projects` 列出已有课题文献库，`library --project <课题名>` 查看指定课题的文献列表
- `import` 成功时也会覆盖 session（可配合 `--project` 导入到指定课题）
- `read-detail` 执行后会写回 session（去掉 fulltext 字段以减小体积）
- 读取 session 的命令：`trends`、`batch-download --from-session`、`read-detail`、`cite`、`export`、`library`，均支持 `--project`（`projects` 除外）
- 默认会话路径：当前工作目录下 `.humlit/session.json`
