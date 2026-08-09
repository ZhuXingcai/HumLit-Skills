# 沙盒环境与提权（on_demand）

> 遇到 `sandbox_blocked`、驱动缺失、`needs_escalation: true`、Exit code 49 等权限问题时读本文件。

## ⚠ 沙盒环境（Codex / Cursor / Claude Code / Gemini CLI / 本地 Agent）

知网功能需要 Selenium 浏览器自动化 → 需要 msedgedriver → 首次运行需联网下载驱动（~8MB）。沙盒默认可能禁网，但**所有主流平台都支持运行时提权**。

**Agent 遇到 `sandbox_blocked` 或驱动缺失时，必须以提权方式重试，不得直接放弃或回退 API 源。** 提权后平台会弹窗让用户授权。

当 `check.capabilities.needs_escalation: true` 时，Agent 必须把 `agent_action` 和 `retry_command` 视为下一步指令：携带 `recommended_env` 重新以提权权限运行同一检查或知网命令。未完成一次提权重试前，不得把 CNKI 判定为不可用，也不得直接回退到 API 源。

各平台提权方式：

| 平台 | 提权方法 |
|------|---------|
| **Codex** | 按客户端授权流程手动允许当前任务联网；如团队策略要求配置文件，由用户/管理员维护。`check --fix` 只返回建议，不创建或修改 `.codex/config.toml` |
| **Cursor** | Shell 工具加 `required_permissions: ["all"]` |
| **Claude Code（交互式）** | 用 `/permissions`、`permissions.allow/ask/deny` 或合适的 permission mode 批准 Bash/PowerShell、WebFetch、浏览器/网络相关命令；启用 Bash sandbox 时可用 `/sandbox` 配置允许域名、路径和是否允许失败后转普通权限流 |
| **Claude Code（子 agent/SDK）** | Bash/PowerShell 工具调用时添加 `dangerouslyDisableSandbox: true`（需要网络的命令：`check`、`search --source cnki`、`batch-search`、`download`、`batch-download`、`read-detail`）。**遇到 Exit code 49 表示权限被拒绝，必须添加此参数** |
| **Gemini CLI** | 若启用 `--sandbox` / `-s`、`GEMINI_SANDBOX` 或 `settings.json` 的 sandbox 配置，遇到网络/路径限制时批准 Sandbox Expansion Request，或调整 sandbox profile、`SANDBOX_MOUNTS`、代理、`security.toolSandboxing` 后重启 Gemini CLI；浏览器自动化在容器/系统沙箱中可能不可用，需改用有 GUI 和网络权限的本机会话 |
| **其他本地 Agent** | 按该平台的 allowlist、approval、sandbox expansion、unsandboxed retry 或提权参数重跑 `retry_command`，并携带 `recommended_env`；没有提权机制时，明确要求用户在有网络和浏览器权限的本地终端执行，不要静默回退 API 源 |

Codex 本地配置示例（不要提交到仓库）：
```toml
approval_policy = "on-request"
sandbox_mode = "workspace-write"

[sandbox_workspace_write]
network_access = true
```

以上仅是平台配置示例，不是 HumLit Skills 的写入目标。`check --fix` 不修改项目本地或用户级配置；它只在 `recommended_actions` 中提示用户按所属平台策略手动授权。

仅使用公开源（OpenAlex/S2/arXiv/NSSD/DBLP）时不因 CNKI 浏览器失败而提权，优先 `--source api --async-search`。BASE 是显式实验入口。

## 沙盒中运行知网的四个卡点

沙盒中运行知网命令可能遇到四个卡点：

1. **预检 socket 被禁**（WinError 10013）→ 脚本自动降级为软警告
2. **缓存不可写** → 脚本自动切换到 `.humlit/selenium-cache`
3. **驱动无法下载** → 提权后 Selenium Manager 自动下载
4. **浏览器进程崩溃**（`0x80000003 STATUS_BREAKPOINT`）→ 脚本自动在沙盒外启动浏览器（`CREATE_BREAKAWAY_FROM_JOB` / `ShellExecuteW`），再通过远程调试端口连接，用户无需手动操作

根本解法是**启用网络权限 + 提权运行**：
- **Codex**：按平台弹窗或团队策略手动授权网络；`check --fix` 不写 `.codex/config.toml`，只返回 `recommended_actions`
- **Cursor**：所有知网命令加 `required_permissions: ["all"]`
- **Claude Code（交互式）**：用 `/permissions` 或 `/sandbox` 批准 Bash/PowerShell、WebFetch、网络域名和必要路径；命令因 sandbox 限制失败时，允许其走普通权限流或按平台提示批准 unsandboxed retry
- **Claude Code（子 agent/SDK）**：所有知网命令的 Bash/PowerShell 工具调用必须加 `dangerouslyDisableSandbox: true`
- **Gemini CLI**：批准 Sandbox Expansion Request，或调整 `GEMINI_SANDBOX`、sandbox 配置、`SANDBOX_MOUNTS`、代理、`security.toolSandboxing` 后重启；若 GUI 浏览器无法在沙箱内启动，改用有 GUI 和网络权限的本机会话
- **其他本地 Agent**：用本平台的 allowlist、approval、sandbox expansion、unsandboxed retry 或提权参数重跑 `retry_command`
- **绝对不要**因为 `sandbox_blocked`、`driver_ok: false` 或 `needs_escalation: true` 就放弃知网、回退 API 源。正确做法是按 `retry_command` 和平台提权机制重试

## 常见错误码

- **Exit code 49**：Claude Code 子 agent 权限拒绝，需在 Bash/PowerShell 工具调用时添加 `dangerouslyDisableSandbox: true`
- **Gemini CLI sandbox denial / Operation not permitted**：批准 Sandbox Expansion Request，或调整 sandbox profile、挂载、代理、tool sandboxing 后重试；浏览器自动化失败时切换到有 GUI 权限的本机会话
- **Exit code 127**：命令未找到，需按 [Python 解释器发现](python-discovery.md#python-解释器发现) 流程重新解析 Python 命令（Windows 优先用 `py -3`）

详见 [Windows/中文环境约束与故障排查](../../references/environment.md)。
