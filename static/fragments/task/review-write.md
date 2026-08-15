# Task Fragment: 综述证据脚手架 / 有边界草稿 / 选题假设 / 词项校验

## 触发条件

课题文献库、综述证据脚手架、有边界草稿、选题假设或词项级证据校验。

## 排除条件

不读材料就要求出版级综述、真实研究空白或最终理论/方法判断。

## 前置条件

需要有效 session/project；超出题录的观点必须有摘要或全文证据。

## 决策流程

| 用户意图 | cnki_feasible: true | cnki_feasible: false |
|----------|--------------------|--------------------|
| 写综述 / 引用建议 | 读 [工作流](../../../references/workflows.md#写文献综述)，脚本先建证据底稿，Agent 核对原文后完成 | 同左，搜索用 `--source api` |
| 选题分析 / 研究问题 | `topics`（基于 session/project） | 同左 |
| 趋势/对比/笔记 | 见对应工作流 | 同左 |

## 命令

| 命令 | 用途 | 关键参数 |
|------|------|----------|
| `projects` | 列出课题文献库 | |
| `library` | 查看当前/指定课题文献库 | `--project` `--limit` |
| `write` | 基于文献库生成大纲/有边界初稿/单节脚手架 | `--project` `--topic` `--limit` `--mode outline/draft/section` `--section` `--format markdown/docx` `--output` `--with-citations` `--citation-style` `--validate` `--raw` |
| `validate` | 检查证据编号与词项重叠，不做语义蕴含判定 | `--project` `--topic` `--limit` `--file` |
| `topics` | 基于当前语料覆盖生成待验证选题假设 | `--project` `--topic` `--limit` |
| `review` | 生成可追溯综述材料 | `--project` `--topic` `--limit` `--output` `--auto-detail` `--detail-top-n` `--cluster` `--gaps` `--raw` |

## review vs write vs validate vs topics

- `write --project <课题名> --topic <主题>` 生成可追溯的大纲或**有边界初稿**；它按规则拼接当前题录/摘要，不理解全文论证，也不等于出版级综述。`--mode outline/draft/section` 控制脚手架形态，`--with-citations` 附当前元数据生成的参考文献。Agent 必须核对摘要/全文、综合分歧并重写成稿。
- `validate --project <课题名> --topic <主题> [--file draft.md]` 检查证据编号、缺摘要、风险文献与**词项重叠**，输出 `support_level`。`strong` 仅表示词项较匹配，不证明引用在语义上支撑论断；最终需读原文。
- `topics --project <课题名> --topic <方向>` 基于当前文献关键词聚类与摘要/关键词/年份元数据覆盖生成**选题假设**。聚类标签来自当前语料，不绑定预设学科；`claim_scope: corpus_coverage_signal` 和 `matched_count` 只描述当前库，不代表真实研究空白；必须扩展数据库、关键词和原文核验。
- `review` 基于当前 session 或 `--project` 文献库生成可追溯综述材料，输出包含检索证据、推荐精读文献、待核对原文、可能不相关/需剔除文献、主题线索、综述草稿和证据条目
- `review --cluster --gaps` 可按当前语料关键词组织聚类，并输出元数据/证据覆盖提示；脚本不使用领域固定模板推断研究空白，输出必须展示覆盖数量、总文献数和证据序号
- `review --auto-detail --detail-top-n N` 会在生成综述前自动挑选高相关、缺摘要的 CNKI 文献调用详情页补摘要，并写回同一 `--project` 文献库；适合用户要写综述但检索结果只有题录时使用

## 不得越界

- 仅题录时只能做筛选线索，不能概括论文观点；缺摘要条目必须保留 `metadata_only/待核对原文`。
- 研究空白、创新性、方法优劣、理论贡献和引用是否真正支撑论断，均不能由标题关键词规则最终判定。
- 引用建议是 Agent-assisted 流程，不是可自动执行的 `citation_suggestion` 工作流：Agent 需先识别具体论断，再搜索、读摘要/全文并逐条匹配。

## 输出合同

输出证据编号、语料范围、待核对项和风险；草稿、选题和 support level 均保持当前语料边界。

## 停止与降级

无会话时停止并先检索/导入；只有题录时退化为筛选线索，不概括论文观点。

## 附件

- [写文献综述](../../../references/workflows.md#写文献综述) — read-paper → 搜索 → 初筛 → 提炼 → cite
- [引用建议](../../../references/workflows.md#引用建议) — 识别需引用句子 → 搜索匹配 → 区分必须/建议
- [基于用户提供的 PDF 文献库](../../../references/workflows.md#基于用户提供的-pdf-文献库) — Glob 扫描 → 读取 → 筛选
- [文献对比矩阵](../../../references/workflows.md#文献对比矩阵) — 多篇论文按维度结构化对比
- [阅读笔记生成](../../../references/workflows.md#阅读笔记生成) — 按模板提取核心信息
- `write` 用于生成有边界初稿（docx 只是输出格式），`review` 用于分析材料，`validate` 用于词项级预检。若 CNKI 题录缺摘要，优先叠加 `review --auto-detail --detail-top-n 5`，再由 Agent 核对和成稿。
