# 执行计划

原则：每层一个可独立验收的提交；先写会失败的测试再实现；真实知网验证放最后且 opt-in。

通用校验命令（在仓库根目录，使用项目虚拟环境）：

```bash
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe scripts/verify_skill_architecture.py
.venv/Scripts/python.exe scripts/smoke_test.py --mode offline
git diff --check
```

## Step 0 读规范（先于任何代码改动）

- [ ] 读 `.trellis/spec/backend/directory-structure.md`
- [ ] 读 `.trellis/spec/backend/error-handling.md`
- [ ] 读 `.trellis/spec/backend/quality-guidelines.md`
- [ ] 读 `.trellis/spec/backend/logging-guidelines.md`
- [ ] 记录当前测试基线：`.venv/Scripts/python.exe -m pytest -q`

## Step 1 层 3 的纯逻辑底座：条件模型（先行，因为层 2/3 都依赖它）

- [ ] 新增 `scripts/core/cnki/query.py`：`CnkiCondition`、`parse_condition`、
      `normalize_value`、`validate_conditions`、`validate_professional_expression`
- [ ] 新增 `tests/test_cnki_query.py`：空格/引号规范化、非法字段、主题禁 match、
      >10 条件、表达式括号与引号配对
- [ ] 验收：新测试通过，既有测试不回归

## Step 2 层 3：高级检索条件可靠性

- [ ] `_advanced_search` 改为结构化条件入参与结构化返回，逐行设置并校验
      字段 / 逻辑关系 / 匹配方式
- [ ] 任一条件未应用即失败，返回 `CNKI_CONDITION_NOT_APPLIED`，不提交检索
- [ ] 新增 `_read_applied_conditions` / `_read_total_hits`，提交后回读比对
- [ ] 回读不一致返回 `CNKI_RETRIEVAL_MISMATCH`；无法回读时 `verified=null`
- [ ] `search_cnki` 与 `batch_search_cnki` 两个调用点同步改造
- [ ] 新增 `tests/test_cnki_advanced_contract.py`：部分未填入、回读不一致、
      无法回读三条路径
- [ ] 验收：离线测试通过；确认不再存在"部分条件生效却返回成功"的路径

## Step 3 层 2：CLI 参数与专业检索

- [ ] `search` 增加 `--condition`（可重复）、`--professional`、`--match`、
      `--cross-language`
- [ ] 旧参数 `query` / `--field` / `--author` / `--journal` 映射为条件模型，行为兼容
- [ ] 新增 `_professional_search` 与 `_set_cross_language`
- [ ] 输出增加 `retrieval` 对象（requested/applied/verified/expression/total_hits）
- [ ] 互斥与非法组合校验：`--professional` × `--condition` × 位置参数 `query`
- [ ] 验收：`search --help` 正常；非法组合返回 `CNKI_INVALID_EXPRESSION`；
      CLI stdout 仍为单一 JSON 文档

## Step 4 层 1：知识注入与路由

- [ ] 新增 `references/search/cnki-advanced-retrieval.md`
      （语法逐条对应 `research/cnki-retrieval-manual-digest.md`，标注手册三处存疑）
- [ ] 更新 `static/fragments/task/search.md` 决策流程与参数表
- [ ] 更新 `manifest.yaml` references 列表，必要时重新生成 `SKILL.md`
- [ ] 更新 `references/error-codes.md` 追加 4 个错误码
- [ ] 更新 `CHANGELOG.md`，明示高级检索严格化属有意行为收紧
- [ ] 验收：`verify_skill_architecture.py` 通过；文档中的每个 CLI 示例参数真实存在

## Step 5 端到端与回归

- [ ] `.venv/Scripts/python.exe -m pytest -q` 全量通过
- [ ] `.venv/Scripts/python.exe scripts/smoke_test.py --mode offline` 5/5
- [ ] `.venv/Scripts/python.exe scripts/verify_skill_architecture.py`
- [ ] `git diff --check`
- [ ] opt-in 知网验证（需桌面与机构权限，用户确认后执行）：
      `.venv/Scripts/python.exe -m pytest -q -m cnki`
      并用手册示例 `SU %= 知识管理 OR TKA = 知识管理` 与一条多概念真实需求各跑一次，
      核对 `retrieval.applied` 与请求一致
- [ ] 用 agent 视角复测：给出"生成式AI广告披露 × 品牌信任"需求，
      确认 agent 会产出概念组检索式而不是一框堆词

## Step 6 收尾

- [ ] 按需更新 `.trellis/spec/backend/`（若形成了可复用的新约定）
- [ ] 提交按层划分：层3底座+可靠性 / 层2 CLI / 层1 文档
- [ ] `task.py finish` + `add_session.py` 记录 journal，归档任务

## 回滚点

- Step 2 之前：仅新增纯函数模块与测试，`git revert` 即可，无行为影响。
- Step 3 之后：CLI 增量可独立回退；层 3 严格化如需回退，单独 revert 对应提交，
  不影响文档与参数解析。
