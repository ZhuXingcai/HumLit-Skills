# Task Fragment: 理论框架搭建

## 触发条件

理论目录浏览、研究关键词候选匹配和有边界的理论框架辅助。

## 排除条件

把关键词重叠分数当作理论适配度、原创性或导师认可。

## 前置条件

需要研究问题/关键词；最终判断必须回到原典和本领域文献。

## 决策流程

1. **据研究问题找候选** → `theory-match --keywords "信任,社会资本,弱关系"`（逗号分隔），得按关键词重叠排序的候选理论 + 命中词。
2. **浏览学科全貌** → `theory-catalog --discipline 社会学`（或 `--query 制度`）看某学科/某主题相关理论。
3. **判断与搭建** → Agent 据候选回到原典与本领域文献核对，判断**理论适配度**，与研究问题对接，搭建框架（通常 1 主理论 + 0-2 补充视角，避免堆砌）。脚本只给有依据的备选，不替代学术判断。

## 命令

| 命令 | 用途 | 关键参数 |
|------|------|----------|
| `theory-match` | 据关键词匹配候选理论 | `--keywords "a,b,c"`（必需） `--top N`（默认8） `--discipline` `--library` `--raw` |
| `theory-catalog` | 浏览/检索理论库 | `--discipline <学科>` `--query <词>` `--library` `--raw` |

## 学科与覆盖

社会学/政治学/传播学/教育学/管理学/经济学/心理学/人类学/法学/哲学；内置常用理论约 30 条（社会资本、弱关系、新制度主义、议程设置、计划行为、资源基础观、委托代理、深描等）。完整清单见 [theory-frameworks.md](../../../references/theory-frameworks.md)。

## 自定义库

`--library custom.json`（`[...]` 或 `{"theories":[...]}`，同 id 覆盖内置）叠加本领域专有理论：
```jsonc
{"theories": [{"id": "my_theory", "name": "X理论", "proposer": "某",
  "discipline": "社会学", "concepts": ["a"], "keywords": ["a","b"],
  "summary": "…", "key_refs": ["…"]}]}
```

## 要点

- 内置库是**常用理论精选（非穷举）**；匹配得分仅关键词重叠，**不代表适配度**。
- 理论选择是学术判断，必须回原典/本领域文献/导师意见核对，脚本不下结论。
- `theory-match` 缺 `--keywords` 报 `NO_KEYWORDS`；零命中仍 `status:success`（matches 为空）。
- 错误码见 [error-codes.md](../../../references/error-codes.md)。

## 输出合同

返回候选理论、命中关键词和目录来源；内置库明确非穷举。

## 停止与降级

缺关键词时停止并澄清；零命中不自动推荐无关理论，改为扩展关键词或自定义库。

## 附件

- [理论库](../../../references/theory-frameworks.md)
- [错误码](../../../references/error-codes.md)
