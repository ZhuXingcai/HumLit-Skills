# Future：评估 Zotero Local API 只读适配

## Goal

在有真实工作流证据后，评估一个不写回、不同步、不破坏用户数据的 Zotero Local API 只读 MVP 是否比 BibTeX/RIS/CSL-JSON 标准互通显著减少人工步骤。

## Status and Trigger

当前仅作为未来规划，不进入实现。只有满足以下至少一项才激活：

- 手动导出/导入成为重复且高频的主要阻断点；
- 研究证据依赖 Zotero collection、标签、附件或批注，标准格式无法保留；
- 真实目标用户明确以现有 Zotero 库作为 HumLit 任务起点；
- 可定义可测量的成功指标，如任务准备时间或重复操作显著下降。

## Candidate MVP

- 连接 Zotero 桌面 Local API；
- 用户显式选择 collection；
- 只读导入题录、标签和可访问附件清单；
- 保留 Zotero item key、版本和来源映射，但不写回；
- Zotero 不可用时可靠降级到标准文件导入。

## Acceptance Criteria for Evaluation

- [ ] 完成至少 3 次真实 Zotero 起点任务观察。
- [ ] 量化标准格式互通与 Local API 只读的步骤/时间差异。
- [ ] 明确权限、隐私、版本兼容和错误矩阵。
- [ ] 只有证据显示收益显著时才创建实现任务。

## Out of Scope

- 双向同步、自动写回、删除、冲突合并和 Zotero 插件。
- 同时深度适配所有文献管理器。

