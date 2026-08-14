# HumLit Skills

[![CI](https://github.com/ZhuXingcai/HumLit-Skills/actions/workflows/ci.yml/badge.svg)](https://github.com/ZhuXingcai/HumLit-Skills/actions/workflows/ci.yml)
[![Platform Adversarial](https://github.com/ZhuXingcai/HumLit-Skills/actions/workflows/platform-adversarial.yml/badge.svg)](https://github.com/ZhuXingcai/HumLit-Skills/actions/workflows/platform-adversarial.yml)
[![Latest Release](https://img.shields.io/github/v/release/ZhuXingcai/HumLit-Skills)](https://github.com/ZhuXingcai/HumLit-Skills/releases/latest)
[![Python](https://img.shields.io/badge/Python-3.9%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/github/license/ZhuXingcai/HumLit-Skills)](LICENSE)

面向人文社会科学研究的可审计 AI Skill：提供多源学术检索、合法开放获取全文、引用与学术文档处理，以及有明确证据边界的研究辅助。

HumLit Skills 把确定性程序能力与语义判断分开：

- **脚本负责** API 调用、浏览器自动化、文件解析、格式检查和结构化输出。
- **Agent 与研究者负责** 理解研究问题、核对原文、解释证据并作出学术判断。
- **所有联网结果都区分成功、空结果和错误**，不把限流、断网或解析失败伪装成“没有文献”。

> HumLit Skills 不是论文代写器、查重工具或官方学术评审系统，也不会绕过付费墙、验证码、机构认证或数据库服务条款。

## 目录

- [项目定位](#项目定位)
- [何时使用](#何时使用)
- [能力地图](#能力地图)
- [数据源](#数据源)
- [快速开始](#快速开始)
- [安装](#安装)
- [常用任务](#常用任务)
- [命令索引](#命令索引)
- [输出合同](#输出合同)
- [配置](#配置)
- [CNKI 桌面能力](#cnki-桌面能力)
- [项目架构](#项目架构)
- [质量与验证](#质量与验证)
- [开发与测试](#开发与测试)
- [更新](#更新)
- [限制与责任边界](#限制与责任边界)

## 项目定位

传统研究工具往往只覆盖检索、引用或文档处理中的一个环节。HumLit Skills 将这些能力组织为一个 Agent 可按需调用的研究工作流，同时对每类能力标注成熟度、前置条件和不可替代的人工判断。

项目遵循四项原则：

1. **可审计**：机器输出保留数据源、状态、错误和证据范围。
2. **不夸大**：规则命中、关键词重叠和元数据评分不等于学术质量或理论适配度。
3. **本地优先**：课题库、缓存和中间产物默认保存在本地 `.humlit/`。
4. **合法访问**：只下载已确认的 OA PDF，CNKI 仅在用户具有合法机构权限时工作。

核心入口：

| 文件 | 作用 |
|------|------|
| [`SKILL.md`](SKILL.md) | Agent 路由器，定义何时使用、何时不使用以及按需加载规则 |
| [`manifest.yaml`](manifest.yaml) | 任务与 fragment 的机器可读映射 |
| [`scripts/literature.py`](scripts/literature.py) | Python CLI 入口 |
| [`evals/capability-contract.json`](evals/capability-contract.json) | 能力前置条件、输出、失败模式和 smoke 证据 |
| [`references/error-codes.md`](references/error-codes.md) | 结构化错误码与应对方式 |

## 何时使用

### 适合

- 搜索、筛选、去重和管理学术文献或题录。
- 查询前向/后向引文，统计年份、关键词和数据源分布。
- 通过 DOI 查找并下载签名验证通过的合法 OA PDF。
- 生成 GB/T 7714、APA、MLA、Chicago、BibTeX、RIS 或脚注格式。
- 读取学术 `.docx/.txt/.md`，提取 PDF 元数据，生成或修补学术 Word。
- 检查学位论文格式、送审信号、C刊投稿硬性规则和匿名泄露。
- 整理古籍、档案、方志、碑刻、报刊、家谱与口述史料引用。
- 生成质性编码簿命中底稿或社会科学理论候选列表。
- 为文献综述、选题、润色和理论框架判断建立可追溯的证据脚手架。

### 不适合

- 天气、新闻、购物、旅行等通用网页搜索。
- 代码/API 文档查询、普通翻译或非学术办公文档处理。
- 知网查重百分比、规避检测、官方录用概率、正式盲审或答辩结论。
- 不读取原文就自动给出出版级综述、引用推荐、开放编码或理论适配结论。
- 绕过付费墙、验证码、机构登录或数据库服务条款。

## 能力地图

| 成熟度 | 能力 | 必要条件与边界 |
|--------|------|----------------|
| **Stable offline** | 引用、导入导出、课题库、Word/PDF 元数据、论文格式、史料引用、规则型投稿检查 | 安装锁定依赖；只对输入中可观测内容负责 |
| **Conditional live** | OpenAlex、Semantic Scholar、arXiv、NSSD、DBLP、引文网络、DOI OA 下载 | 依赖网络、上游服务和配额；以实际 `source_statuses` 为准 |
| **Conditional desktop** | CNKI 搜索、详情、全文、下载、学位论文和核心期刊筛选 | 本地 Edge/Chrome、Selenium Manager、校园网/VPN/CARSI 和合法权限 |
| **Agent-assisted** | 综述、选题、引用建议、盲审解释、润色、质性解释、理论框架 | 必须核对用户材料、摘要或全文；输出需标注未知项 |
| **Experimental** | BASE | 仅显式 `--source base`；不进入默认聚合或自动 fallback |

完整合同见 [`evals/capability-contract.json`](evals/capability-contract.json)。

## 数据源

| 数据源 | 适用场景 | 主要限制 |
|--------|----------|----------|
| **OpenAlex** | 综合文献、高被引线索、跨学科检索、OA 解析 | 元数据和全文覆盖因领域而异 |
| **Semantic Scholar** | 计算机科学、生物医学、引文网络 | 匿名访问容易触发 `429`，建议配置 API key |
| **arXiv** | 物理、数学、计算机科学的最新预印本 | 不代表已同行评审，缺少统一引文计数 |
| **NSSD** | 中文社会科学文献 | 元数据字段和响应速度有限 |
| **DBLP** | 计算机科学会议、作者追踪 | 通常没有摘要和引文计数 |
| **CNKI** | 中文期刊、学位论文、核心期刊筛选与合法全文访问 | 需要桌面浏览器及有效机构权限 |
| **BASE** | 显式实验性的机构知识库补检 | 已知存在超时、访问限制和异构元数据问题 |

数据源选择：

- `--source api --async-search`：并发检索五个维护中的公开源，不启动 CNKI。
- `--source all --async-search`：公开源加 CNKI，仅在桌面条件满足且任务确需 CNKI 时使用。
- `--source openalex|semantic|arxiv|nssd|dblp`：显式使用单一公开源。
- `--source cnki`：使用 CNKI 桌面浏览器能力。
- `--source base`：仅在用户明确接受实验性结果时使用。

## 快速开始

### 让 Agent 自动安装

在 Cursor、Codex、Claude Code、TRAE、Gemini CLI 或其他支持 Skill 的 Agent 中发送：

```text
Fetch and follow instructions from https://raw.githubusercontent.com/ZhuXingcai/HumLit-Skills/main/setup.md
```

安装完成后开启新会话，直接说：

```text
帮我搜索 2020 年以来关于数字人文的中英文文献，并按研究主题整理。
```

### 命令行安装与首次检索

```bash
git clone https://github.com/ZhuXingcai/HumLit-Skills.git
cd HumLit-Skills

python -m pip install -r scripts/requirements.lock
python -m pip install --no-deps .

humlit --version
humlit check --fix
humlit search "数字人文" --source api --async-search --limit 20
```

`check --fix` 的名称表示“给出修复建议”，不会执行 `pip install`、下载 Driver、修改 Agent 配置或更改沙箱权限。

## 安装

### 环境要求

| 项目 | 要求 |
|------|------|
| Python | 3.9 或更高版本 |
| 操作系统 | Windows、macOS、Linux |
| 公开 API | 可访问相应上游服务的网络 |
| CNKI | 本地 Edge/Chrome、合法机构权限和可交互桌面 |
| Python 依赖 | 推荐使用 [`scripts/requirements.lock`](scripts/requirements.lock) 的固定版本 |

### 各 Agent 的默认安装位置

```bash
# Cursor - macOS/Linux
git clone https://github.com/ZhuXingcai/HumLit-Skills.git \
  ~/.cursor/skills/humlit-skills

# Codex
git clone https://github.com/ZhuXingcai/HumLit-Skills.git \
  ~/.codex/skills/humlit-skills

# Claude Code
git clone https://github.com/ZhuXingcai/HumLit-Skills.git \
  ~/.claude/skills/humlit-skills

# TRAE
git clone https://github.com/ZhuXingcai/HumLit-Skills.git \
  ~/.trae-cn/skills/humlit-skills

# Gemini CLI
gemini skills install https://github.com/ZhuXingcai/HumLit-Skills.git
```

Cursor Windows PowerShell：

```powershell
git clone https://github.com/ZhuXingcai/HumLit-Skills.git `
  "$env:USERPROFILE\.cursor\skills\humlit-skills"
```

安装 Python 入口：

```bash
python -m pip install -r <安装路径>/scripts/requirements.lock
python -m pip install --no-deps <安装路径>
```

同一份 checkout 可以注册给多个 Agent，不需要复制仓库：

```bash
python <安装路径>/scripts/register_skill.py \
  --source <安装路径> \
  --client codex --client claude --client trae
```

安装器不会覆盖已有的不同目标，也不会在存在未提交改动时静默更新。

## 常用任务

### 1. 多源公开检索

```bash
humlit search "digital humanities" \
  --source api \
  --async-search \
  --year-from 2020 \
  --sort priority \
  --limit 30
```

`priority` 只表示元数据完整性和影响力线索的检索优先级，不是论文质量评分。

### 2. CNKI 搜索

```bash
humlit search "乡村振兴" \
  --source cnki \
  --core "北大核心,CSSCI" \
  --doc-type journal \
  --year-from 2020 \
  --limit 20
```

校外访问可先建立机构会话：

```bash
humlit auth-cnki --wait-seconds 240 --keep-browser
```

登录、扫码、短信和滑块必须由用户本人完成，HumLit Skills 不绕过这些步骤。

### 3. 下载合法 OA PDF

```bash
humlit download --doi "10.1038/sdata.2016.18" --dir ./papers
humlit download --doi "10.1038/sdata.2016.18" --link-only
```

下载过程会流式写入临时文件、限制默认大小为 100 MiB、检查 `%PDF-` 签名并原子替换目标文件。HTML 登录页或错误响应不会被保存成 PDF。

### 4. 查询引文网络

```bash
humlit citations "10.1038/sdata.2016.18" --direction both --limit 20
```

引文网络依赖 Semantic Scholar 的覆盖与配额。`API_RATE_LIMIT` 是上游限流，不代表论文没有引用。

### 5. 建立课题库与综述证据

```bash
humlit search "平台劳动" \
  --source api \
  --async-search \
  --project platform-labor \
  --limit 30

humlit review \
  --project platform-labor \
  --cluster \
  --gaps \
  --output review-evidence.md

humlit write \
  --project platform-labor \
  --mode outline \
  --with-citations \
  --validate \
  --output review-outline.md
```

`review`、`write`、`topics` 和 `validate` 生成的是证据脚手架与待核验假设，不替代研究者阅读全文后的综合判断。

### 6. 引用与题录

```bash
humlit cite --style gbt7714 --raw
humlit export --format bibtex --output references.bib
humlit export --format excel --output literature.xlsx
humlit import exported-records.txt --project platform-labor
```

支持 GB/T 7714、APA、MLA、Chicago、BibTeX、RIS、脚注、Markdown、JSON 和 Excel。

### 7. 学术 Word 与 PDF

```bash
humlit read-paper thesis.docx --output thesis.txt
humlit pdf-meta article.pdf
humlit write-docx draft.md --output draft.docx
humlit patch-docx thesis.docx --patch patch.json --output thesis-patched.docx
```

DOCX 解析覆盖正文、表格、脚注、尾注、批注、页眉页脚和文本框，并在输出中说明未观测到的 OOXML 部件。

### 8. 学位论文格式与送审信号

```bash
humlit format-profile --template --output university-profile.json
humlit format-check thesis.docx --profile university-profile.json
humlit format-apply thesis.docx \
  --profile university-profile.json \
  --output thesis-formatted.docx

humlit review-signals thesis.docx --raw
```

格式问题与送审信号是确定性检查结果，不是官方盲审结论。

### 9. 人文社科专用工具

```bash
# 史料引用
humlit cite-source historical-sources.json --style both

# 中文学术表达诊断
humlit polish-signals thesis.docx --max-sentence 80

# C刊投稿与匿名泄露自查
humlit journal-check manuscript.docx --profile journal-profile.json

# 编码簿关键词/正则命中
humlit qual-code interviews.docx --codebook codebook.json

# 理论候选检索
humlit theory-match \
  --keywords "信任,社会资本,弱关系" \
  --discipline 社会学 \
  --top 8
```

`qual-code` 不执行语义开放编码，`theory-match` 的得分也不代表理论适配度。

## 命令索引

HumLit Skills 当前提供 39 个 CLI 命令：

| 命令组 | 命令 | 用途 |
|--------|------|------|
| 检索与分析 | `search`, `batch-search`, `citations`, `trends` | 单次/批量检索、引文网络、趋势统计 |
| 下载与 CNKI | `download`, `batch-download`, `detail`, `auth-cnki`, `read-detail` | OA/CNKI 下载、详情、全文和机构认证 |
| 课题与综述 | `projects`, `library`, `review`, `write`, `validate`, `topics` | 课题库、综述证据、写作与校验 |
| 引用与题录 | `cite`, `export`, `import` | 引用生成、导入导出 |
| 文档 | `read-paper`, `pdf-meta`, `write-docx`, `patch-docx` | 论文读取、PDF 元数据和 Word 处理 |
| 环境与流程 | `check`, `clean-cache`, `workflows` | 环境检查、缓存清理和预定义工作流 |
| 论文格式 | `format-profile`, `format-check`, `format-apply` | 格式规范建模、检查和套用 |
| 盲审信号 | `review-rubric`, `review-signals` | rubric 与送审前信号 |
| 史料引用 | `cite-source-template`, `cite-source` | 七类史料字段模板与引用 |
| 学术表达 | `polish-signals` | 规则型中文表达诊断 |
| 投稿自查 | `journal-profile`, `journal-check` | 期刊硬性要求和匿名泄露 |
| 质性编码 | `qual-codebook-template`, `qual-code` | 编码簿和确定性命中统计 |
| 理论框架 | `theory-catalog`, `theory-match` | 理论浏览与关键词候选匹配 |

查看总帮助或某个命令的完整参数：

```bash
humlit --help
humlit search --help
humlit workflows --list
```

## 输出合同

CLI 默认将机器可读 JSON 写到 `stdout`，日志、进度和诊断写到 `stderr`。Agent 不应通过截取日志文本判断成功与否。

顶层状态：

| `status` | 含义 | Agent 应对 |
|----------|------|------------|
| `success` | 操作成功完成 | 使用结果，同时保留来源与证据范围 |
| `empty` | 请求成功，但没有匹配记录 | 调整关键词、年份、来源或筛选条件 |
| `partial` | 部分来源或步骤成功 | 只使用成功部分，并明确列出失败项 |
| `warning` | 产物可用，但存在重要限制 | 展示 warning，不应静默忽略 |
| `error` | 操作未完成 | 读取 `code`、`message` 和来源状态后处理 |

多源检索必须读取 `source_statuses`：

- `success`：该来源返回了可解析结果。
- `empty`：该来源成功完成查询但没有匹配项。
- `error`：网络、HTTP、限流、解析或服务错误。

`SOURCE_UNAVAILABLE`、`API_RATE_LIMIT` 和 `SOURCE_SCHEMA_ERROR` 都不能解释为“没有文献”。完整错误码见 [`references/error-codes.md`](references/error-codes.md)。

## 配置

项目级配置保存在 `.humlit/config.json`：

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

环境变量优先于配置文件：

| 环境变量 | 配置字段 | 用途 |
|----------|----------|------|
| `HUMLIT_REQUEST_INTERVAL` | `request_interval` | CNKI 请求间隔 |
| `HUMLIT_CACHE_TTL_DAYS` | `cache_ttl_days` | API/全文缓存有效期 |
| `HUMLIT_MAILTO` | `mailto` | Unpaywall/OpenAlex polite access 邮箱 |
| `SEMANTIC_SCHOLAR_API_KEY` | `semantic_scholar_api_key` | Semantic Scholar API key |
| `HUMLIT_SAVE_DIR` | `save_dir` | 默认下载目录 |
| `HUMLIT_BROWSER` | `browser` | `auto`、`edge` 或 `chrome` |
| `HUMLIT_BATCH_WINDOW_SIZE` | `batch_window_size` | 批量下载窗口大小 |
| `HUMLIT_DRIVER_PATH` | - | 显式指定 `msedgedriver`/`chromedriver` |
| `HUMLIT_CNKI_DIRECT_DOMAINS` | - | 追加 CNKI/学校认证直连域名 |
| `HUMLIT_SKIP_NETWORK_CHECK` | - | 跳过 CNKI 网络预检，常用于授权重试 |

运行时数据默认位于项目目录的 `.humlit/`，该目录已被 Git 忽略：

```text
.humlit/
├── config.json
├── session.json
├── projects/
├── fulltext/
├── browser-profile/
└── cookies.json
```

缓存写入使用临时文件、`fsync` 和原子替换。损坏 JSON 会保留为 `*.corrupt-<timestamp>`，不会静默清空用户数据。

## CNKI 桌面能力

CNKI 功能需要：

1. 本地可见的 Edge 或 Chrome。
2. 已安装锁定的 Selenium 依赖。
3. 校园网、机构 VPN、CARSI 或学校提供的校外统一认证。
4. 用户对相应内容具有合法访问权限。

### 首次运行的 Driver 行为

无需预先手动下载 ChromeDriver 或 EdgeDriver。HumLit Skills 使用 Selenium Manager：

- `check --fix` 只确认供应机制是否就绪，不下载 Driver。
- 第一次真实 CNKI 操作才按浏览器版本获取匹配 Driver。
- 已缓存或通过 `HUMLIT_DRIVER_PATH` 指定时直接复用。
- 无法供应时返回结构化 `DRIVER_MISSING`，而不是把问题伪装成搜索空结果。

`check` 中的关键字段：

| 字段 | 含义 |
|------|------|
| `driver_mode: cached_or_explicit` | 已找到缓存或显式 Driver |
| `driver_mode: selenium_manager_on_demand` | 首次真实操作时按需供应 |
| `cnki_feasible: true` | 本地前置条件允许尝试，不代表搜索已经执行 |
| `runtime_verified: null` | 静态自检没有冒充真实桌面检索 |

### 校外认证与代理

```bash
# CNKI FSSO，用户在浏览器中选择学校
humlit auth-cnki --wait-seconds 240 --keep-browser

# 尝试按机构名称选择
humlit auth-cnki \
  --institution "示例大学" \
  --wait-seconds 240

# 使用学校图书馆或 VPN 提供的入口
humlit auth-cnki \
  --auth-url "https://library.example.edu/cnki" \
  --direct-domain idp.example.edu
```

使用 Clash、Mihomo、Surge、Quantumult X、系统 PAC 或 TUN 模式时，CNKI、CARSI 和学校认证域名必须走直连。详细说明见 [`references/environment.md`](references/environment.md)。

## 项目架构

```text
HumLit-Skills/
├── SKILL.md                       # Agent 路由器
├── manifest.yaml                  # fragment 映射
├── setup.md                       # Agent 自动安装说明
├── pyproject.toml                 # Python 包与 CLI 元数据
├── references/                    # 错误码、环境、工作流等参考资料
├── static/
│   ├── core/                      # 常驻执行规则
│   └── fragments/task/            # 按任务加载的详细说明
├── scripts/
│   ├── literature.py              # 统一 CLI 入口
│   ├── cli/                       # 参数解析、命令分发和输出
│   ├── core/                      # 搜索、格式化、文档和 CNKI 逻辑
│   ├── requirements.lock          # 发布验证的运行时依赖
│   └── requirements-dev.lock      # 测试依赖
├── evals/
│   ├── capability-contract.json   # 能力合同
│   ├── skill-routing-cases.json   # 正/负路由案例
│   └── results/                   # 发布验证证据
└── tests/                         # 单元、合同、E2E 与跨平台测试
```

CLI 使用惰性导入：只加载当前命令对应的模块，避免离线格式化任务被浏览器或联网依赖阻塞。

## 质量与验证

每次 `main` 推送会在 GitHub Actions 中执行：

- Ubuntu：Python 3.9、3.11、3.13。
- macOS：Python 3.11。
- Windows：Python 3.11。
- 完整 pytest、CLI 身份、发布合同和离线端到端 smoke。

涉及运行时代码、依赖或打包配置时，额外执行 Windows/macOS 对抗矩阵：

- 从源码构建 wheel。
- 安装生成的 wheel，而不是依赖源码目录。
- 验证中文路径、编码、当前目录变化和已安装入口。

当前稳定版本的发布证据：

- [`evals/results/v1.0.2-e2e-smoke.json`](evals/results/v1.0.2-e2e-smoke.json)
- [`evals/results/v1.0.2-summary.json`](evals/results/v1.0.2-summary.json)
- [HumLit Skills v1.0.2](https://github.com/ZhuXingcai/HumLit-Skills/releases/tag/v1.0.2)

联网 smoke 的失败可能来自上游限流或网络策略，必须和本地代码回归分开判断。

## 开发与测试

推荐使用隔离虚拟环境：

```bash
python -m venv .venv

# macOS/Linux
source .venv/bin/activate

# Windows PowerShell
# .venv\Scripts\Activate.ps1

python -m pip install -r scripts/requirements-dev.lock
python -m pip install --no-deps .
```

运行验证：

```bash
# 完整离线测试
python -m pytest -q

# 发布合同
python scripts/verify_release.py --version 1.0.2

# 离线端到端产物链
python scripts/smoke_test.py --mode offline

# 显式启用公开 API 测试
HUMLIT_RUN_LIVE_TESTS=1 python -m pytest -m live -q

# 显式启用 CNKI 网络/桌面测试
HUMLIT_RUN_CNKI_TESTS=1 \
HUMLIT_RUN_CNKI_DESKTOP_TESTS=1 \
python -m pytest -m cnki -q
```

CNKI 测试会打开真实浏览器并访问真实服务，只应在具备合法权限的桌面环境中启用。

## 更新

Git 安装：

```bash
git pull --ff-only
python -m pip install -r scripts/requirements.lock
python -m pip install --no-deps .
humlit check
```

非 Git 安装需要从 [Releases](https://github.com/ZhuXingcai/HumLit-Skills/releases) 重新下载。`check` 只提示新版本，不会自动更新。

## 常见问题

### `check` 显示 `selenium_manager_on_demand`

这是正常状态，表示 Driver 尚未缓存，但 Selenium Manager 已可用。第一次真实 CNKI 操作会按需获取匹配 Driver。

### Semantic Scholar 返回 `API_RATE_LIMIT`

这是匿名 API 配额限制。可配置 `SEMANTIC_SCHOLAR_API_KEY`、稍后重试或切换 OpenAlex/DBLP/arXiv。程序不会把限流降级为空结果。

### CNKI 在校外打不开

先确认学校 VPN/CARSI 会话，再用浏览器手动访问 `https://kns.cnki.net/`。若使用系统代理或 TUN 模式，检查 CNKI、CARSI 和学校认证域名是否命中 DIRECT。

### `source_statuses` 中只有部分来源成功

只使用成功来源的结果，并明确说明覆盖范围。不要声称已经完整检索所有数据库。

### Windows 中文路径或终端乱码

使用 UTF-8 终端，PowerShell 中可先运行 `chcp 65001`。批量中文关键词优先写入 UTF-8 文件并使用 `--query-file`。更多约束见 [`references/environment.md`](references/environment.md)。

## 限制与责任边界

- 本项目仅供合法的学术研究与资料整理。
- CNKI 能力依赖用户自己的机构权限，并受 CNKI 页面、认证和服务策略影响。
- OpenAlex、Semantic Scholar、arXiv、NSSD、DBLP、Crossref 和 Unpaywall 的可用性由对应上游服务决定。
- OA 下载只接受验证为 PDF 的开放获取响应，不提供付费内容绕过。
- 自动生成的综述、盲审、润色、质性分析和理论候选必须由研究者核对。
- 下载文献的版权归原作者与出版方所有。

## License

HumLit Skills 采用 [MIT License](LICENSE)。

版本变化见 [`CHANGELOG.md`](CHANGELOG.md)，正式发布说明见 [`RELEASE_NOTES.md`](RELEASE_NOTES.md)。
