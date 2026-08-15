# 检索、综述与写作工作流

## 文献检索

1. 提取中文和英文关键词。
2. 中文词用于 CNKI/NSSD，英文词用于公开 API。
3. 核心期刊任务读取 [`../core-journals.md`](../core-journals.md)。
4. 学位论文、核心体系和 CNKI 全文根据 `cnki_feasible` 决定。
5. 通用检索优先 `search --source api --async-search`。
6. 展示结果时注明实际成功和失败来源。

高级参数：

- 经典线索：`--sort citations`
- 最新进展：`--sort date`
- 优先核验：`--sort priority`
- 期刊：`--journal-filter`
- 作者：`--author-filter`
- 学科：`--field-of-study`
- 标题/摘要：`--field`
- 翻页：`--page`
- 单源降级：`--enable-fallback`

`--source all` 会额外启动 CNKI；BASE 只能显式 `--source base`。

数据源选择：

- 计算机科学：DBLP + OpenAlex。
- 综合学科：OpenAlex 或 Semantic Scholar。
- 预印本：arXiv，并标注未经同行评议。
- 中文：CNKI 或 NSSD。
- 机构仓储：BASE 仅作实验补检。

更多细节见 [`../api-search-best-practices.md`](../api-search-best-practices.md)。

## 预定义工作流

```bash
workflows --list
workflows --execute <id> --variables '<json>' --dry-run
```

Windows PowerShell 的 JSON 内部双引号写成 `""`：

```powershell
python scripts\literature.py workflows \
  --execute literature_review_classic \
  --variables '{""topic"":""deep learning""}' \
  --dry-run
```

## 写文献综述

1. 用户提供文稿时先 `read-paper`。
2. 提取 5-10 组关键词，多源检索用 `--append` 积累课题库。
3. 初筛后读取摘要或全文；仅题录只能作为待核对线索。
4. `review/write` 生成证据脚手架。
5. Agent 核对实际材料、比较分歧并重写。
6. `cite --style gbt7714` 生成参考文献。

`write --mode draft` 不是出版级综述；`validate` 的 strong/medium/weak
只是编号与词项重叠预检，不证明语义蕴含。

## 引用建议

1. `read-paper` 读取论文。
2. 识别需引用句子并提取关键词。
3. 按本次环境选择公开 API 或 CNKI。
4. 读取候选摘要/全文，定位具体支持段落。
5. 区分“必须引用”和“建议引用”。

引用建议没有自动串行的 `citation_suggestion` 命令。无法定位原文时必须标为
“待核对”，不得凭题名推荐。

## 改写论文并生成 Word（内容大改）

1. `read-paper` 读取用户论文。
2. 搜索并核验参考材料。
3. Agent 保持原意改写为 Markdown。
4. 用 `[^1]` 定义脚注，或维护 `## 参考文献`。
5. 运行：

```bash
write-docx draft.md --output 论文.docx
```

## 基于用户提供的 PDF 文献库

1. 扫描文件夹中的 `.pdf`。
2. 使用 Agent 的 PDF 工具读取，不使用 `read-paper`。
3. 提取标题、作者、核心观点和与研究问题的关联。
4. 按关联度报告筛选结果。
5. 根据用户需求生成综述、引用补丁或推荐列表。

超过 10 篇时先读每篇前 2-3 页判断相关性，只对相关篇目读取全文。
