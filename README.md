# HumLit Skills

学术文献检索与科研辅助 AI Skill。稳定公开源集合为 OpenAlex、Semantic Scholar、arXiv、NSSD、DBLP；CNKI 是需要桌面浏览器与合法机构权限的条件能力；BASE 仅保留为显式实验入口。通过 Crossref 条件性补全元数据，通过 Unpaywall（需真实邮箱）或 OpenAlex 解析 OA PDF。

HumLit Skills 是独立的人文社会科学研究 Skill，采用 MIT License。
许可证全文见 [`LICENSE`](LICENSE)。
版本亮点、安装说明、平台验证与已知限制见 [`RELEASE_NOTES.md`](RELEASE_NOTES.md)。

## Capability Contract

| 级别 | 能力 | 边界 |
|------|------|------|
| Stable offline | 引用/导出/导入、课题库统计、Word/PDF 元数据、论文格式、史料格式化、投稿规则检查 | 仅对输入中可观测信息负责 |
| Conditional live | 5 个稳定公开检索源、引文网络、DOI OA 下载 | 网络和上游服务可用；以实际 `source_statuses` 为准 |
| Conditional desktop | CNKI 搜索、全文、下载、学位论文与核心期刊筛选 | 浏览器 + 驱动 + 校园网/VPN/CARSI + 合法权限 |
| Agent-assisted | 综述/选题、引用建议、盲审、润色、质性解释、理论框架 | 脚本提供证据/信号，Agent 或研究者核对原文后完成 |
| Experimental | BASE | 仅 `--source base`；不进入默认聚合或 fallback |

完整输入前置条件、输出合同、失败模式和 smoke 证据见 [`evals/capability-contract.json`](evals/capability-contract.json)。

## Features

### 文献检索

`--source api --async-search` 并发检索 5 个稳定公开源，不启动 CNKI；`--source all` 仅在确需 CNKI 且桌面条件满足时使用，表示 CNKI + 5 个公开源。知网侧支持核心期刊、硕博论文、搜索字段和高级筛选。API 源支持作者、期刊、学科与分页过滤，单源可显式 `--enable-fallback`。所有多源结果返回 `source_statuses`，严格区分成功、空结果和上游错误；BASE 不参与聚合。

### 论文下载

知网 PDF/CAJ 批量下载支持搜索+下载一步完成，并明确记录实际格式和降级。`download --doi` 会流式下载合法 OA PDF（默认上限 100 MiB）、验证 `%PDF-` 签名并原子保存；DOI 文件名带稳定哈希，既有 PDF 幂等复用，不碰撞覆盖。`--link-only` 只返回链接。无 OA、登录页/HTML 响应、超限或网络失败都不会冒充已下载文件。本项目不绕过付费墙。

### 全文阅读

知网论文全文抓取与本地缓存。期刊论文使用 HTML 阅读提取，硕博论文通过 FlowPDF 三级加速提取（PDF.js API 直取 → 批量滚动 → 逐页补漏）。支持 .docx / .txt / .md 文件解析，自动处理中文编码（UTF-8 / GBK / GB18030）；DOCX 可提取正文、表格、脚注、尾注、批注、页眉页脚和文本框，并返回未观测部件边界。`pdf-meta` 命令可从 PDF 文件中提取元数据（标题、作者、DOI），并通过 Crossref 自动补全完整书目信息。

### 引用生成与导出

支持 GB/T 7714、APA、MLA、Chicago、BibTeX、RIS、脚注等引用格式。文献列表可导出为 BibTeX、RIS、Markdown、JSON、Excel。支持导入知网导出的 NoteExpress / Refworks / BibTeX 题录文件（含卷期页码完整解析）。搜索结果自带引用预览（`citation_preview`），cite 命令对知网论文自动补全卷期页码。

### 引文网络分析

基于 Semantic Scholar API 的前向/后向引用追踪。输入 DOI、arXiv ID 或论文 URL，获取双向引用链。不依赖知网，但依赖网络、上游覆盖和配额，不能保证任何环境或任意论文都可解析。

### 研究趋势分析

对搜索结果进行聚合统计：年份分布、高频关键词 Top 30、高被引论文 Top 10、数据源分布。用于选题分析和研究热点判断。

### Word 文档处理

Markdown 转学术格式 .docx（自动生成脚注和参考文献节）。支持在现有 .docx 上打补丁——插入引用、脚注、参考文献，保留原文档格式。

### 中文学位论文与人文社科写作

- `format-profile` / `format-check` / `format-apply`：生成学校/期刊格式 profile、检测论文格式、将 `.md/.docx` 套用为目标格式。
- `review-rubric` / `review-signals`：按教育部学位论文盲审四维 rubric 输出送审前自查信号。
- `polish-signals`：诊断中文学术表达中的超长句、口语化、主观表述、标点混用、重复与段落衔接问题。
- `journal-profile` / `journal-check`：检查 C刊/核心期刊投稿篇幅、摘要、关键词、参考文献要求，并扫描匿名送审泄露项（基金号、具名致谢、作者信息、自我指认机构）。

### 人文社科专用研究工具

- `cite-source-template` / `cite-source`：古籍、档案、方志、碑刻、报刊、家谱、口述等 7 类史料的脚注体与 GB/T 7714 著录。
- `qual-codebook-template` / `qual-code`：按编码簿对访谈/田野文本做关键词/正则命中标注，输出频次、段落覆盖和共现矩阵。
- `theory-catalog` / `theory-match`：浏览常用社科理论库，并按研究关键词匹配候选理论框架。

### Agent 驱动的工作流

以下功能必须由 Agent/研究者结合脚本证据完成，不能把脚本信号当作最终学术判断：

- **文献综述** — `review/write/validate/topics` 只生成有边界证据脚手架、初稿和词项级检查；Agent 核对全文后综合成稿
- **引用建议** — 识别论文中需要引用的句子，匹配文献并区分"必须引用"和"建议引用"
- **文献对比矩阵** — 多篇论文按研究问题、方法、发现、局限性等维度结构化对比
- **阅读笔记** — 按模板提取每篇论文的核心信息，多篇时附综合评述
- **学术表达优化** — `polish-signals` 只定位规则信号；Agent 保原意改写
- **质性解释** — `qual-code` 只做编码簿关键词/正则命中；开放编码、主题归纳和饱和度判断由研究者完成
- **理论框架** — `theory-match` 只按关键词重叠给候选，不代表理论适配度

## Usage

安装完成后，直接用自然语言指示 Agent：

```
"帮我搜索关于乡村振兴的核心期刊论文"
"搜20篇新闻传播的CSSCI论文并下载"
"搜几篇关于数字经济的硕士论文，抓取全文"
"读取我的论文，帮我写一段文献综述"
"把这些引用插入我的 Word 文档"
"这篇论文被哪些后续研究引用了"
"分析一下这批搜索结果的研究趋势"
"帮我对比这5篇论文的研究方法和发现"
"帮我优化这篇论文的学术表达"
"检查我的学位论文格式是否符合学校规范"
"把这篇论文排成学校要求的 Word 格式"
"模拟盲审看看这篇论文会不会被毙"
"检查这篇 C 刊投稿稿是否匿名泄露身份"
"帮我诊断这段论文文字哪里不够学术"
"把这些古籍和档案条目整理成脚注和参考文献"
"用这个访谈编码簿给访谈稿做质性编码"
"根据我的研究关键词推荐理论框架"
```

Agent 会自动识别意图并调用 HumLit Skills。

不会触发的典型任务：天气/新闻等通用网页搜索、代码文档、日常翻译、普通办公 Word/PDF、知网查重百分比、官方盲审或录用概率判断。

安装 Python 入口后也可直接调用：

```bash
humlit --version
humlit search "数字人文" --source api --async-search
```

## Installation

### 一句话安装（所有平台通用）

在 Agent 聊天中发送：

```
Fetch and follow instructions from https://raw.githubusercontent.com/ZhuXingcai/HumLit-Skills/main/setup.md
```

Agent 会自动识别平台、clone 到正确位置、安装依赖并验证环境。

适用于 Cursor、Codex、Claude Code、TRAE、Gemini CLI 及其他支持 Skill 的 Agent。

### 手动安装

<details>
<summary>展开手动安装步骤</summary>

```bash
# Cursor — Windows (PowerShell)
git clone https://github.com/ZhuXingcai/HumLit-Skills "$env:USERPROFILE\.cursor\skills\humlit-skills"

# Cursor — macOS / Linux
git clone https://github.com/ZhuXingcai/HumLit-Skills ~/.cursor/skills/humlit-skills

# Codex
git clone https://github.com/ZhuXingcai/HumLit-Skills ~/.codex/skills/humlit-skills

# Claude Code
git clone https://github.com/ZhuXingcai/HumLit-Skills ~/.claude/skills/humlit-skills

# TRAE
git clone https://github.com/ZhuXingcai/HumLit-Skills ~/.trae-cn/skills/humlit-skills

# Gemini CLI
gemini skills install https://github.com/ZhuXingcai/HumLit-Skills.git
# 或手动 clone:
# git clone https://github.com/ZhuXingcai/HumLit-Skills ~/.gemini/skills/humlit-skills

# 安装经过发布验证的固定依赖
<python> -m pip install -r <安装路径>/scripts/requirements.lock
<python> -m pip install --no-deps <安装路径>

# 同一份 checkout 可注册给多个客户端，不复制仓库
<python> <安装路径>/scripts/register_skill.py \
  --client codex --client claude --client trae
```

</details>

### 验证

开启新会话，对 Agent 说：

> "帮我搜索关于乡村振兴的核心期刊论文"

Agent 应自动识别 HumLit Skills 并执行。

发布/安装级 smoke：

```bash
# 无网络端到端产物链：题录库、综述脚手架、Word/PDF、格式/盲审信号、人文社科工具
<python> scripts/smoke_test.py --mode offline

# 真实上游探测；失败表示当前网络/上游不可用，不得改写成“无文献”
<python> scripts/smoke_test.py --mode live

# 生成可交给外部模型的路由评测请求；不会伪造独立评测结果
<python> scripts/evaluate_routing.py prepare \
  --output evals/results/routing-evaluation-request.json
```

## Requirements

| 要求 | 说明 |
|------|------|
| Python | 3.9+ |
| 浏览器 | Edge 或 Chrome（知网功能需要） |
| 网络 | 知网需校园网、机构 VPN，或学校支持的 CARSI/校外统一认证 |
| Selenium | 4.10+（自动管理 WebDriver，无需手动下载） |
| httpx | 同步 HTTP 可选（未安装时走标准库 urllib 兜底）；`--async-search` 并发检索必需 |
| pypdf | 5+（`pdf-meta` 必需，已进入锁文件） |

## Configuration

<details>
<summary>可选配置</summary>

在项目目录下创建 `.humlit/config.json`：

```json
{
  "request_interval": 3,
  "cache_ttl_days": 30,
  "mailto": "researcher@example.edu",
  "semantic_scholar_api_key": "",
  "save_dir": "./papers",
  "browser": "auto",
  "batch_window_size": 10
}
```

也可通过环境变量覆盖，详见 [配置说明](static/core/python-discovery.md#配置)。
Unpaywall 需要真实 `mailto`；Semantic Scholar 无 key 可用，但更容易触发
`429`，可通过 `SEMANTIC_SCHOLAR_API_KEY` 配置官方 key。

</details>

## Platform Notes

- **知网功能**需要本地桌面浏览器（Edge/Chrome）+ 合法机构访问权限（校园网、机构 VPN，或学校支持的 CARSI/校外统一认证），沙箱环境中需具备这些条件才可用
- **校外访问知网**可运行 `auth-cnki` 预热会话：默认打开 CNKI FSSO，也可用 `--auth-url` 传学校图书馆、VPN 或 CARSI 入口；`--institution` 可选，不传时由用户在浏览器中手动选择机构。登录成功后会复用 `.humlit/browser-profile` 和 cookies，通常同一项目/会话无需反复登录。
- **代理/梯子软件**（Clash、Mihomo、Surge、Quantumult X、系统 PAC 等）需要让 CNKI、CARSI 和学校认证域名直连。脚本会给浏览器注入 `proxy-bypass-list`，但 TUN/全局接管模式仍需在代理软件中配置 DIRECT 规则；可用 `--direct-domain` 或 `HUMLIT_CNKI_DIRECT_DOMAINS` 追加学校认证域名。
- **离线确定性功能**在安装锁定依赖后跨平台可用；**live API 功能**仍取决于网络和上游服务
- `check` 的 `connector_available` 只表示本地连接器就绪，不表示 live API 已探测成功；实际搜索以 `source_statuses` 为准
- `check --fix` 只返回 `recommended_actions`；不会执行 `pip install`，也不会修改 `.codex`/`.claude` 或用户级配置

## File Structure

<details>
<summary>展开目录结构</summary>

```
humlit-skills/
├── SKILL.md              ← Agent 指令（核心）
├── setup.md              ← 一句话自动安装脚本
├── README.md
├── LICENSE
├── .gitignore
├── references/           ← Agent 按需读取的参考文档
│   ├── core-journals.md
│   ├── error-codes.md
│   ├── environment.md
│   ├── api-search-best-practices.md
│   └── workflows.md
└── scripts/              ← Python 脚本
    ├── literature.py     ← 统一 CLI 入口
    ├── requirements.txt      ← 支持的依赖范围
    ├── requirements.lock     ← 发布验证使用的固定版本
    ├── cli/                 ← 命令层：参数解析、错误输出、惰性分发
    │   ├── registry.py
    │   ├── search_cmd.py
    │   ├── format_cmd.py
    │   ├── defense_cmd.py
    │   ├── source_cmd.py
    │   ├── polish_cmd.py
    │   ├── journal_cmd.py
    │   ├── qual_cmd.py
    │   └── theory_cmd.py
    └── core/                ← 逻辑层：纯业务逻辑与 CNKI 浏览器自动化
        ├── search.py
        ├── formatter.py
        ├── thesis_format/
        ├── blind_review/
        ├── source_citation.py
        ├── zh_polish.py
        ├── journal_fit.py
        ├── qual_coding.py
        ├── theory_catalog.py
        └── cnki/
```

</details>

## Update

在 skill 安装目录执行：

```bash
git pull
<python> -m pip install -r scripts/requirements.lock
```

`check` 命令会自动检测是否有新版本可用。

## Disclaimer

- 本工具仅供学术研究用途
- 使用知网功能需遵守 CNKI 服务条款，需具备合法访问权限（校园网/机构 VPN）
- 下载的论文版权归原作者和出版方所有
- 本项目不提供任何绕过付费墙的功能

## License

[MIT](LICENSE)
# Private
