# 结果展示、歧义与会话

只在需要组织长结果、澄清模糊任务或读写课题库时读取。

## 结果展示

- 搜索结果默认展示前 10 条：序号、标题、作者、期刊、年份、被引次数。
- 用户要求更多时再展示剩余结果。
- `read-detail` 优先用 `--indices` 精确选择论文。
- 全文过长时先给摘要和核心观点，用户要求时再展开。
- `cite` 和 `export` 的引用结果完整展示，不截断。

## 歧义处理

- “帮我找论文”：先确认研究主题和学科方向。
- “帮我写综述”：确认是读取已有材料，还是从检索开始。
- “帮我改论文”：确认是引用、表达、格式还是内容结构。
- 关键词不确定时，先给 2-3 组候选让用户选择。
- 多意图任务先执行建立后续前置条件的命令，并说明顺序。

## 长文档

论文超过 15000 字时：

1. `read-paper` 正常读取全文。
2. Agent 每次处理 1-2 个章节。
3. 每段处理后汇报进度再继续。
4. `patch-docx` 可一次提交全部已确认补丁。

## 会话与课题库

- `search` / `batch-search` 成功后写入 `.humlit/session.json`。
- `--append` 追加结果；默认搜索会覆盖当前会话。
- `--project <name>` 使用 `.humlit/projects/<name>/session.json`。
- `projects` 列出课题库，`library --project <name>` 查看内容。
- `import` 可将题录写入默认会话或指定课题。
- `read-detail` 补全后写回会话，但移除大体积全文字段。
- `trends`、`batch-download`、`read-detail`、`cite`、`export` 和 `library`
  消费已保存会话。
- session 使用版本化对象和原子写入；损坏时返回 `SESSION_CORRUPT` 并保留备份，
  禁止按空库覆盖。
