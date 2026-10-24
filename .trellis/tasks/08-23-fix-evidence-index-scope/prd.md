# P0：修复 write/validate 证据编号作用域

## Goal

确保 `write --validate` 和后续 `validate --file` 产生的每个证据编号都严格属于当前写作证据集，不再出现项目库原始编号、裁剪后编号和参考文献重编号混用。

## Evidence

端到端验证在宽文献库的 outline 中观察到 `invalid_evidence_index`：正文引用的编号不属于本次写作证据集。

## Requirements

- 建立最小合成 project，覆盖项目原始编号非连续、`--limit` 裁剪、相关性重排和参考文献重新编号。
- 明确一个写作产物内唯一的证据编号映射，并由正文、段落证据映射、参考文献和 validator 共用。
- 越界编号不得静默输出；生成阶段应修复或返回稳定 warning/error。
- 保持现有 JSON stdout、证据层级和引用格式合同。

## Acceptance Criteria

- [ ] 最小 fixture 能在修复前稳定复现 invalid index。
- [ ] 修复后正文、证据表和参考文献编号一一对应。
- [ ] `write --validate` 与独立 `validate --file` 对同一产物结论一致。
- [ ] 定向测试、完整 pytest、架构验证和 offline smoke 通过。

## Out of Scope

- 改写综述生成策略或主题聚类算法。
- Zotero、数据库 schema、依赖升级。

