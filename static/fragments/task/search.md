# Task Fragment: 搜索 / 检索 / 趋势 / 引文网络

## 触发条件

搜索、检索、查找学术文献、研究趋势或引文追踪。

## 排除条件

通用网页/新闻搜索，或要求把元数据排序解释为学术质量。

## 前置条件

首次会话已完成 `check`；趋势依赖 session，引文网络依赖 Semantic Scholar。

## 决策流程

| 用户意图 | cnki_feasible: true | cnki_feasible: false |
|----------|--------------------|--------------------|
| 搜索（单关键词） | 中文学位/核心/CNKI 专属用 `search "词"`；其他用 `--source api --async-search` | `search "词" --source api --async-search` |
| 搜索（多关键词） | CNKI 专属用 `batch-search`；其他逐组 `search --source api --async-search --append` | 逐组 `search --source api --async-search --append` |
| 按作者/期刊搜 | `search --author / --journal` | 同上加 `--source`（DBLP 适合计算机领域作者搜索） |
| 核心期刊 | 加 `--core`（读 [core-journals.md](../../../references/core-journals.md)） | API 源无核心期刊筛选 |
| 引文网络 | `citations <DOI>` | 同左（不依赖知网） |
| 趋势分析 | `trends`（基于 session） | 同左 |

先读 `source_statuses`：网络/HTTP/schema 错误不能解释为“0 篇”；只有来源成功且结果为空时，才尝试同义词/英文词/放宽年份/换数据源。

## 命令

| 命令 | 用途 | 关键参数 |
|------|------|----------|
| `search "词"` | 单关键词搜索 | `--source` (cnki/openalex/semantic/arxiv/nssd/dblp/api/all；base 仅实验性显式调用) `--core` `--doc-type` `--field` `--author` `--journal` `--year-from` `--year-to` `--sort` `--pages` `--limit` `--cite-enrich` `--export` `--output` `--download` `--download-dir` `--download-top-n` `--download-file-format` `--download-fallback-format`（别名 `--fallback-format`）`--download-citation-style` `--download-report-output` `--append` `--project` `--author-filter` `--journal-filter` `--field-of-study` `--page` `--enable-fallback` `--async-search` |
| `batch-search "词1" "词2"` | 多关键词搜索 | `--query-file` `--core` `--doc-type` `--field` `--author` `--journal` `--year-from` `--year-to` `--sort` `--pages` `--export` `--output` `--append` `--project` |
| `citations "DOI/URL"` | 引文网络分析 | `--direction citing/cited/both` `--limit` |
| `trends` | 研究趋势分析（基于会话） | `--project` |

## 参数详解

`--core` 接收知网侧边栏精确选项名（逗号分隔）：`北大核心,CSSCI,AMI,WJCI,CSCD,EI`
Agent 负责将用户意图翻译为选项名，详见 [核心期刊知识](../../../references/core-journals.md)。
`--core` 使用规则：**仅在用户明确要求核心期刊时添加**。用户未提"核心""CSSCI""C刊"等词时不主动加，避免过滤掉有价值的非核心文献。

`--cite-enrich N`：仅知网搜索可用。搜索时点击前 N 条结果的"引用"按钮，读取弹窗中的 GB/T 7714 文本，写入 `gbt7714_raw` 并快速补全 `pages`。当用户要某篇论文的引用、要求页码、或需要准确 GB/T 引用时优先使用，例如：`search "论文题名" --source cnki --limit 3 --cite-enrich 3`。它比 `--enrich` 访问详情页更快，但会多做 N 次弹窗点击。

`--sort`：排序方式，可选 `relevance`（相关度，默认）/ `date`（时间）/ `citations`（被引次数）/ `priority`（检索优先级）。
- `citations` 和 `date` 排序在 OpenAlex 和 Semantic Scholar 中通过 API 参数实现，效率更高
- `priority` 基于摘要与元数据完整性、被引线索、开放获取和年份排序，只用于安排核验/精读顺序，**不代表学术质量**

`--author-filter`：作者过滤（仅 API 源），例如 `--author-filter "Hinton"`。OpenAlex 使用 API 级别过滤，Semantic Scholar 使用客户端过滤。

`--journal-filter`：期刊过滤（仅 API 源），例如 `--journal-filter "Nature"`。所有 API 源使用客户端过滤（大小写不敏感的子串匹配）。

`--field-of-study`：学科领域过滤（仅 API 源），例如 `--field-of-study "Computer Vision"`。OpenAlex 使用 API 级别过滤，Semantic Scholar 使用客户端过滤。

`--page`：分页参数（仅 API 源），默认第 1 页。支持 OpenAlex、Semantic Scholar、arXiv。每页结果单独缓存，适合浏览大量结果。
- arXiv 不支持按被引排序（`cited_by` 始终为 0），混合数据源时建议用 `relevance` 或 `priority`

数据源集合：
- `--source api`：OpenAlex、Semantic Scholar、arXiv、NSSD、DBLP；不启动 CNKI，推荐用于通用多源检索。
- `--source all`：CNKI + 上述 5 个稳定公开源；仅在确需同时覆盖 CNKI 且桌面条件满足时使用。
- `--source base`：实验入口，已知可能超时或受 IP 策略限制；不进入 `api/all` 和自动 fallback，不得宣传为稳定覆盖。
- `api/all` 聚合结果基于 DOI 精确匹配和标题标准化去重；默认 `relevance` 在全局 `--limit` 前按成功来源 round-robin，避免固定首源占满结果。用户显式选择 `citations/date/priority` 时服从该全局排序。`--async-search` 可并发公开源。

`--doc-type`：文献类型筛选，可选 `journal`（学术期刊）/ `master`（硕士论文）/ `doctor`（博士论文）/ `thesis`（全部学位论文）/ `conference`（会议论文）/ `newspaper`（报纸）。Agent 根据用户意图自动添加。

`--field`：搜索字段，可选 `主题`（默认）/ `篇名` / `关键词` / `摘要` / `全文` / `作者` / `来源`。指定后脚本自动切换高级搜索。

`--author` / `--journal`：传入后脚本自动切换知网高级搜索（多条件表单），无需 Agent 关心搜索模式。
Agent 的职责是从用户自然语言中提取作者/期刊名/文献类型/搜索字段，例如：
- "搜张三的论文" → `search "" --author 张三`（keyword 可为空）
- "找《中国社会科学》上关于乡村振兴的文章" → `search "乡村振兴" --journal 中国社会科学`
- "张三在北大核心上发的关于教育改革的论文" → `search "教育改革" --author 张三 --core 北大核心`
- "搜摘要里提到内容分析的硕士论文" → `search "内容分析" --doc-type master --field 摘要`
- "找博士论文中关于深度学习的" → `search "深度学习" --doc-type doctor`

## 检索优先级机制

所有搜索结果自动计算 `retrieval_priority_score`（0-100），用于安排检索和精读顺序，不代表学术质量。评分维度：
- **摘要完整性**（0-30）：>500 字得 30 分，>200 字得 20 分，有摘要得 10 分
- **DOI 存在**（20）：有 DOI 得 20 分
- **被引次数**（0-20）：对数归一化，高被引论文得分更高
- **关键词存在**（10）：有关键词得 10 分
- **开放获取**（10）：OA 论文得 10 分
- **基本题录完整性**（5）：题名、作者、年份、来源字段完整时加分，不按数据源身份加分
- **年份新近性**（0-10）：最近 5 年内，每年递减 2 分

使用场景：
- `--sort priority` 优先展示元数据较完整、便于核验的候选论文
- 分数只可作为检索和精读顺序参考
- 禁止据此断言论文“高质量”或“低质量”；学术价值仍需结合研究问题、方法、同行评议状态和原文判断

## 输出合同

返回 JSON 结果和 `source_statuses`；论文信息只来自实际响应，priority 仅用于安排核验顺序。

## 停止与降级

所有来源错误时停止并报告；部分来源失败时标明覆盖缺口；只有成功空结果才能调整关键词或过滤条件。

## 附件

- [文献检索](../../../references/workflows.md#文献检索) — 关键词提取、数据源选择、核心期刊判断
- [引文网络分析](../../../references/workflows.md#引文网络分析) — citations 命令，不依赖知网
- [研究趋势分析](../../../references/workflows.md#研究趋势分析) — trends 命令，基于会话数据
- API 源高级过滤/分页/优先级排序详见 [API 源检索最佳实践](../../../references/api-search-best-practices.md)
