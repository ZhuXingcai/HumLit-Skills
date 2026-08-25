# CNKI 认证到检索交接复盘（2026-08-25）

## 现象

- 用户已经在可见浏览器完成机构选择和登录，但 `auth-cnki` 仍持续等待到超时。
- 认证超时后脚本再次导航到验证页，并把正常页面中的残留挑战组件判为安全验证。
- Agent 随后重复执行带 `--force` 的认证，导致用户被再次要求登录。
- 因认证命令最终返回错误，原定 `batch-search` 没有进入执行阶段。

## Bug Analysis: 已登录但重复认证且未继续检索

### 1. Root Cause Category

- **Category**: B / E / D — 跨层合同、隐式假设与测试缺口。
- **Specific Cause**:
  - 认证识别假设机构名与“个人登录”必定出现在同一文本行，不能覆盖真实页眉 DOM 的分行布局。
  - `captchaId` 被视为永久安全门，即使挑战已经完成且检索控件可用。
  - `_wait_for_cnki_auth` 捕获了聚焦的安全验证异常，随后认证函数又导航验证页，形成第二次挑战循环。
  - Skill 只规定了认证行为，没有明确“认证是前置状态，必须继续用户原定检索”的交接合同。
  - Agent 使用 `--force` 重跑认证，错误地把重新认证当作检索失败后的默认恢复动作。

### 2. Why Fixes Failed

1. 只增加“机构名 + 个人登录”同一行识别：真实页眉可能分行，仍漏判。
2. 只过滤隐藏验证文案：URL 仍可能保留 `captchaId`，继续导致假阳性。
3. 只修核心检测器：没有修复 Skill 的认证到检索编排，Agent 仍可能在成功登录后停住或重跑认证。

### 3. Prevention Mechanisms

| Priority | Mechanism | Specific Action | Status |
|---|---|---|---|
| P0 | Runtime | 机构页眉识别允许有限相邻行，并排除 FSSO 机构选择页 | DONE |
| P0 | Runtime | `captchaId` 与可用检索 DOM 联合判断，明显可用页面不再卡死 | DONE |
| P0 | Runtime | 聚焦安全异常从认证轮询直接传播，不再吞掉后进入第二轮验证 | DONE |
| P0 | Skill contract | 认证成功或用户确认已登录后，继续原定检索；禁止循环 `--force` | DONE |
| P0 | Test | 增加分行页眉、FSSO 误判、残留 `captchaId`、异常传播和交接回归 | DONE |
| P1 | Live E2E | 不运行认证命令，直接复用本地会话完成 20 组批量检索 | DONE |

### 4. Systematic Expansion

- **Similar Issues**: `read-detail` 与 `download` 也必须把认证视为前置状态，不能在人工登录后停止。
- **Design Improvement**: 浏览器状态应由“挑战是否可见 + 目标页面是否可用”共同判定，不能由单一 URL 参数决定。
- **Process Improvement**: 真实端到端测试必须记录状态转移：`needs_auth -> authenticated -> action_running -> result`，而不只记录每条命令是否启动。

### 5. Knowledge Capture

- 已更新 `.trellis/spec/backend/error-handling.md` 的认证到动作交接合同。
- 已更新 `.trellis/spec/backend/quality-guidelines.md` 的浏览器认证交接测试检查项。
- 已更新 HumLit 下载/认证 fragment、环境参考和 README。

## 修复后真实验证

- 未再次运行 `auth-cnki`，未使用 `--force`，未再次要求用户登录。
- 直接运行原定 20 组 `batch-search`，浏览器读取本机 `.humlit/` 会话后进入真实检索。
- 13 组成功，7 组返回 `CNKI_RESULT_PAGE_UNAVAILABLE`；总题录 127 条，去重/年份过滤后 102 条，顶层 `status=partial`。
- 输出：本地临时验证结果文件（不纳入 Git）。
- 7 组失败保持页面状态错误，没有伪装为 `NO_RESULTS`。

## 隐私边界

- 本记录不包含学校、账号、Cookie、浏览器页面正文或论文全文。
- `.humlit/` 本地状态不进入 Git，也不复制到其他设备或其他用户环境。
