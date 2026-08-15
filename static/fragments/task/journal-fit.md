# Task Fragment: C刊/核心期刊投稿适配

## 触发条件

C刊/核心期刊投稿硬性要求、篇幅、摘要、关键词和匿名泄露自查。

## 排除条件

预测录用概率、期刊质量、主题适配或编辑部未公开规则。

## 前置条件

需要稿件；准确检查目标期刊时需用户提供并编码《投稿须知》。

## 决策流程

1. **建期刊要求** → `journal-profile --template`（或 `--output p.json`）拿模板，Agent 据目标期刊《投稿须知》填 length/abstract/keywords/references/anonymous；缺省也可直接用内置默认。
2. **自查** → `journal-check draft.docx --profile p.json`（不带 `--profile` 用内置默认），得篇幅/摘要/关键词/参考文献达标信号 + 匿名泄露清单。
3. **据信号修改** → Agent 据 issues 给增删字数/补英文摘要/调关键词建议；据 anonymity.leaks 指出基金号/致谢具名/作者简介/自我指认机构，**提示用户确认后**再匿名化（脚本不自动删）。

## 命令

| 命令 | 用途 | 关键参数 |
|------|------|----------|
| `journal-profile` | 投稿要求模板 / 校验 | `--template` `--validate <file>` `--output` |
| `journal-check "file"` | 篇幅/摘要/关键词 + 匿名泄露 | `--profile <file>`（缺省内置默认） `--raw` |

## 检查维度

适配（warning）：`length` 正文字数区间、`abstract` 摘要字数+是否含英文摘要、`keywords` 关键词数区间、`references` 参考文献下限。
匿名泄露（profile.anonymous=true 时为 **error 一票否决**，否则 warning）：
- `fund_leak` 基金项目号/资助信息（如 `（17ZDA158）`、`No. 12BZS034`）。
- `ack_named` 具名致谢（致谢段、"感谢 XX 教授"）。
- `author_info` 作者简介/作者单位/通讯作者。
- `self_institution` 自我指认机构（"笔者所在 XX 大学"）。

## 要点

- 期刊体系（C刊/北大核心/CSCD 等）判断见 [core-journals.md](../../../references/core-journals.md)；profile.journal_system 仅作提示。
- 脚本算信号、定位泄露，**不自动改写/删除**；匿名化删改与字数调整交 Agent 据用户文稿判断。
- `journal-check` 即使大量不达标/有泄露仍 `status:success`，问题在 issues / anonymity.leaks。
- 与盲审自审（review-signals）互补：本引擎管投稿硬性门槛+匿名合规，盲审引擎只提供送审就绪度信号；两者都不预测录用或正式盲审结论。
- 错误码见 [error-codes.md](../../../references/error-codes.md)。

## 输出合同

适配问题进入 issues，匿名泄露进入 `anonymity.leaks`；脚本成功不等于稿件达标。

## 停止与降级

缺目标规则时只使用明确标注的默认 profile；任何身份删除都需用户确认。

## 附件

- [核心期刊体系](../../../references/core-journals.md)
- [错误码](../../../references/error-codes.md)
