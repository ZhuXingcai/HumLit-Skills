# Task Fragment: 中文学术润色

> 对应命令：`polish-signals`。用户意图为"润色/改写论文、学术表达优化、句子太啰嗦/口语化、提升书面化"时读本文件。

## 工作流

1. **诊断** → `polish-signals draft.md`（或 `--stdin`），得到逐句问题清单（超长句/口语化/主观/标点混用/重复/段首弱衔接）。
2. **逐段润色** → Agent 按 locator 定位，结合用户实际文稿改写：拆长句、去口语词、改客观表述、统一中文标点、消解重复、补逻辑连接。
3. **保原意** → 只改表达不改学术观点；不杜撰内容；改完可再跑一次确认问题减少。

## 命令速查

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
