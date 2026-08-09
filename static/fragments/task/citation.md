# Task Fragment: 引用 / 导出 / 题录导入

> 对应命令：`cite` `export` `import`。用户意图为格式化参考文献、导出 BibTeX/RIS、导入知网题录时读本文件。

## 决策指南

| 用户意图 | 命令 |
|----------|------|
| 导入题录 | `import "file"`（NoteExpress/Refworks/BibTeX） |
| 导出 | `export --format bibtex/ris/markdown/json/excel/gbt7714/footnote/apa/mla/chicago` |
| 生成引用 | `cite --style gbt7714/gb/footnote/apa/mla/chicago` |

题录导入、现有元数据格式化与导出不依赖知网；但 `cite` 遇到缺卷期页码且带 CNKI URL 的记录时会尝试详情页补全。CNKI 不可用时仍可对已有字段生成引用，但必须保留缺失项，不能声称元数据完整。

## 命令速查

| 命令 | 用途 | 关键参数 |
|------|------|----------|
| `export` | 导出文献列表 | `--format` `--output` `--raw` `--project` |
| `cite` | 生成引用 | `--style`（gbt7714/gb/footnote/apa/mla/chicago） `--raw` `--project` |
| `import "file"` | 导入知网导出的题录文件 | NoteExpress/Refworks/BibTeX |

## 要点

- **引用格式由脚本生成**：Agent 不手拼 GB/T 7714，由 `cite` 命令统一导出。
- `cite` / `export` 加 `--raw` 输出纯文本（直接展示给用户时使用），否则输出 JSON。
- 引用格式直接完整展示，不截断。
- `cite` 会尝试对缺卷期页码的知网记录走 detail、对 DOI 记录走 Crossref；这些是条件性 live 补全，失败不应由 Agent 凭记忆填字段。
- `import` 成功时覆盖 session（可配合 `--project` 导入到指定课题）。
- BibTeX 导入按 entry/字段结构解析，支持平衡花括号、引号值、`@string` 宏和常见转义；无法形成题名的 entry 不写入 session。它不是 LaTeX 编译器，复杂自定义宏仍应先在文献管理器中展开后导出。
- 缺失元数据时标注"未获取"，不得凭记忆补写作者、年份、DOI。

## 相关工作流

- [引用建议](../../../references/workflows.md#引用建议) — 识别需引用句子 → 搜索匹配 → 区分必须/建议
