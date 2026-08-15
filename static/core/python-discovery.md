# Python 发现与首次自检

> always_load：每次会话首次调用脚本前读取一次。

## 解析解释器

不要假设 `python` 在 PATH。按顺序选择并在当前会话复用：

1. 环境变量 `$PYTHON`
2. Windows 的 `py -3`
3. `python3`
4. `python`

全部不可用时才提示安装 Python 3.9+。Exit code 127 表示命令不存在，应重新按顺序解析。下文 `<python>` 均指解析结果。

## 安装与自检

```bash
<python> -m pip install -r <skill_path>/scripts/requirements.lock
<python> <skill_path>/scripts/literature.py check --fix
```

同一会话只需自检一次，并缓存 `capabilities`。`--fix` 只返回
`recommended_actions`，不安装依赖、不修改配置、不申请权限。

## 决策

- `warning` 或可选项失败不等于整体阻断；只检查当前任务必需能力。
- `connector_available` 只表示本地连接器存在，live 可用性看实际 `source_statuses`。
- `cnki_feasible` 只描述 CNKI 本地前置条件，不代表已执行真实检索。
- `needs_escalation` 仅在任务必须使用 CNKI 时按返回的重试命令申请授权。
- Word、Excel、PDF 或 CNKI 依赖失败不得阻断无关的公开 API 或纯文本任务。
- BASE 保持显式实验入口，不进入默认聚合。
- 有新版本时只提示用户手动更新，不自动执行 `git pull`。

配置和字段解释见
[`../../references/configuration.md`](../../references/configuration.md)；
平台故障见 [`../../references/environment.md`](../../references/environment.md)；
授权流程见 [`sandbox-escalation.md`](sandbox-escalation.md)。
