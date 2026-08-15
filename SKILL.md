---
name: humlit-skills
description: >-
  Auditable academic research Skill for 文献/论文检索, 下载论文/OA 全文, 引用/
  BibTeX/RIS, 学术 Word/PDF, 论文格式, 文献综述证据脚手架, 有边界的盲审,
  古籍/档案等史料引用, 中文润色, C刊投稿自查, 质性编码底稿, and 理论框架候选.
  OpenAlex, Semantic Scholar, arXiv, NSSD, and DBLP are conditional live;
  CNKI additionally requires a desktop browser and lawful institutional access.
  Agent-assisted outputs require source-text verification and are not final
  academic judgments. Do not use for general web search, current news/weather,
  code documentation, general office documents, translation alone, plagiarism
  percentages, official decisions, paywall bypass, or automated semantic claims.
metadata:
  version: 1.0.2
  compatibility:
    platform: any
    python: ">=3.9"
    os: windows, macos, linux
---

# HumLit Skills

脚本负责 API、浏览器、解析和格式化；Agent/研究者负责理解意图、核对原文和学术判断。本文件只负责发现与分流，`manifest.yaml` 是路由唯一真源。

## 每次会话首次执行前

1. 读 `static/core/python-discovery.md`，解析 `<python>` 并完成无副作用自检。
2. 读 `static/core/output-rules.md`，遵守 JSON 状态、证据和人工判断边界。
3. 只读当前任务映射的 fragment；报错时再读相关 reference。

```bash
<python> -m pip install -r <skill_path>/scripts/requirements.lock
<python> <skill_path>/scripts/literature.py check --fix
```

`check --fix` 只给建议，不安装依赖、不改用户配置、不替用户授权。

<!-- BEGIN GENERATED ROUTES -->
## 意图路由（由 manifest.yaml 生成）

| 任务 | 触发信号 | 排除信号 | 命令 | 按需读取 |
|------|----------|----------|------|----------|
| `search` | 学术文献检索、研究趋势或引文追踪 | 通用网页、新闻、天气或代码文档搜索 | `search`<br>`batch-search`<br>`citations`<br>`trends` | `static/fragments/task/search.md` |
| `download` | OA 或合法 CNKI 全文、详情与下载 | 绕过付费墙、验证码或机构认证 | `download`<br>`batch-download`<br>`detail`<br>`auth-cnki`<br>`read-detail` | `static/fragments/task/download.md` |
| `review-write` | 课题库、综述证据、选题假设与证据校验 | 不核对原文的出版级综述或研究空白结论 | `projects`<br>`library`<br>`review`<br>`write`<br>`validate`<br>`topics` | `static/fragments/task/review-write.md` |
| `citation` | 参考文献、BibTeX、RIS 与题录导入导出 | 凭记忆补造缺失书目信息 | `cite`<br>`export`<br>`import` | `static/fragments/task/citation.md` |
| `docx` | 学术 Word、论文读取、PDF 元数据与文档补丁 | 合同、通知、简历等普通办公文档 | `read-paper`<br>`pdf-meta`<br>`write-docx`<br>`patch-docx` | `static/fragments/task/docx.md` |
| `format` | 论文格式 profile、检查与套用 | 捏造学校或期刊未提供的格式要求 | `format-profile`<br>`format-check`<br>`format-apply` | `static/fragments/task/format.md` |
| `blind-review` | 有边界的模拟盲审与送审信号 | 官方盲审、答辩或学术不端结论 | `review-rubric`<br>`review-signals` | `static/fragments/task/blind-review.md` |
| `source-citation` | 古籍、档案、方志、碑刻、报刊等史料引用 | 推断用户未提供的版本、卷次或档号 | `cite-source-template`<br>`cite-source` | `static/fragments/task/source-citation.md` |
| `polish` | 中文学术表达诊断与保原意润色 | 查重百分比、规避检测或自动改写承诺 | `polish-signals` | `static/fragments/task/polish.md` |
| `journal-fit` | 期刊硬性规则与匿名泄露自查 | 录用概率、期刊质量或编辑部决定 | `journal-profile`<br>`journal-check` | `static/fragments/task/journal-fit.md` |
| `qual-coding` | 编码簿关键词或正则命中与共现统计 | 把规则命中冒充语义开放编码或理论饱和 | `qual-codebook-template`<br>`qual-code` | `static/fragments/task/qual-coding.md` |
| `theory-framework` | 社会科学理论目录与关键词候选匹配 | 把关键词重叠分数当作理论适配结论 | `theory-catalog`<br>`theory-match` | `static/fragments/task/theory-framework.md` |
| `operations` | 环境自检、缓存清理或预定义工作流 | 把连接器存在解释为 live 服务已验证 | `check`<br>`clean-cache`<br>`workflows` | `static/core/python-discovery.md` |
<!-- END GENERATED ROUTES -->

## 全局边界

- 公开 API 是否可用只看本次 `source_statuses`；连接器存在不等于 live 成功。
- CNKI 只在本地浏览器、驱动、网络和合法权限满足时使用，不绕过认证或验证码。
- `review/write/validate/topics`、盲审、润色、质性解释和理论匹配都需要核对实际材料。
- 禁止凭记忆补造论文信息、把网络错误写成无结果、把规则信号写成最终学术结论。
- BASE 仅限用户显式指定 `--source base`，不进入默认聚合或 fallback。

## 按需参考

核心期刊、理论库、错误码、工作流、API 检索、环境和沙箱处理路径以 `manifest.yaml` 的 `on_demand` 为准；完整能力合同见 `evals/capability-contract.json`。
