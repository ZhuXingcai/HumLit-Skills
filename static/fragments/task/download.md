# Task Fragment: 下载 / 全文获取

## 触发条件

下载合法 OA PDF、CNKI 论文、详情、摘要/全文或建立校外认证会话。

## 排除条件

绕过付费墙、验证码、机构认证，或把摘要冒充全文。

## 前置条件

DOI OA 需要网络；CNKI 需要本地浏览器、Driver 和用户合法机构权限。

## 决策流程

| 用户意图 | cnki_feasible: true | cnki_feasible: false |
|----------|--------------------|--------------------|
| 已有 DOI，下载合法 OA PDF | `download --doi <DOI>` | 同左 |
| 下载 CNKI 论文 | `search --download` 或 `batch-download` | 不可用；不能用普通 API 摘要冒充全文 |
| 获取摘要/全文 | `read-detail --indices ... --fulltext` | API 源用搜索返回的摘要 |

## 命令

| 命令 | 用途 | 关键参数 |
|------|------|----------|
| `read-detail` | 获取摘要/全文（CNKI 论文，含硕博论文） | `--top-n` `--indices` `--fulltext` `--project` |
| `detail "url"` | 单篇详情 | |
| `auth-cnki` | 校外认证/会话预热 | `--auth-url` `--verify-url` `--institution` `--wait-seconds` `--captcha-timeout` `--direct-domain` `--keep-browser` `--force` |
| `download [url]` | CNKI URL 下载，或 DOI 解析并实际保存 OA PDF | `--dir` `--doi` `--file-format` `--link-only` |
| `batch-download [url1 url2 ...]` | 批量下载（推荐） | `--from-session` `--top-n` `--dir` `--file-format` `--fallback-format` `--citation-style` `--report-output` `--project` |

## 搜索与下载联动

当用户意图是"搜索并下载"或"下载文献"时，若用户未明确说明，先追问两个选项：
- 下载文件格式：`pdf` / `caj`（默认推荐 `pdf`）
- 下载清单引用格式：`gbt7714` / `apa` / `mla` / `chicago`（中文论文默认推荐 `gbt7714`）

当用户意图是"搜索并下载"时，优先使用 `search ... --download`（一步完成），避免分两步操作：
- "帮我搜20篇XX的论文并下载" → `search "XX" --pages 2 --download --download-top-n 20`
- "搜几篇关于XX的核心期刊论文下载下来" → `search "XX" --core CSSCI --download`
- 仅当用户需要先看结果再决定下载哪些时，才用两步走：`search` → `batch-download --from-session`

## 下载格式策略

- `download --doi` 先用配置了真实邮箱的 Unpaywall，否则用 OpenAlex OA 记录；响应以流式分块写入，默认上限 100 MiB，只有文件以 `%PDF-` 开头才原子保存到 `<dir>/pdf/`。
- DOI 文件名包含规范化片段和稳定哈希，避免不同 DOI 清洗后碰撞；目标文件已存在且是 PDF 时返回 `cached:true` 并保留原文件，非 PDF 既有文件返回 `OA_OUTPUT_EXISTS`，不覆盖。
- CNKI 直链只接受 `http/https` 且 hostname 为 `cnki.net` 或真实子域；仅在字符串中包含 `cnki.net` 的第三方域名会返回 `UNSUPPORTED_URL`。
- `--link-only` 只返回 OA 链接，输出方法名含 `_link`；不得向用户声称文件已下载。
- DOI 无 OA、OA URL 返回登录页/HTML、网络失败或超限时明确返回 `OA_NOT_FOUND`/`OA_DOWNLOAD_FAILED`/`OA_PDF_TOO_LARGE`；不绕过付费墙。
- 用户明确要求 PDF 时，默认先严格下载 PDF 到 `pdf/` 子目录
- 若用户同意兜底：`search --download` 使用 `--download-fallback-format caj`（也可用别名 `--fallback-format caj`），`batch-download` 使用 `--fallback-format caj`；只有 PDF 按钮不存在等明确失败项才再次尝试 CAJ，并写入 `caj/` 子目录，避免不同格式混放
- 不要静默把 CAJ 当作 PDF 返回；展示结果时必须标明实际格式、是否降级、保存目录

## 下载清单

下载完成后必须展示或引用脚本生成的下载清单：
- `download_report.path` 是 Markdown 清单文件，包含"已下载"与"未下载"两节
- 两节中的条目使用用户选择的引用格式，便于直接放入论文参考文献
- 若某篇缺少完整元数据，清单会用已知题名/URL 降级生成引用；Agent 应标注"元数据待补全"，不得凭记忆补写作者、年份、DOI
- 未下载项必须说明脚本返回的失败原因，例如无 PDF/CAJ 按钮、超时、知网不可达或权限不足

## 校外访问知网

用户在校外、VPN/CARSI/学校统一认证环境下要使用知网时，优先运行 `auth-cnki` 预热会话，而不是让用户自己猜浏览器状态：
- 不绑定具体学校。`--auth-url` 可传 CNKI FSSO、学校图书馆入口、VPN 入口或 CARSI 入口；`--institution` 可选，用于在 FSSO 页面自动选择机构，不传则让用户手动选择
- 运行前向用户明示：浏览器会打开；需要手动登录、扫码、短信、滑块等验证；不要关闭浏览器窗口；脚本会等待并自动保存 cookies/profile
- 如果用户使用 Clash/Mihomo/Surge/Quantumult X/PAC/系统代理等，询问或识别需要直连的学校认证域名，用 `--direct-domain` 传入；脚本会追加 CNKI/CARSI 直连域名，但 TUN/全局接管仍需要用户在代理软件里配置 DIRECT 规则
- 如果 `auth-cnki` 返回 `already_authenticated: true` 或 `access_confirmed: true`，同一项目后续 `search` / `read-detail` / `download` 直接复用 `.humlit/browser-profile` 和 cookies，非必要不要重复要求用户登录
- 如果返回 `warning` 且 `access_confirmed: false`，展示 `diagnostics.page.url/title`，提示用户浏览器可能还停在学校登录页或验证页；可用 `--keep-browser` 保留窗口继续手动处理

## 超时设置

- `read-detail --fulltext` 按 top_n×40s，`batch-download` 按 篇数×45s（含冷却）
- 命令超时转后台时，必须轮询终端文件直到出现 exit_code

沙盒/提权问题详见 [sandbox-escalation.md](../../core/sandbox-escalation.md)。

## 输出合同

JSON 明确实际文件格式、保存路径、字节数、缓存/降级和逐项失败；只有签名验证通过的 PDF 才算已下载。

## 停止与降级

无 OA、HTML 响应、超限或权限失败时不得声称下载成功；CNKI 全文失败可降级为明确标注的摘要，不能用公开 API 摘要冒充全文。

## 附件

- [环境与校外认证](../../../references/environment.md)
- [错误码](../../../references/error-codes.md)
- [工作流](../../../references/workflows.md)
