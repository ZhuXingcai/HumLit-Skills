# Task Fragment: 学位论文/期刊格式规范

## 触发条件

将用户提供的学校/期刊要求建模、检测论文格式或套用可修复规则。

## 排除条件

捏造机构要求、自动补写缺失章节或声称未观测维度合格。

## 前置条件

需要用户要求或已验证 profile，以及 `.docx/.md/.txt` 稿件。

## 决策流程

1. **拿到格式要求** → 用户给学校/期刊格式文档（文字/截图/.docx）。Agent 跑 `format-profile --template --output profile.json` 拿骨架，按要求填值，再 `format-profile --validate profile.json` 校验。
2. **检测** → `format-check thesis.docx --profile profile.json`，读 issues 清单向用户报告。
3. **套用** → `format-apply thesis.docx --profile profile.json`（.docx 原地重排 / .md 生成），产出 `原名_formatted.docx`。

## 命令

| 命令 | 用途 | 关键参数 |
|------|------|----------|
| `format-profile` | profile 模板/校验 | `--template` `--validate p.json` `--output` |
| `format-check "file"` | 格式检测，输出问题清单 | `--profile`（必填） |
| `format-apply "file"` | 套用格式产出 .docx | `--profile`（必填） `--output` |

## profile 字段（Agent 据用户要求填）

- `page`：纸张 `paper`、页边距 `margin_cm{top,bottom,left,right}`。
- `body`：中英文字体 `font_cjk/font_latin`、字号 `size_pt`（小四=12 五号=10.5 小五=9）、行距 `line_spacing`、首行缩进 `first_line_indent_char`、段后距 `space_after_pt`。
- `headings[]`：每级 `level/font_cjk/size_pt/bold/align/numbering`。
- `structure.required_sections[]`：`id/title_patterns/order/required`，配 `enforce_order`。
- `references`：`style`（gbt7714/gb/apa/mla/chicago/footnote）、`numbered/require_sequential/require_intext_match/hanging_indent_char`。
- `footnotes`：`location`（footnote/endnote）、`marker_style/numbering`。
- `figures`/`tables`：`caption_prefix/caption_position/numbering(chapter|continuous)/caption_size_pt/align`。

## 要点

- profile **由用户提供的格式要求驱动**，不内置具体高校库；不确定的字段保留默认即可，校验只拒非法值。
- `format-check` 即使发现大量违规仍 `status:success`，违规在 `issues[]` 里；脚本故障才是 error 状态。
- `issues[].fixable=true`（字体/字号/行距/页边距）→ `format-apply` 可自动修；`fixable=false`（缺章节、正文引用与列表不匹配）→ 需 Agent/用户补内容，apply 不臆造。
- `format-apply` 默认输出 `原名_formatted.docx`，不覆盖原文件。
- 错误码见 [error-codes.md](../../../references/error-codes.md)。

## 输出合同

`issues[]` 明确 severity/fixable 和 observed/unknown 维度；apply 产出新 `.docx`。

## 停止与降级

profile 非法时停止；`fixable=false` 保留给 Agent/用户，不臆造内容或覆盖原稿。

## 附件

- [错误码](../../../references/error-codes.md)
