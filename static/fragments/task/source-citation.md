# Task Fragment: 史料引用（古籍/档案/方志/碑刻/报刊/家谱/口述）

> 对应命令：`cite-source` `cite-source-template`。用户意图为"古籍/档案/方志/碑刻怎么引用、史料脚注、史料参考文献、引用一条史料"时读本文件。

## 工作流

1. **取字段模板** → `cite-source-template --type ancient`（或 archive/gazetteer/epigraph/periodical/genealogy/oral）拿该类字段骨架。
2. **填条目** → Agent 据用户提供的原书/档案信息填成条目 JSON（单条或数组），史料常残缺、缺字段可留空。
3. **出引用** → `cite-source entries.json`（或 `--stdin`），默认同时出脚注体 + GB/T 7714；`--style footnote/gbt7714` 只出一种。

## 命令速查

| 命令 | 用途 | 关键参数 |
|------|------|----------|
| `cite-source-template --type <类型>` | 史料字段模板 | `--output` |
| `cite-source "entries.json"` | 史料→脚注体+GB/T7714 | `--stdin` `--style footnote/gbt7714/both` `--start-index N` `--raw` |

## 7 类与体例

- `ancient`古籍 / `gazetteer`方志 / `genealogy`家谱：古籍式（著者：《书名》卷次《篇》，点校者，地：社，年，第X页）。
- `archive`档案：《文件题名》，日期，某某馆藏，全宗，档号XXX。
- `epigraph`碑刻金石：《碑名》，立石年代，现藏地，收入《金石萃编》卷X。
- `periodical`报刊：《文章题名》，《报刊名》某年某月某日，版次。
- `oral`口述：口述者口述：《题名》，访谈者访谈，地点，日期。

## 要点

- 史料引用**由 Agent 据原书/档案信息填字段**，脚本只做确定性格式化；不杜撰版本、档号、卷次。
- 默认 `--style both`：脚注体供正文脚注、GB/T 7714 供文末参考文献。
- `--start-index` 可接续正文已有脚注序号（圈号①②…超过 20 用括号数字）。
- 带 `source_category` 的条目也可经 `cite`/`export`（会自动走史料 GB/T 7714 著录）。
- 缺字段进各条 `warnings`，不阻断；错误码见 [error-codes.md](../../../references/error-codes.md)。
