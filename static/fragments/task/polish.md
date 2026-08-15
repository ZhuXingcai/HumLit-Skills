# Task Fragment: 中文学术润色

## 触发条件

中文论文润色、表达诊断、长句/口语/重复或衔接问题定位。

## 排除条件

查重率检测、规避检测、自动改写承诺或改变作者原意。

## 前置条件

需要 `.md/.txt/.docx` 文稿或 stdin，并由 Agent 阅读实际上下文。

## 决策流程

1. **诊断** → `polish-signals draft.md`（或 `--stdin`），得到逐句问题清单（超长句/口语化/主观/标点混用/重复/段首弱衔接）。
2. **逐段润色** → Agent 按 locator 定位，结合用户实际文稿改写：拆长句、去口语词、改客观表述、统一中文标点、消解重复、补逻辑连接。
3. **保原意** → 只改表达不改学术观点；不杜撰内容；改完可再跑一次确认问题减少。

## 命令

| 命令 | 用途 | 关键参数 |
|------|------|----------|
| `polish-signals "file"` | 中文学术表达诊断 | `--stdin` `--max-sentence N`（默认 80） `--raw` |

## 诊断维度

- `long_sentence` 超长句（> max-sentence 中文字）→ 拆分。
- `colloquial` 口语词（其实/的话/然后/挺…）→ 换书面表达。
- `subjective` 主观第一人称（我觉得/我认为）→ 改客观陈述。
- `punct_mix` 中英标点混用 → 统一中文标点。
- `repetition` 段内实词高频重复 → 同义替换/合并。
- `weak_transition` 段首缺逻辑连接 → 补过渡词（仅提示）。

## 要点

- 脚本**只诊断、不自动改写**（机器改写易损学术原意）；润色是 Agent 职责。
- 所有项 `severity: warning`，`fixable_by_agent: true`；`locator` 用「第X段第Y句」定位。
- 先处理结构性问题（超长句/重复）再做句面润色。
- 错误码见 [error-codes.md](../../../references/error-codes.md)。

## 输出合同

脚本只返回带 locator 的 warning signals；实际改写由 Agent 完成并说明策略。

## 停止与降级

无法确认作者原意时停止该段改写；规则零命中不代表文稿质量合格。

## 附件

- [表达优化工作流](../../../references/workflows.md#学术表达优化)
- [错误码](../../../references/error-codes.md)
