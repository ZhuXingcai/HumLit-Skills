# Python 解释器发现与环境自检

> always_load：每次会话首次调用脚本前先读本文件。

## 运行环境

Python 3.9+, Selenium 4.10+, Edge 或 Chrome, 知网需校园网/VPN。

## Python 解释器发现

Agent 不要假设 `python` 一定在 PATH 中。首次调用脚本前，应先解析可用 Python 命令，并在同一会话后续命令中复用：

1. 若环境变量 `PYTHON` 存在，优先使用 `$PYTHON`
2. **Windows 优先尝试 `py -3`**（Python Launcher，最可靠）
3. 否则尝试 `python3`
4. 否则尝试 `python`
5. 全部不可用时，才提示用户安装 Python 3.9+ 或将 Python 加入 PATH

**遇到 Exit code 127（command not found）表示 Python 命令不存在，必须按上述顺序重新解析。**

验证命令示例：

```bash
if [ -n "$PYTHON" ]; then
  "$PYTHON" --version
elif command -v py >/dev/null 2>&1; then
  py -3 --version
elif command -v python3 >/dev/null 2>&1; then
  python3 --version
elif command -v python >/dev/null 2>&1; then
  python --version
else
  echo "Python 3.9+ not found"
fi
```

下文命令中的 `python` 代表上述已解析出的解释器命令，不是固定字符串。

## 环境自检 check

Agent 在首次调用脚本前应运行 `check` 命令自检（同一会话只需运行一次，Agent 应缓存 `capabilities` 结果供后续命令使用）：

```bash
python scripts/literature.py check --fix
```

`--fix` 是**建议模式**：它只在 `recommended_actions` 中列出手动安装依赖、授权网络或检查 VPN 的动作，不执行 `pip install`，不修改项目或用户级沙箱配置，也不重试产生副作用的操作。Agent **不得因为 `check.status == "warning"` 或某个可选项 `fail` 直接退出**；必须读取 `capabilities` 决定下一步。只有 Python 无法运行、Python < 3.9、或当前任务必需能力不可用且无替代路径时，才算阻断。

`check` 返回本地依赖和 CNKI 桌面条件；它**不是所有 live API 的网络探针**：

- `sources.<name>.connector_available: true` → 连接器代码与本地依赖存在，不等于上游服务本次可访问。
- `sources.<name>.runtime_verified: null` → 本次 `check` 未发 live 请求；执行搜索后以 `source_statuses` 为准。
- `cnki_feasible: true` → 当前浏览器、驱动和连通性检查允许尝试 CNKI，仅代表 CNKI 条件能力。
- `cnki_feasible: false` → 仅当任务必须使用 CNKI，且返回 `needs_escalation: true` 时授权重试：
  0. 若存在 `needs_escalation: true` → 按 `retry_command` 重新运行，并按 `recommended_env` 设置环境变量；`agent_action: rerun_same_command_with_escalated_permissions` 表示必须请求平台提权
  1. 设置 `HUMLIT_SKIP_NETWORK_CHECK=1`，然后**以提权方式重新运行知网命令**（平台会弹窗让用户授权网络访问）。提权后 Selenium Manager 自动下载驱动，三个卡点一步清零
  2. 提权后仍失败 → 读 `fix_note`，**区分场景**：
     - 硕士/博士/学位论文、知网全文等**只有知网能做的任务** → 告知用户"请确认已连接校园网/VPN"，**不要用 API 源替代**
     - 其他通用搜索 → 用 `--source openalex` 继续，一句话告知用户

- `python-docx` / `openpyxl` / `pypdf` 失败只影响 Word/Excel/PDF 元数据功能，不影响搜索和纯文本引用；需要时降级输出 Markdown/JSON。
- `selenium`、浏览器、驱动、知网连通性失败只影响 CNKI 自动化；若用户任务不是 CNKI 专属，可用 API 源继续。
- `api_connectors_available: true` 时，OpenAlex/Semantic Scholar/arXiv/NSSD/DBLP 连接器不应因 CNKI 检查失败而中止；实际可用性仍由搜索响应决定。
- BASE 为 `experimental` 且 `opt_in_only: true`，不进入默认 `api/all` 聚合。

- `update.update_available: true` → 提示用户"有新版本可用，在 skill 目录执行 `git pull` 更新"（该字段仅在版本检测成功时存在，缺失时忽略）

沙盒/提权细节详见 [sandbox-escalation.md](sandbox-escalation.md)；平台兼容性详见 [environment.md](../../references/environment.md#平台兼容性)。

## 配置

优先级: **环境变量 > `.humlit/config.json` > 内置默认值**

| 配置项 | 环境变量 | config.json 键 | 默认值 |
|--------|----------|----------------|--------|
| 知网请求间隔 | `HUMLIT_REQUEST_INTERVAL` | `request_interval` | `3` |
| 缓存 TTL（天） | `HUMLIT_CACHE_TTL_DAYS` | `cache_ttl_days` | `30` |
| API 邮箱 | `HUMLIT_MAILTO` | `mailto` | 空（配置真实邮箱后启用 Unpaywall polite access） |
| Semantic Scholar API key | `SEMANTIC_SCHOLAR_API_KEY` | `semantic_scholar_api_key` | 空（无 key 时可能更易 429） |
| 下载目录 | `HUMLIT_SAVE_DIR` | `save_dir` | `./papers` |
| 浏览器 | `HUMLIT_BROWSER` | `browser` | `auto` |
| 批量下载窗口大小 | `HUMLIT_BATCH_WINDOW_SIZE` | `batch_window_size` | `10` |
| 跳过网络预检 | `HUMLIT_SKIP_NETWORK_CHECK` | — | `0`（沙盒中建议设为 `1`） |
| 浏览器驱动路径 | `HUMLIT_DRIVER_PATH` | — | 自动（手动指定 msedgedriver/chromedriver 路径） |
| Selenium 缓存路径 | `SE_CACHE_PATH` | — | 自动（默认缓存不可写时降级到 `.humlit/selenium-cache`） |

```bash
