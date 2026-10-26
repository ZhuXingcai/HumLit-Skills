# 知网高级检索能力注入与条件可靠性

## Goal

让 agent 在需要**精准定位**中文文献时，能用概念组检索式而不是一框堆词；
让 CLI 真正支持同字段组合、多条件组合与专业检索；
并消除高级检索"条件静默丢失却仍返回结果"的可靠性缺陷。

## 背景与问题

用户反馈：当前 skill 的检索方式浅显，多为关键词匹配，未使用知网高级检索；
精准定位场景成功率低；且 agent 习惯一次性把多个关键词注入一个检索框，
导致得不到可用文献。

代码与文档核查（2026-10-25）确认三层原因：

1. **知识层空白**：`references/` 全文只有"提取中英文关键词""提取 5-10 组关键词
   用 `--append` 积累课题库"，没有概念组拆解、字段选择、匹配方式、检索式迭代的任何指导。
2. **能力层缺失**：`scripts/core/cnki/constants.py` 只有 `CNKI_SEARCH_URL` 与
   `CNKI_ADV_SEARCH_URL`，无专业检索入口；`search` 仅支持
   `query + --field/--author/--journal`，最多 3 个条件，无逻辑关系与匹配方式控制。
   `batch-search` 是 N 次**独立**检索，不能表达 AND。
3. **可靠性缺陷**：`scripts/core/cnki/search.py::_advanced_search` 的 JS 在
   `filledCount > 0` 时即返回 `ready`，部分条件未填入也会被判为成功并提交；
   未设置每行逻辑关系与匹配方式；提交后不回读校验。
   → 调用方无法区分"按 A 且 B 且 C 检索"与"只有 A 生效"。

## Requirements

### R1 知识注入（层 1）

- 新增 `references/search/cnki-advanced-retrieval.md`，内容必须基于知网官方手册
  （见 `research/cnki-retrieval-manual-digest.md`），不得凭记忆编写语法。
- 覆盖：概念组拆解法（块内 OR / 块间 AND / 排除 NOT）、字段选择决策、
  三种匹配方式的真实语义、同字段组合运算、专业检索语法、结果中检索迭代策略、
  中英文扩展的影响、同义词应优先用知网推荐引导而非编造。
- 明确反模式：一框堆多个空格分隔关键词；把 `batch-search` 当 AND 用；
  把 `SU` 相关匹配的噪声或空结果直接解释为"没有文献"。
- 在 `static/fragments/task/search.md` 的决策流程中加入"精准定位/多概念组合"分支，
  并按需更新 `manifest.yaml` 的 references 列表。

### R2 CLI 能力（层 2）

- `search` 支持传入**同字段组合表达式**（如 `主题：(生成式AI + AIGC) * 广告`），
  按手册规范处理空格与引号，不再把整串当作单一检索词。
- `search` 支持**多条件高级检索**：每条件可指定字段、逻辑关系、匹配方式，
  条件数上限 10（与知网一致）。
- `search` 支持**专业检索表达式**入口。
- 支持控制**中英文扩展**（默认行为需在文档中写明）。
- 输出合同新增**实际执行检索式/条件回显**与**命中数**（若页面可读取），
  使调用方能核对条件是否真的生效、并据此迭代宽窄。

### R3 高级检索可靠性（层 3）

- 逐条件校验：任一请求条件未成功应用时，不得静默继续；
  按项目错误码规范显式报错并指出是哪个条件。
- 支持设置每行的逻辑关系（并且/或者/不含）与匹配方式（精确/模糊）。
- 提交后回读结果页"检索条件显示"，与实际请求比对，不一致要显式暴露。
- 不得把条件应用失败伪装成空结果或成功结果。

### R4 质量与兼容

- 现有 `search` / `batch-search` 的既有调用方式与 JSON 输出字段保持向后兼容，
  新字段只做增量。
- 遵守 `.trellis/spec/backend/` 的 error-handling、quality、logging、directory-structure 指南。
- CLI stdout 仍为单一 JSON 文档；诊断信息走 stderr。
- 离线与在线测试分离：不依赖知网真实会话的用例必须可离线运行；
  真实知网验证用例保持 opt-in。

## 非目标

- 不做 OpenAlex / Semantic Scholar / arXiv 等 API 源的检索式语法改造。
- 不解决综述相关性排序问题（属既有任务 `08-23-improve-review-relevance`）。
- 不绕过知网安全验证、验证码或机构权限。
- 不引入"检索式质量评分"之类无法证实的指标。

## Acceptance Criteria

- [ ] AC1：`references/search/cnki-advanced-retrieval.md` 存在，语法条目均可追溯到
      官方手册；手册三处自相矛盾处已标注为"存疑，需在线验证"。
- [ ] AC2：`static/fragments/task/search.md` 含多概念组合/精准定位分支，
      `manifest.yaml` 引用一致，`verify_skill_architecture.py` 通过。
- [ ] AC3：给定多概念需求，CLI 能构造并提交同字段组合表达式；
      高级检索可提交 ≥4 个带逻辑与匹配方式的条件（超过 3 个现有限制）。
- [ ] AC4：专业检索表达式可通过 CLI 提交执行。
- [ ] AC5：输出中包含实际执行的检索式/条件回显；可读取时包含命中数。
- [ ] AC6：构造一个必定无法应用的条件（如非法字段/不存在行），
      CLI 返回显式错误而非"成功"或"空结果"。
- [ ] AC7：新增离线单元测试覆盖表达式构造、条件校验、回读不一致三条路径；
      既有测试不回归（基线 306 passed, 9 skipped）。
- [ ] AC8：`smoke_test.py --mode offline` 5/5 通过；`git diff --check` 通过。
- [ ] AC9（opt-in，需知网环境）：用手册示例检索式与一条多概念真实需求各跑一次，
      回显条件与请求一致，结果非误报。

## Notes

- 手册要点与出处见 `research/cnki-retrieval-manual-digest.md`。
- 技术方案见 `design.md`，执行顺序见 `implement.md`。
- 与既有任务的关系：本任务是底层检索能力；`08-23-improve-review-relevance`
  是综述场景的相关性调优，可在本任务完成后复用新能力。
