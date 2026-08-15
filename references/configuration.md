# 配置与自检字段

仅在修改运行参数或解释 `check` 输出时读取。

## 配置优先级

环境变量 > `.humlit/config.json` > 内置默认值。

| 配置项 | 环境变量 | config.json 键 | 默认值 |
|--------|----------|----------------|--------|
| 知网请求间隔 | `HUMLIT_REQUEST_INTERVAL` | `request_interval` | `3` |
| 缓存 TTL（天） | `HUMLIT_CACHE_TTL_DAYS` | `cache_ttl_days` | `30` |
| API 邮箱 | `HUMLIT_MAILTO` | `mailto` | 空 |
| Semantic Scholar key | `SEMANTIC_SCHOLAR_API_KEY` | `semantic_scholar_api_key` | 空 |
| 下载目录 | `HUMLIT_SAVE_DIR` | `save_dir` | `./papers` |
| 浏览器 | `HUMLIT_BROWSER` | `browser` | `auto` |
| 批量窗口 | `HUMLIT_BATCH_WINDOW_SIZE` | `batch_window_size` | `10` |
| 跳过网络预检 | `HUMLIT_SKIP_NETWORK_CHECK` | - | `0` |
| 浏览器驱动 | `HUMLIT_DRIVER_PATH` | - | 自动 |
| Selenium 缓存 | `SE_CACHE_PATH` | - | 自动 |

`HUMLIT_MAILTO` 应使用真实邮箱，以启用 Unpaywall/OpenAlex polite
access。Semantic Scholar 无 key 时更容易出现 `API_RATE_LIMIT`。

## check 字段

- `connector_available: true`：连接器代码和本地依赖存在，不代表上游可访问。
- `runtime_verified: null`：自检没有发起 live 请求；搜索结果看 `source_statuses`。
- `cnki_feasible: true`：当前本地前置条件允许尝试 CNKI，不代表搜索已成功。
- `cnki_feasible: false`：仅在任务必须用 CNKI 时处理授权、浏览器或网络。
- `needs_escalation: true`：按 `retry_command` 和 `recommended_env` 请求平台授权后重试。
- `api_connectors_available: true`：公开源不应因 CNKI 检查失败而被禁用。
- `update_available: true`：只提示用户手动更新，不自动执行 `git pull`。

## 能力降级

- Word/Excel/PDF 依赖失败时，可在任务允许时降级为 Markdown、JSON 或纯文本。
- Selenium、浏览器或 Driver 失败只影响 CNKI；通用检索可切换公开 API。
- CNKI 学位论文、合法全文等专属任务不得伪装为可由公开 API 等价替代。
- BASE 是显式实验入口，不进入 `api/all` 或自动 fallback。

沙箱授权见
[`../static/core/sandbox-escalation.md`](../static/core/sandbox-escalation.md)，
平台故障见 [`environment.md`](environment.md)。
