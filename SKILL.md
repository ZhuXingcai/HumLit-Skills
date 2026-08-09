---
name: humlit-skills
description: >-
  Search and manage scholarly metadata through OpenAlex, Semantic Scholar, arXiv,
  NSSD, DBLP, and conditionally CNKI; download verified open-access PDFs by DOI;
  format citations and research libraries; and process academic Word/PDF metadata.
  It also provides bounded, auditable support for Chinese theses and humanities/
  social-science work: 学位论文格式检测/套用, 模拟盲审信号, 古籍/档案/方志/碑刻/
  报刊史料引用, 中文学术表达诊断, C刊投稿硬性规则与匿名泄露检查, 编码簿关键词/
  正则命中统计, and 社会科学理论候选检索. Literature-review drafts, citation
  suggestions, blind-review conclusions, semantic qualitative coding, polishing,
  and theory fit are Agent-assisted and require source-text verification; scripts
  do not make final academic judgments. BASE is experimental and explicit opt-in.
  Use for 文献/论文检索, 下载论文/OA 全文, 引用/史料脚注/BibTeX/RIS, 学术 Word/docx,
  论文格式, 有边界的盲审模拟, 投稿自查/匿名化, 中文润色/学术表达优化, 质性编码底稿,
  理论框架候选, 引文网络, 研究趋势, 文献综述证据脚手架, 文献对比, or 阅读笔记.
  DO NOT USE for general web search, current news/weather, non-academic content,
  general office-document editing, code documentation lookup, translation alone,
  plagiarism-percentage detection, or official acceptance/degree decisions.
metadata:
  version: 1.0.0
  compatibility:
    platform: any
    python: ">=3.9"
    os: windows, macos, linux
---

# HumLit Skills

学术文献检索与科研辅助工具。脚本是"手"，Agent 是"脑"——脚本负责浏览器自动化、API 调用、解析与格式化；Agent 负责理解意图、筛选展示、决策与错误应对。

本 SKILL.md 是 **router**：只做意图分流，详细规则在按需加载的 fragment 中。**不要把所有内容一次性读进来**，按下表 Read 对应文件即可。

## 启动协议（每次会话首次调用脚本前）

1. **始终先读** `static/core/python-discovery.md`（解析可用 Python 命令、运行 `check --fix` 自检、配置项）。
2. **始终先读** `static/core/output-rules.md`（Agent/脚本分工、JSON status 约定、硬性规则、会话机制、结果展示）。
3. 这两份是常驻基础规则；其余按用户意图与报错按需加载。

```bash
# 首次：显式安装锁定依赖 + 自检（解析出的 <python> 见 python-discovery.md）
<python> -m pip install -r <skill_path>/scripts/requirements.lock
<python> <skill_path>/scripts/literature.py check --fix
```

> `<skill_path>` 是本 Skill 目录实际路径，Agent 自行解析；`<python>` 是 python-discovery.md 中解析出的解释器命令，不是固定字符串。
> `check --fix` 仅返回 `recommended_actions`，不安装依赖、不修改沙箱或用户配置；依赖安装必须是上方显式命令或用户批准的等价操作。

## 何时使用

- 用户需要**学术文献或题录**：搜索、筛选、去重、引文网络、趋势统计、课题文献库。
- 用户需要**合法开放获取全文**：已有 DOI，接受仅在确有 OA PDF 时下载；或具备合法 CNKI 桌面访问条件。
- 用户需要**确定性学术产物**：参考文献/BibTeX/RIS、史料脚注、Word 生成/补丁、PDF 元数据、格式 profile/检测/套用。
- 用户需要**有证据边界的 Agent 辅助**：综述证据脚手架、引用建议、盲审模拟、中文润色、开放式编码补充、理论框架判断。脚本先提供可审计信号，Agent 必须读实际材料完成判断。

## 何时不使用

- 通用网页搜索、天气/新闻/购物/旅行等非学术检索；代码/API 文档查找；无学术任务的翻译。
- 通用 Word/PDF 办公处理（合同、会议通知、简历等）；应使用对应文档工具。
- 要求知网查重百分比、规避检测、官方录用概率、正式盲审/答辩结论、学术不端定性。本 Skill 不具备这些能力。
- 要求脚本自动完成语义开放编码、扎根理论饱和度判断、理论适配结论、出版级综述或不经核对的引用推荐。这些只能作为 Agent-assisted 任务，不能冒充确定性结果。
- 需要绕过付费墙、验证码、机构认证或数据库服务条款的下载。

## 能力成熟度与前置条件

| 成熟度 | 能力 | 前置条件与边界 |
|--------|------|----------------|
| Stable offline | 引用/导出/导入、Word 与 PDF 元数据、格式引擎、史料格式化、规则型投稿检查、会话统计 | 安装锁定依赖；只对输入中可观测信息负责 |
| Conditional live | OpenAlex/S2/arXiv/NSSD/DBLP、引文网络、DOI OA 下载 | 网络和上游服务可用；以 `source_statuses`/实际下载结果为准，`check` 不冒充 live 探测 |
| Conditional desktop | CNKI 搜索、详情、全文、下载、学位论文/核心筛选 | 本地可见浏览器 + 驱动 + 校园网/VPN/CARSI + 用户合法权限 |
| Agent-assisted | 综述/选题/证据校验、盲审、润色、质性解释、理论框架 | 必须读用户材料/摘要/全文；输出注明证据范围、未知项和人工判断 |
| Experimental | BASE | 仅用户显式指定 `--source base`；不进入 `api/all` 或自动 fallback |

机器可读的完整输入、输出、失败模式和 smoke 证据见 `evals/capability-contract.json`。

## 意图 → fragment 映射（按需 Read）

把用户意图映射到一个或多个任务，Read 对应 fragment 后再执行（可多选）：

| 用户意图 | 命令组 | Read 这个 fragment |
|----------|--------|--------------------|
| 搜索/检索/查找文献、研究趋势、引文追踪/谁引用了 | search / batch-search / trends / citations | `static/fragments/task/search.md` |
| 下载论文/全文、批量下载、校外访问知网 | search --download / download / batch-download / read-detail / detail / auth-cnki | `static/fragments/task/download.md` |
| 综述证据脚手架、选题假设、词项级证据校验、课题文献库 | review / write / validate / topics / projects / library | `static/fragments/task/review-write.md` |
| 格式化参考文献、导出 BibTeX/RIS、导入题录 | cite / export / import | `static/fragments/task/citation.md` |
| 生成 Word、插引用/改写 .docx、读论文、PDF 元数据 | write-docx / patch-docx / read-paper / pdf-meta | `static/fragments/task/docx.md` |
| 检查论文格式是否合规、排成学校/期刊格式、生成格式规范文件 | format-profile / format-check / format-apply | `static/fragments/task/format.md` |
| 模拟盲审/投稿前自审/送审前自查/会不会被毙 | review-rubric / review-signals | `static/fragments/task/blind-review.md` |
| 古籍/档案/方志/碑刻/报刊等史料引用、史料脚注/参考文献 | cite-source / cite-source-template | `static/fragments/task/source-citation.md` |
| 中文润色/改写论文/学术表达优化/句子太口语化 | polish-signals | `static/fragments/task/polish.md` |
| 投C刊/核心期刊投稿前自查、字数/摘要/关键词达标、匿名送审泄露检测 | journal-profile / journal-check | `static/fragments/task/journal-fit.md` |
| 质性编码/访谈编码/扎根理论编码/给文本打标签/编码共现 | qual-codebook-template / qual-code | `static/fragments/task/qual-coding.md` |
| 理论框架/用什么理论/理论基础/有哪些相关理论/某理论是什么 | theory-catalog / theory-match | `static/fragments/task/theory-framework.md` |

每个 fragment 含该组的命令速查、参数详解、决策指南与相关工作流入口。

## on_demand 索引（仅在需要时 Read）

| 何时读 | 文件 |
|--------|------|
| 决策 `--core` 参数 / 判断核心期刊体系 | `references/core-journals.md` |
| 查阅常用社科理论库（人工版） | `references/theory-frameworks.md` |
| 脚本报错、需要错误码应对 | `references/error-codes.md` |
| 执行具体任务流程（综述、引用、优化、对比、笔记等） | `references/workflows.md` |
| 使用 API 源高级过滤、分页、检索优先级排序 | `references/api-search-best-practices.md` |
| 编码/超时/连接问题、平台兼容性、故障排查 | `references/environment.md` |
| 遇到 `sandbox_blocked`/驱动缺失/`needs_escalation`/Exit code 49 等权限问题 | `static/core/sandbox-escalation.md` |

## check 决策入口

- 同一会话首次调用脚本前运行一次 `check --fix`，缓存本地依赖与 CNKI 桌面能力；`--fix` 只生成手动建议，不产生环境写入副作用。
- `check.sources[*].connector_available: true` 只表示连接器代码/依赖就绪，**不表示上游 API 已实测可用**；live 结果只看实际命令的 `source_statuses`。
- `cnki_feasible: true` 只表示当前环境可尝试 CNKI；不代表其他网络源或所有命令都可用。`false` 时仅在 CNKI 是任务必需能力时按 `sandbox-escalation.md` 授权重试。
- 连续失败时重跑 `check` 确认环境，再查 `references/environment.md#故障排查`；不得把网络错误写成“无检索结果”。

> 详细规则见上述所引 fragment，不在本 router 内展开。
