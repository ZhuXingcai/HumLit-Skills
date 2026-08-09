# HumLit Skills 1.0.0 发布说明

发布日期：2026-08-09  
发布状态：稳定版  
项目地址：https://github.com/ZhuXingcai/HumLit-Skills  
版本页面：https://github.com/ZhuXingcai/HumLit-Skills/releases/tag/v1.0.0

## 版本概述

HumLit Skills 1.0.0 是独立项目的首个公开稳定版本，面向人文社会科学研究中的文献检索、合法开放获取、引用管理、学术文档处理和研究辅助任务。

项目使用统一的 `humlit-skills` Skill、`humlit` CLI、`.humlit` 运行目录和 `HUMLIT_*` 环境变量，不提供其他品牌入口或隐式配置别名。

与仅声明功能不同，本版本为 39 个命令和 17 类能力建立了机器可读合同，明确输入前置条件、输出结构、失败模式、成熟度和验证证据。脚本生成的规则信号不会被表述为最终学术判断。

## 主要亮点

### 多源学术检索

- 支持 OpenAlex、Semantic Scholar、arXiv、NSSD 和 DBLP 五个稳定公开源。
- 新增 `--source api`，可聚合公开源而不加载 CNKI 桌面组件。
- 多源输出提供 `source_statuses`，区分检索成功、空结果和上游错误。
- 聚合结果采用轮询合并，减少首个数据源占满结果集的偏差。
- BASE 仅保留为显式实验入口，不进入默认聚合或自动降级链。

### 合法开放获取与文档处理

- 可通过 DOI 解析并下载确有开放许可的 PDF，不绕过付费墙或机构认证。
- PDF 下载采用流式写入、大小限制、签名校验和原子保存，避免 HTML 登录页或残缺文件被误报为成功。
- 支持 Word 正文、表格、脚注、尾注、批注、页眉页脚和文本框的可观测提取。
- 提供 PDF 元数据提取、Markdown 转 Word、现有 Word 文档补丁和多种引用格式导出。

### 中文学术写作与人文社科工具

- 学位论文和期刊格式 profile 的生成、检测与套用。
- 盲审前规则信号、C刊投稿硬性规则和匿名泄露扫描。
- 中文学术表达中的超长句、口语化、主观表述和标点问题诊断。
- 古籍、档案、方志、碑刻、报刊、家谱和口述史料的脚注与 GB/T 7714 著录。
- 访谈编码簿关键词/正则命中统计、段落覆盖和编码共现。
- 常用社会科学理论目录与关键词候选匹配。

### 可审计的 Agent 辅助

文献综述、盲审结论、中文润色、开放编码、理论适配和引用建议属于 Agent-assisted 能力。脚本只生成可追溯的证据、规则信号或候选项，最终结论必须由 Agent 或研究者核对原文后完成。

## 稳定性改进

- NSSD 检索适配当前接口，同步与异步路径共享同一实现。
- 缓存和会话数据采用临时文件、`fsync` 和原子替换，降低中断导致的数据损坏风险。
- 损坏的缓存或会话文件会被保留备份，并通过结构化错误或 stderr 明确报告。
- BibTeX 解析支持嵌套花括号、引号值、常见转义和 `@string` 宏。
- `check --fix` 改为纯建议模式，不自动执行 `pip install`，也不修改用户级 Agent 配置。
- CLI 标准输入、标准输出和标准错误统一处理 UTF-8，兼容 Windows 默认 `cp1252` 环境。
- 路径处理已覆盖中文、空格、深层目录和常见 shell 元字符。

## 平台支持与验证

独立项目发布基线已在 GitHub 托管的真实 runner 上完成验证：

| 平台 | 环境 | 完整测试 | 对抗性测试 | 离线烟测 |
|------|------|----------|------------|----------|
| Windows | Windows AMD64, Python 3.11 | 282 passed | 9/9 passed | 5/5 passed |
| macOS | macOS ARM64, Python 3.11 | 282 passed | 9/9 passed | 5/5 passed |

对抗性测试覆盖：

- 从构建后的 wheel 安装，而不是依赖源码目录。
- 在仓库外目录调用安装后的 `humlit`。
- Windows `cp1252` 默认环境下的中文 stdin/stdout。
- 中文、空格、深层目录及 shell 元字符路径。
- 损坏 JSON、损坏会话和缺失文件的结构化降级。
- 首次运行时八个并发进程读取空状态目录。
- Windows 保留名、尾随空格/点、大小写冲突和常见路径长度风险。
- 机器可读命令的 JSON stdout 纯度。

验证记录：

- 完整 CI：https://github.com/ZhuXingcai/HumLit-Skills/actions/workflows/ci.yml
- Windows/macOS 对抗矩阵：https://github.com/ZhuXingcai/HumLit-Skills/actions/workflows/platform-adversarial.yml

## 安装

在支持 Skill 的 Agent 中发送：

```text
Fetch and follow instructions from https://raw.githubusercontent.com/ZhuXingcai/HumLit-Skills/main/setup.md
```

手动安装 Python 入口：

```bash
git clone https://github.com/ZhuXingcai/HumLit-Skills.git
cd HumLit-Skills
python -m pip install -r scripts/requirements.lock
python -m pip install --no-deps .
humlit --version
python scripts/smoke_test.py --mode offline
```

Windows 可将 `python` 替换为 `py -3`。

## 项目标识

- Skill ID 和安装目录为 `humlit-skills`。
- CLI 为 `humlit`。
- 运行数据位于当前项目的 `.humlit` 目录。
- 项目配置使用 `HUMLIT_*` 环境变量；第三方服务使用其官方变量，例如 `SEMANTIC_SCHOLAR_API_KEY`。
- 搜索结果使用 `retrieval_priority_score` 表示检索优先级；该分数不代表论文的学术质量。

## 使用边界

### 有条件能力

- 实时公开源检索依赖当前网络、上游服务覆盖和配额，实际状态以 `source_statuses` 为准。
- CNKI 能力需要本地 Edge 或 Chrome、WebDriver、校园网/VPN/CARSI 和用户合法权限。
- DOI 下载只在确认存在合法 OA PDF 时成功；无开放全文不是程序错误。

### 不提供的能力

- 不绕过付费墙、验证码、机构认证或数据库服务条款。
- 不提供知网查重百分比、规避检测、官方录用概率或正式盲审结论。
- 不将规则命中、关键词重叠或元数据完整度冒充语义判断和学术质量评价。
- 不替代通用网页搜索、代码文档检索、日常翻译或普通办公文档处理工具。

## 已知限制

- 实时 API 的可用性不能由离线测试保证，项目通过定时 live canary 持续监测维护中的公开源。
- CNKI 浏览器自动化依赖用户设备、浏览器版本、机构登录流程和网络环境，不属于无条件跨平台承诺。
- Agent-assisted 产物仍需核对原始论文、史料、引用和投稿规则。

## 兼容性

- Python 3.9 及以上版本。
- Windows、macOS 和 Linux。
- MIT License，许可证全文见 `LICENSE`。
