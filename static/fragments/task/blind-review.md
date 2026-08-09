# Task Fragment: 盲审模拟

> 对应命令：`review-rubric` `review-signals`。用户意图为"模拟盲审/投稿前自审/送审前自查/帮我审一下论文/会不会被毙/盲审会怎么评"时读本文件。

## 工作流

1. **（可选）准备 rubric** → 默认用教育部 4 维；用户给特定学校/期刊标准时，`review-rubric --template --output rubric.json`，按要求改维度/权重（权重和=100），再 `review-rubric --validate rubric.json`。
2. **算信号** → `review-signals thesis.docx [--rubric rubric.json] [--format-profile p.json]`，得到按维度归类的可度量信号 + needs_human_judgment + integrity_flags。
3. **扮演盲审专家** → Agent 按下方协议读论文实际内容，结合信号产出 3 位专家报告 + 1 份交叉综述。

## 命令速查

| 命令 | 用途 | 关键参数 |
|------|------|----------|
| `review-rubric` | rubric 模板/校验 | `--template` `--validate r.json` `--output` |
| `review-signals "file"` | 送审就绪度信号 | `--rubric` `--format-profile` `--raw` |

## Agent 盲审专家协议（核心）

收到 `review-signals` 的 JSON 后：

- **扮演 3 位盲审专家**，仅评审侧重不同（均需覆盖全部维度，差异是权重不是省略）：
  - 专家 1：侧重「选题与综述」+「学术规范与写作水平」
  - 专家 2：侧重「创新性及论文价值」
  - 专家 3：侧重「基础理论与科研能力」
- 每位专家输出：各维度得分（按 rubric 权重）、加权总分、档次（A/B/C/D，对照 `grade_bands`）、总体评语、**具体可执行修改意见**。
- 再出 **1 份交叉综述**：共识优点、共识风险、分歧点、最终档次区间、送审前必改项。

## 强约束（红线，借鉴 nature-reviewer）

- 只基于 `signals` + 用户提供的论文**实际内容**评审。`needs_human_judgment` 项必须读论文后判断；读不到对应内容时标「需补充材料 / AUTHOR_INPUT_NEEDED」，不臆测。
- 不杜撰论文中不存在的缺陷、证据、引用或章节。
- 脚本**不打分**，分数与档次由 Agent 依据 rubric 给出，并说明是"模拟参考、非答辩委员会/编辑最终决定"。
- 学术不端只依据 `integrity_flags` 提示**核查提醒**，不直接定性。
- `integrity_veto: true` 且确有实锤不端时，按规则提示"可能一票否决"，但需说明依据。

## 要点

- `review-signals` 即使信号显示论文较弱仍 `status:success`；脚本故障才是 error。
- `--format-profile` 传入时，「学术规范」维度的 `format_check` 内嵌 P0-② 检测结果（error/warning 数）。
- 错误码见 [error-codes.md](../../../references/error-codes.md)。
