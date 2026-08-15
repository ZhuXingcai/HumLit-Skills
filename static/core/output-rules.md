# 输出与证据规则

> always_load：每次会话首次调用脚本前读取一次。

## 分工与输出

- Agent 负责意图、参数、筛选、解释和错误应对。
- 脚本负责 API、浏览器、解析、文件 I/O 和确定性格式。
- 默认 JSON 写 stdout；日志和诊断写 stderr。
- `--raw` 只在命令明确支持且需要直接展示文本时使用。
- 模板指定 `--output` 后必须返回状态和产物路径。

状态处理：

- `success`：展示结果并保留来源与证据范围。
- `partial`：使用成功部分，明确失败来源。
- `warning`：产物可用，但必须展示限制。
- `error`：按 `code` 和错误码表处理，不编造结果。
- `empty`：只表示请求成功但无匹配，不得与网络或解析错误混淆。

## 硬性规则

1. 搜索失败禁止用模型记忆补全论文。
2. 题名、作者、年份、DOI 只来自工具；缺失写“未获取”。
3. 研究空白必须附数据库、关键词、时间范围和命中数。
4. 核心期刊必须注明体系和来源。
5. 论文观点必须可追溯；无法定位时标“待核对原文”。
6. 引用格式由脚本生成，不由 Agent 手拼。
7. arXiv 等预印本须标明未同行评议。
8. 学术表达优化应保原意，不承诺或规避查重百分比。
9. 综述、盲审、润色、质性和理论信号不得冒充最终判断。
10. 连接器存在不等于 live 可用；以本次 `source_statuses` 为准。
11. session 损坏必须停止写入并保留备份，禁止按空库覆盖。

连续失败时重新运行 `check`，再读
[`../../references/error-codes.md`](../../references/error-codes.md) 和
[`../../references/environment.md`](../../references/environment.md)。
结果展示、歧义、长文档和 session 细节见
[`../../references/interaction-and-sessions.md`](../../references/interaction-and-sessions.md)。
