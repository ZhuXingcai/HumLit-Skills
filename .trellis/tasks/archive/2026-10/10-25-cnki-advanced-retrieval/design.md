# 技术设计：知网高级检索能力与条件可靠性

## 1. 边界与总体思路

三层共用一套"条件模型"，避免文档、CLI、驱动各说各话：

```
用户自然语言
   │  agent 依据 references/search/cnki-advanced-retrieval.md 拆解概念组
   ▼
CLI 参数（--condition / --professional / --match / --cross-language）
   │  scripts/core/cnki/query.py 解析 + 规范化 + 校验（纯函数，可离线测试）
   ▼
CnkiCondition / ProfessionalQuery
   │  scripts/core/cnki/search.py 驱动浏览器
   ▼
提交 → 回读结果页检索条件 → 比对 → retrieval 回显 + total_hits
```

关键取舍：**优先复用一框式/高级检索的同字段组合运算，而不是一上来就做专业检索。**
手册明确一框式与高级检索都支持 `*`、`+`、`-`，多数"A 且 B 且 C"需求在这一层就能解决；
专业检索只服务需要跨字段布尔组合、位置描述符、比较运算符的复杂场景。

## 2. 条件模型（新增 `scripts/core/cnki/query.py`，纯函数）

```python
@dataclass(frozen=True)
class CnkiCondition:
    field: str          # 中文检索项名：主题/篇关摘/关键词/篇名/全文/作者/...
    value: str          # 检索词或同字段组合表达式
    logic: str = "并且"  # 并且/或者/不含；第一条件忽略
    match: str | None = None  # 精确/模糊；主题不允许（只相关度匹配）
```

职责：
- `parse_condition(text)`：解析 `--condition` 的 `字段|逻辑|匹配|值` 形式。
- `normalize_value(value)`：按手册规范处理同字段组合——`*`、`+`、`-` 前后各空一个字节；
  含空格或特殊符号的词用英文半角单引号括起；不改动用户已有的引号与括号结构。
- `validate_conditions(conditions)`：条件数 1–10；字段名合法；
  主题不得指定 match；逻辑词合法；值非空。
- `validate_professional_expression(expr)`：非空、括号与单引号配对、
  不含换行注入；**不做语法重写**，表达式语义由知网判定。
- 全部不触网、不依赖 selenium，便于离线单测。

## 3. CLI 合同（`scripts/cli/search_cmd.py`，全部增量可选参数）

| 参数 | 含义 |
|------|------|
| `--condition "字段|逻辑|匹配|值"` | 可重复，多条件高级检索，最多 10 条 |
| `--professional "<表达式>"` | 专业检索表达式 |
| `--match 精确/模糊` | 单条件或一框式检索的匹配方式 |
| `--cross-language on/off` | 中英文扩展；默认 `on`（与知网默认一致） |

兼容与互斥：
- 既有 `query`、`--field`、`--author`、`--journal` 行为保留，内部统一映射为 `CnkiCondition`。
- `--professional` 与 `--condition` 互斥；与位置参数 `query` 互斥。
- 提供 `--condition` 时，`--author` / `--journal` 仍追加为条件（保持旧脚本可用）。
- 主题条件指定 `--match` 属于用法错误，显式报错而不是静默忽略。

## 4. 驱动改造（`scripts/core/cnki/search.py`）

- `_advanced_search(driver, conditions)`：
  - 入参改为 `list[CnkiCondition]`；`search_cnki` 与 `batch_search_cnki` 两个调用点同步改造。
  - 逐行设置字段、逻辑关系、匹配方式，并**逐行校验是否生效**。
  - 返回结构化结果（成功/失败 + 已应用条件 + 失败条件及原因），不再用
    `filledCount > 0` 作为成功判据。
  - 任一请求条件未应用 → 失败，不提交检索。
- 新增 `_professional_search(driver, expression)`：在 AdvSearch 页切到专业检索标签，
  填入表达式并提交；提交前回读输入框确认表达式完整写入。
- 新增 `_set_cross_language(driver, enabled)`：控制检索扩展中的中英文扩展。
- 新增 `_read_applied_conditions(driver)`：读取结果页"检索条件显示"区。
- 新增 `_read_total_hits(driver)`：读取命中数；读不到返回 `None`，不猜。
- 保留安全验证、真实空结果判定等既有状态机，不与本任务的状态分类混用。

## 5. 输出合同（增量，不改动既有字段）

```jsonc
"retrieval": {
  "source": "cnki",
  "mode": "simple | advanced | professional",
  "requested": { "conditions": [], "expression": null, "cross_language": true },
  "applied":   { "conditions": [], "expression": null },
  "verified":  true,          // false=回读不一致；null=无法回读
  "expression": null,          // professional 时回显实际提交表达式
  "total_hits": 123            // 读不到为 null
}
```

`verified: null` 表示页面不支持回读，只降级可观测性，不阻断；
`verified: false` 必须配错误码，结果不得当作可信检索输出。

## 6. 错误码（追加到 `references/error-codes.md`）

| 错误码 | 触发 | Agent 应对 |
|--------|------|-----------|
| `CNKI_INVALID_EXPRESSION` | 表达式/条件基本校验失败 | 按 message 修正检索式，不要原样重试 |
| `CNKI_TOO_MANY_CONDITIONS` | 条件超过 10 条 | 合并同字段条件或改用专业检索 |
| `CNKI_CONDITION_NOT_APPLIED` | 某条件未能应用到表单 | 展示具体字段与原因；不得解释为无结果 |
| `CNKI_RETRIEVAL_MISMATCH` | 回读条件与请求不一致 | 结果不可信，停止并报告差异 |

`ADV_SEARCH_FALLBACK` 保留，但只用于"高级检索整体不可用且存在可回退关键词"，
**不再吞掉部分条件未应用的情况**。这是有意的行为收紧，需写入 CHANGELOG。

## 7. 文档结构

- 新增 `references/search/cnki-advanced-retrieval.md`：概念组方法、字段决策、
  匹配语义、同字段组合、专业检索语法、结果中检索迭代、中英文扩展、反模式。
  语法逐条对应官方手册；三处手册自相矛盾处标"存疑，需在线验证"，`/AFT N` 不推荐。
- 更新 `static/fragments/task/search.md`：决策表新增"多概念组合/精准定位"分支，
  指向新参考文档；补充 `--condition` / `--professional` / `--cross-language` 参数。
- 更新 `manifest.yaml` 的 search 路由 references 列表，保持单一真源。
- 更新 `references/error-codes.md`、`CHANGELOG.md`。

## 8. 测试策略

- 离线（默认必跑）：
  - `tests/test_cnki_query.py`：条件解析、空格/引号规范化、校验、>10 报错、主题禁 match。
  - `tests/test_cnki_advanced_contract.py`：以假 driver/JS 返回值模拟
    部分条件未填入 → `CNKI_CONDITION_NOT_APPLIED`；回读不一致 → `CNKI_RETRIEVAL_MISMATCH`。
  - 既有 `test_cli_help.py` 等随新参数同步。
- 在线（opt-in，遵循仓库既有 live 标记约定）：手册示例检索式 + 一条多概念真实需求。
- 验收基线：原 306 passed, 9 skipped 不回归；`smoke_test.py --mode offline` 5/5；
  `verify_skill_architecture.py` 通过。

## 9. 回滚与风险

- 新参数、新输出字段均为增量；不使用新参数即回到旧调用形态。
- 风险 1：知网页面结构漂移导致条件校验误报 → 校验失败必须带可诊断信息，
  且与"真实空结果"状态分离。
- 风险 2：严格化让原本"部分成功"的旧调用变 error → 属预期收紧，文档与 CHANGELOG 明示。
- 风险 3：中英文扩展默认开启会改变部分旧检索的结果集 → 保持知网默认 on，
  但在 `retrieval.requested.cross_language` 中显式回显，便于归因。
- 回滚：单次 commit 按层划分，层 3 可独立 revert 而不影响层 1 文档与层 2 参数解析。
