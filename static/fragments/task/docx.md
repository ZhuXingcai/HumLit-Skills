# Task Fragment: Word 文档 / 排版 / 读论文

> 对应命令：`write-docx` `patch-docx` `read-paper` `pdf-meta`。用户意图为生成 Word、在原 .docx 插引用/改写、读取用户论文、从 PDF 提取元数据时读本文件。

## 决策指南

| 用户意图 | 命令 | 降级 |
|----------|------|------|
| Markdown → 学术格式 Word | `write-docx "file.md"` | `docx_tools: false` 时降级输出 Markdown |
| 在原 .docx 插引用/改写 | `patch-docx "file.docx" --patch patch.json` | 同上 |
| 读取用户论文 | `read-paper "file"` | — |
| 从 PDF 提元数据 | `pdf-meta "file.pdf"` | `pdf_tools: false` 时用 Agent PDF 工具人工提取 |

**docx_tools: false** → write-docx/patch-docx 不可用，降级输出 Markdown。

## 命令速查

| 命令 | 用途 | 关键参数 |
|------|------|----------|
| `read-paper "file"` | 读取用户论文（.docx/.txt/.md） | `--output` `--raw` |
| `pdf-meta "file.pdf"` | 从 PDF 提取元数据（标题、DOI 等） | |
| `write-docx "file.md"` | Markdown → 学术格式 Word | `--output` |
| `patch-docx "file.docx"` | 在原 .docx 上打补丁（插入引用/脚注） | `--patch` `--output` |

## 要点

- **禁止 Read .docx**，必须用 `read-paper` 读取（Read 会读到乱码/XML）。
- `read-paper` 读取正文、表格，以及 OOXML 中可提取的脚注、尾注、批注、页眉、页脚和文本框；JSON 输出的 `observability.observed_parts/unobserved_parts` 明确本次可见边界。嵌入对象、无 OCR 图片、绘图语义和已删除修订不在文本合同内，不能把返回文本宣称为 Word 的全部信息。
- `pdf-meta` 只读取 PDF 内嵌元数据/XMP 和前 3 页可识别 DOI，可选用 Crossref 补题录；它不读取全文、不做 OCR，也不保证扫描件有元数据。
- 论文超过 **15000 字**时：`read-paper` 正常读全文；Agent 按章节分段处理（每次 1-2 节），向用户汇报进度；`patch-docx` 可一次提交所有段补丁，无需分批。
- `patch-docx` 通过 patch JSON 描述插入位置与内容（引用/脚注），尽量保留原文格式；必须检查 `not_found`/`warnings`，`status:partial` 不能宣称全部修改成功。
- 本 fragment 只处理学术文档。普通合同、简历、会议通知等 Word/PDF 办公任务不应触发 HumLit Skills。

## 相关工作流

- [改写论文并生成 Word](../../../references/workflows.md#改写论文并生成-word内容大改) — read-paper → 改写 → write-docx
- [在原论文中插入引用](../../../references/workflows.md#在原论文中插入引用保留格式) — read-paper → 搜索 → patch JSON → patch-docx
- [学术表达优化](../../../references/workflows.md#学术表达优化) — 诊断 → 逐段优化 → patch-docx 写回
