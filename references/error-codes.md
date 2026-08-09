# 错误码对照表

脚本在 `status` 为 `error`、`warning` 或 `partial` 时可能附带 `code` 字段，格式为 `{"status": "error|warning|partial", "code": "...", "message": "..."}`。
注意：部分 `warning`/`partial` 响应无 `code` 字段（如 `check`、`write-docx`、`patch-docx`），需读 `message` 或 `warnings` 数组。
`search --source all` 时知网失败不阻断，错误信息在 `cnki_error` 子字段中，Agent 应检查并提示用户。
Agent 根据此表决定如何回应用户。

| 错误码 | 含义 | Agent 应对 |
|--------|------|-----------|
| `CNKI_UNREACHABLE` | 无法连接知网 | 提示检查校园网/VPN |
| `CNKI_AUTH_FAILED` | 知网校外认证流程异常 | 展示 `message` 和认证入口，提示用户检查 `--auth-url`、`--institution`、`--direct-domain`，并在浏览器中完成学校登录/验证码后重试 |
| `CNKI_SEARCH_FAILED` | 搜索过程异常 | 提示网络问题，建议稍后重试 |
| `CNKI_BATCH_FAILED` | 批量搜索异常 | 同上 |
| `CNKI_DETAIL_FAILED` | 获取论文详情失败 | 提示网络问题或该论文页面结构异常 |
| `CNKI_DOWNLOAD_FAILED` | 下载失败 | 提示手动下载或检查网络 |
| `CNKI_BATCH_DOWNLOAD_FAILED` | 批量下载异常 | 同上 |
| `DOWNLOAD_BTN_NOT_FOUND` | 未找到下载按钮 | 该论文可能不支持在线下载（博硕论文等） |
| `DOWNLOAD_TIMEOUT` | 下载等待超时（warning） | 文件可能仍在下载，让用户检查目录 |
| `NO_URLS` | 未提供下载 URL | Agent 应从搜索结果中选取 URL 后传入 |
| `NO_KEYWORDS` | 未提供搜索关键词 | Agent 应从用户请求中提取关键词 |
| `NO_RESULTS` | 已成功查询的数据源无匹配结果 | 检查 `source_statuses` 后尝试同义词/英文关键词、放宽年份或改用 `--source api --async-search` |
| `SOURCE_UNAVAILABLE` | 数据源请求未完成（网络、代理、DNS 或服务不可用） | 不得解释为“无结果”；检查 `source_statuses`，修复网络或切换可用数据源后重试 |
| `SOURCE_HTTP_ERROR` | 数据源返回非成功 HTTP 状态 | 查看 `http_status`；5xx 稍后重试，4xx 检查参数或服务策略 |
| `SOURCE_SCHEMA_ERROR` | 数据源响应结构与解析契约不一致 | 视为上游接口漂移，保留响应证据并更新对应 contract fixture/parser |
| `PARTIAL_SOURCE_FAILURE` | 多源检索中部分来源失败 | 只使用成功来源的结果，并明确列出失败来源；不得声称已完整检索全部数据库 |
| `ADV_SEARCH_FALLBACK` | 高级搜索失败且无关键词可回退 | 提示用户补充关键词，或建议稍后重试；Agent 也可尝试改为传 keyword 重新搜索 |
| `UNKNOWN_SOURCE` | 未知数据源 | 可用：cnki, openalex, semantic, arxiv, nssd, dblp, api, all；base 为实验性显式入口 |
| `OA_DOWNLOAD_FAILED` | 已解析 OA URL，但网络、HTTP 或 PDF 签名验证失败 | 不得声称已下载；查看 `url/message`，稍后重试或改用 `--link-only` 人工核验 |
| `OA_PDF_TOO_LARGE` | OA 响应超过默认 100 MiB 上限 | 不保留部分文件；改用 `--link-only` 人工核验，不应通过提高上限绕过来源合法性检查 |
| `OA_OUTPUT_EXISTS` | 目标路径已有非 PDF 文件或无法安全检查 | 不覆盖；检查并移动既有文件后重试 |
| `DRIVER_MISSING` | 浏览器驱动缺失 | 运行 `check --fix` 读取 `recommended_actions`，在项目虚拟环境安装锁定依赖，必要时按平台机制授权联网下载驱动 |
| `SANDBOX_BLOCKED` | 沙箱阻止网络或浏览器能力 | 按 `check.capabilities.retry_command` 提权重试，不要直接判定 CNKI 不可用 |
| `API_RATE_LIMIT` | API 源触发速率限制 | 等待后重试，或切换到其他 API 源 / 使用 `--enable-fallback` |
| `UNSUPPORTED_URL` | URL 不是 http/https CNKI 主域或真实子域 | 仅支持合法知网直链；拒绝 hostname 混淆地址，可改用 `--doi` 查 OA |
| `OA_NOT_FOUND` | DOI 查询无 OA 且无知网 URL 可回退 | 返回 metadata 供 Agent 展示；建议用户手动获取或用知网 URL |
| `NO_DOWNLOAD_TARGET` | 未提供 URL 也未提供 DOI | Agent 应从搜索结果选取 URL 或提取 DOI |
| `UNSUPPORTED_FORMAT` | 不支持的文件格式 | 支持 .docx/.txt/.md；PDF 用 Agent 内置读取工具 |
| `NOT_PDF` | `pdf-meta` 输入不是 PDF 文件 | 检查文件路径和后缀 |
| `PDF_READ_FAILED` | PDF 元数据读取失败 | 换用 Agent 内置 PDF 读取工具或检查文件是否损坏 |
| `FILE_NOT_FOUND` | 指定文件不存在 | 检查路径是否正确 |
| `DOCX_PARSE_FAILED` | docx 文件解析异常 | 提示用户确认文件完整性 |
| `ENCODING_ERROR` | 文本文件编码无法识别 | 建议用户转为 UTF-8 编码 |
| `IMPORT_PARSE_FAILED` | 题录文件解析失败 | 检查文件格式是否为 NoteExpress/Refworks/BibTeX |
| `NO_SESSION_DATA` | 无会话数据 | 提示先执行 search、batch-search 或 import。注意：`read-detail` 在会话仅含 API 源论文（无知网论文）时也返回此码（status=warning），此时应提示用户 read-detail 仅支持知网论文 |
| `SESSION_CORRUPT` | 会话 JSON 损坏或 schema 不支持 | 停止写入；读取 `backup_path` 保留的备份，修复或恢复后再继续 |
| `NO_URL` | 未提供 URL 参数 | Agent 应从搜索结果中获取 URL |
| `UNSUPPORTED_EXPORT_FORMAT` | 不支持的导出格式 | 支持 bibtex/ris/markdown/json/excel/gbt7714/footnote/apa/mla/chicago |
| `MISSING_DEPENDENCY` | 缺少依赖包 | 提示用户 `pip install` |
| `IO_ERROR` | 文件保存失败（磁盘满、只读等） | 检查磁盘空间和写入权限 |
| `PATCH_PARSE_FAILED` | 补丁 JSON 解析失败 | 检查 JSON 格式是否正确 |
| `BROWSER_CRASH` | 浏览器进程崩溃（如 0x80000003） | 脚本已内置 `--disable-gpu` + `--disable-features=RendererCodeIntegrity` + 独立 `--user-data-dir` 防护。若仍崩溃：提权运行（`required_permissions: ["all"]`） |
| `DOWNLOAD_SOURCE_MISMATCH` | --download 仅支持 --source cnki | 提示用户搜索+下载一步到位仅限知网源 |
| `NO_SESSION` | 无搜索会话记录 | 提示先执行 search 或 batch-search |
| `INVALID_INDICES` | `read-detail --indices` 序号无效 | 根据当前会话论文数量重新选择 1 开始的序号或范围 |
| `NO_PAPER_ID` | 未提供论文标识 | Agent 应从搜索结果获取 DOI 或 URL |
| `RESOLVE_FAILED` | 无法识别论文标识或 API 查询失败 | 检查 DOI/URL 格式；可能 S2 API 暂时不可用 |
| `NO_DOWNLOAD_URLS` | search --download 但结果中无可用下载链接（warning） | 展示搜索结果，提示用户手动选取 URL 再 download |
| `WORKFLOW_NOT_FOUND` | 未找到预定义工作流 | 先运行 `workflows --list` 查看可用 ID |
| `INVALID_VARIABLES` | `workflows --variables` 不是合法 JSON | 修正 JSON 字符串，确保键和值使用双引号 |
| `MISSING_VARIABLES` | 工作流缺少必需变量 | 按响应中的 `required_variables` 补齐 |
| `REQUIREMENTS_NOT_MET` | 工作流前置条件不满足 | 读取 `missing` 和 `suggestions`，先完成环境检查或换用不依赖该能力的流程 |
| `WORKFLOW_STEP_FAILED` | 工作流某一步失败 | 查看 `failed_step`、`failed_command` 和前序 `results`，修复该步骤后重跑 |
| `NO_ACTION` | `workflows` 未指定操作 | 使用 `workflows --list` 或 `workflows --execute <workflow_id>` |

## 格式规范引擎（format-*）

`format-check` 即使发现大量违规仍返回 `status:success`，违规在 `issues[]` 中（每项含 `code`/`severity`/`fixable`）；下表的脚本级 code 才表示命令本身失败。

| code | 含义 | 应对 |
|------|------|------|
| `PROFILE_INVALID` | profile 字段非法（见 `errors[]`） | 按 errors 修正字段后重试 |
| `PROFILE_PARSE_FAILED` | profile JSON 解析失败 | 检查 JSON 语法 |
| `UNSUPPORTED_FORMAT` | 文件格式不支持 | 仅支持 .docx / .md / .txt |

issues[] 中常见 code（非脚本故障）：

| code | severity | fixable | 含义 |
|------|----------|---------|------|
| `MARGIN_MISMATCH` | error | 是 | 页边距不符 |
| `FONT_CJK_MISMATCH` / `FONT_LATIN_MISMATCH` | error | 是 | 中/西文字体不符 |
| `FONT_SIZE_MISMATCH` / `LINE_SPACING_MISMATCH` | error | 是 | 字号/行距不符 |
| `PAPER_MISMATCH` | warning | 是 | 纸张不符 |
| `SECTION_MISSING` | error | 否 | 缺必需章节，需 Agent/用户补 |
| `SECTION_ORDER` | warning | 否 | 章节顺序与规范不一致 |
| `HEADING_LEVEL_SKIP` | warning | 否 | 标题层级跳级 |
| `INTEXT_REF_UNMATCHED` / `REF_NOT_SEQUENTIAL` | warning | 否 | 正文引用与文末列表不匹配/不连续 |
| `TOC_MISMATCH` | warning | 否 | 正文标题未出现在目录 |

## 盲审模拟引擎（review-rubric / review-signals）

| code | 含义 | 应对 |
|------|------|------|
| `RUBRIC_INVALID` | rubric 字段非法（见 errors[]，常见权重和≠100） | 按 errors 修正后重试 |
| `RUBRIC_PARSE_FAILED` | rubric JSON 解析失败 | 检查 JSON 语法 |
| `UNSUPPORTED_FORMAT` | 文件格式不支持 | 仅支持 .docx / .md / .txt |

`review-signals` 即使信号显示论文较弱仍返回 `status:success`，信号在 `signals` 中；脚本不打分，评分由 Agent 按 fragment 协议给出。

## 史料引用引擎（cite-source / cite-source-template）

| code | 含义 | 应对 |
|------|------|------|
| `ENTRY_PARSE_FAILED` | 史料条目 JSON 解析失败 | 检查 JSON 语法 |
| `EMPTY_ENTRIES` | 条目为空 | 至少提供一条史料条目 |
| `INVALID_SOURCE_CATEGORY` | source_category 不在 7 类 | 用 ancient/archive/gazetteer/epigraph/periodical/genealogy/oral |
| `FILE_NOT_FOUND` | 条目文件不存在 | 检查路径或用 --stdin |

`cite-source` 单条目缺字段不报 error，进各条 `warnings`；整体仍 `status:success`。

## 中文润色引擎（polish-signals）

| code | 含义 | 应对 |
|------|------|------|
| `UNSUPPORTED_FORMAT` | 文件格式不支持 | 仅支持 .md / .txt / .docx |
| `FILE_NOT_FOUND` | 文稿文件不存在 | 检查路径或用 --stdin |
| `ENCODING_ERROR` | 文件编码无法识别 | 转存 UTF-8 |

`polish-signals` 只诊断不改写，问题均为 warning（在 `issues` 中），整体 `status:success`；润色由 Agent 按 fragment 协议完成。

## C刊适配引擎（journal-profile / journal-check）

| code | 含义 | 应对 |
|------|------|------|
| `PROFILE_INVALID` | profile 字段非法（见 errors[]，如字数区间下限>上限） | 按 errors 修正后重试 |
| `PROFILE_PARSE_FAILED` | profile JSON 解析失败 | 检查 JSON 语法 |
| `UNSUPPORTED_FORMAT` | 文件格式不支持 | 仅支持 .docx / .md / .txt |
| `FILE_NOT_FOUND` | 稿件或 profile 文件不存在 | 检查路径 |
| `MISSING_DEPENDENCY` | .docx 缺 python-docx | 提示 `pip install python-docx` |
| `ENCODING_ERROR` | 文本编码无法识别 | 转存 UTF-8 |

`journal-check` 即使大量不达标或检出泄露仍返回 `status:success`；适配问题在 `issues`（warning），匿名泄露在 `anonymity.leaks`（profile.anonymous=true 时 severity=error 表一票否决，但不阻断脚本）。删改由 Agent 据用户确认完成。

## 质性编码引擎（qual-codebook-template / qual-code）

| code | 含义 | 应对 |
|------|------|------|
| `CODEBOOK_INVALID` | 编码簿字段非法（见 errors[]，如 codes 为空、编码缺 keywords/patterns） | 按 errors 修正后重试 |
| `CODEBOOK_PARSE_FAILED` | 编码簿 JSON 解析失败 | 检查 JSON 语法 |
| `BAD_PATTERN` | 某编码的正则 patterns 编译失败（见 errors[]） | 修正该正则 |
| `UNSUPPORTED_FORMAT` | 文件格式不支持 | 仅支持 .docx / .md / .txt |
| `FILE_NOT_FOUND` | 文本或编码簿文件不存在 | 检查路径或用 --stdin |
| `MISSING_DEPENDENCY` | .docx 缺 python-docx | 提示 `pip install python-docx` |
| `ENCODING_ERROR` | 文本编码无法识别 | 转存 UTF-8 |

`qual-code` 只做确定性命中统计，即使零命中仍 `status:success`（命中在 `codes[].matches`，共现在 `cooccurrence`）；开放式编码与主题归纳由研究者/Agent 完成。

## 理论框架引擎（theory-catalog / theory-match）

| code | 含义 | 应对 |
|------|------|------|
| `NO_KEYWORDS` | theory-match 未提供 --keywords | 从研究问题提取关键词，逗号分隔后重试 |
| `LIBRARY_PARSE_FAILED` | 自定义理论库 JSON 解析失败 | 检查 JSON 语法 |
| `LIBRARY_INVALID` | 自定义库结构非法（非列表/条目非对象） | 用 `[...]` 或 `{"theories":[...]}`，每条为对象 |
| `FILE_NOT_FOUND` | --library 文件不存在 | 检查路径 |

`theory-catalog`/`theory-match` 即使零命中仍 `status:success`（结果在 `theories`/`matches`）。匹配得分仅关键词重叠，**不代表理论适配度**；理论选择是学术判断，由研究者/Agent 据原典与本领域文献决定。
