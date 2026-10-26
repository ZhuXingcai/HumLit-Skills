# Journal - ZhuXingcai (Part 1)

> AI development session journal
> Started: 2026-08-23

---



## Session 1: 初始化 HumLit 跨设备开发与端到端基线

**Date**: 2026-08-23
**Task**: 初始化 HumLit 跨设备开发与端到端基线
**Branch**: `main`

### Summary

克隆并初始化 Trellis，建立项目规范与跨设备协作指南；完成真实 DOCX 只读基线，修复 Windows 多客户端注册的 junction 回退；全量测试 306 passed、9 skipped，架构与 offline smoke 通过。

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `f241051` | (see git log) |
| `c2cf0d3` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete

---

## Session 2: 知网高级检索能力注入与条件可靠性
<!-- trellis-session: v=2 fp=a2ea6a96fa0d40b3 -->

**Date**: 2026-10-27
**Task**: 知网高级检索能力注入与条件可靠性
**Branch**: `feature/cnki-advanced-retrieval`

### Summary

把知网检索从关键词匹配升级为概念组检索式：新增条件模型、高级/专业检索能力、逐条件校验与结果页回读，并注入基于官方手册的检索式构造知识

### Main Changes

- 新增 core/cnki/query.py 条件模型（解析/规范化/校验/专业表达式）
- _advanced_search 逐条件校验字段、逻辑、匹配方式与写入值；任一未应用即失败
- 提交后回读检索条件并与请求比对，新增 total_hits
- search 支持 --condition/--professional/--match/--cross-language；batch-search 支持 --match/--cross-language
- 输出新增 retrieval（requested/applied/verified/expression/total_hits）
- 新增 cnki-advanced-retrieval.md 与 cnki-professional-syntax.md 两份参考文档并接入路由

### Git Commits

| Hash | Message |
|------|---------|
| `718be45` | feat(cnki): 检索条件模型与高级检索条件可靠性 |
| `796dde9` | feat(cli): search/batch-search 支持检索式参数与 retrieval 回显 |
| `7d49c03` | docs(cnki): 注入高级检索检索式构造知识并接入路由 |

### Testing

- [OK] pytest 388 passed, 9 skipped（基线 329，新增 59 个离线用例）
- [OK] smoke_test.py --mode offline 5/5
- [OK] verify_skill_architecture.py success
- [OK] git diff --check 通过

### Status

[OK] **Completed**

### Next Steps

- opt-in 真机验证：用 HAND 手册示例与多概念真实需求各跑一次，核对 retrieval.applied 与 verified
