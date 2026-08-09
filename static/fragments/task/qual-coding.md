# Task Fragment: 质性研究编码

> 对应命令：`qual-codebook-template` `qual-code`。用户意图为"质性编码/访谈编码/扎根理论编码/给访谈文本打标签/编码簿/共现分析/田野材料编码"时读本文件。

## 工作流

1. **建编码簿** → `qual-codebook-template --output cb.json`，研究者/Agent 把每个编码配上 keywords（字面词）与/或 patterns（正则）；可迭代增补。
2. **标注** → `qual-code interview01.md --codebook cb.json`（或 `--stdin`），得每个编码的命中片段+段落定位+频次、编码共现矩阵、未编码段统计。
3. **据命中做解释** → Agent/研究者据命中片段做**开放式编码补充**（脚本未覆盖的新主题）、主题归纳、共现解读、饱和度判断；脚本的确定性命中仅是可审计的底稿。

## 命令速查

| 命令 | 用途 | 关键参数 |
|------|------|----------|
| `qual-codebook-template` | 编码簿模板 | `--output` |
| `qual-code "file"` | 关键词命中标注 + 频次/共现 | `--codebook <file>`（必需） `--stdin` `--raw` |

## 编码簿格式

```jsonc
{"name": "访谈编码簿v1", "codes": [
  {"code": "信任", "keywords": ["信任", "相信"], "patterns": [], "memo": "对医生的信任"},
  {"code": "就医决策", "keywords": ["就医", "挂号"], "patterns": ["\\d+元"]}
]}
```

- `keywords` 字面词全量匹配；`patterns` 正则（`re.finditer`）；二者至少一项。
- `memo` 为编码定义备注，便于团队一致性。

## 要点

- 脚本只做**确定性命中统计**（可复现、可审计），**不做语义编码、不归纳主题、不发现新编码**——那是质性研究者与 Agent 的解释性工作。
- 共现 = 同一段落内两个编码同时命中计一次，供看编码关联，非因果。
- 未编码段落数偏高 → 提示编码簿可能不匹配该文本或需补开放式编码。
- `qual-code` 即使零命中仍 `status:success`；坏正则报 `BAD_PATTERN`。
- 错误码见 [error-codes.md](../../../references/error-codes.md)。
