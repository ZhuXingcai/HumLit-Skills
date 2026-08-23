# 建立真实论文端到端学术辅助基线

## Goal

在不泄露或提交用户论文材料的前提下，用本地代表性学术长文档样本做一
次可审计、可复现的端到端辅助试运行，确认 HumLit Skills 从文档读取、研
究文献整理、格式/匿名/表达信号到写作脚手架的真实边界，并把失败和人工
核验点沉淀为后续开发输入。

## What We Know

- 远程仓库已克隆到本机开发目录，`main` 与 `origin/main` 在 `41096bf`
  同步；设备绝对路径不写入跟踪文档。
- 项目是 Python 3.9+ CLI，入口为 `scripts/literature.py`，核心依赖和
  开发依赖已在本机 `.venv` 安装。
- CLI stdout 是单一 JSON 合同；`.humlit/` 是本地状态，论文和下载文件
  不进 Git。
- 本地测试输入目录包含多份代表性学术 DOCX/PDF/Markdown 样本（不纳入 Git）。
- Trellis 已初始化，项目规范位于 `.trellis/spec/backend/`，跨设备约定
  位于 `DEVELOPMENT.md`。

## Requirements

- [x] 选定一份代表性学术长文档 DOCX，只通过
  `read-paper` 读取，不直接解析 OOXML/XML。
- [x] 在临时工作目录运行 `read-paper`、`polish-signals`、
  `journal-check`/`review-signals` 中适用的确定性检查，并记录 JSON 合同、
  输出边界和人工判断项。
- [x] 用最小化的非敏感衍生文本验证 `review`/`write`/`validate`、引用和
  文档输出链路；真实论文文本不写入仓库。
- [x] 分别记录离线能力基线和公共 API/OA/CNKI 的条件验证边界；
  不把条件失败解释为无结果或代码失败。
- [x] 为发现的真实问题建立最小合成 fixture 与回归任务，不直接把用户论文
  复制到 `tests/`。
- [x] 将每次试运行的命令、输入角色、输出路径、状态、人工核验点和失败
  记录到本任务的研究/结果文件，供另一台设备继续。

## Acceptance Criteria

- [x] `python -m pytest` 完成并如实记录通过/跳过/失败。
- [x] `python scripts/verify_skill_architecture.py` 成功。
- [x] `python scripts/smoke_test.py --mode offline` 成功，且结果可追溯。
- [x] 至少一份真实 DOCX 试运行产生可解析 JSON；未把私人正文或附件加入
  Git diff。
- [x] 输出中明确区分程序确定性信号、来源状态和需要研究者核验的判断。
- [x] 任务 PRD/研究记录包含下一步优先级和跨设备恢复命令。

## Definition of Done

- 任务验证命令已执行并有结果证据。
- 真实素材仅以路径角色/统计信息出现，不出现正文摘录、隐私字段或凭证。
- 发现的问题被分类为代码缺陷、环境条件、数据质量或人工判断边界。
- 必要时补充最小 fixture/测试；不做无关重构。
- Trellis 任务、规范和 journal 足以让另一台设备继续工作。

## Out of Scope

- 不自动生成或宣称完成出版级论文、研究结论、研究空白或盲审结论。
- 不绕过 CNKI 认证、验证码、付费墙或机构权限。
- 不把用户论文、下载 PDF、cookies、`.humlit/` 状态或本机绝对路径提交
  到远程仓库。
- 不在本任务中升级依赖、重构 CLI 架构或修改公共 API，除非基线发现阻断
  后续工作的明确缺陷。

## Technical Approach

1. 先跑仓库自带的 pytest、架构验证和 offline smoke，建立代码基线。
2. 从用户资料目录选取代表性 DOCX，运行 `read-paper` 读取文本/表格等可
   见部分，随后运行确定性诊断命令；把 JSON 摘要写入任务研究目录。
3. 使用脱敏/合成材料跑综述、写作、验证、引用和文档输出链路，避免真实
   内容进入版本库。
4. 对公开源做 opt-in live 探测，记录成功、空结果、限流、条件可用和错误
   的区别；CNKI 只在用户自己的合法登录环境中手工确认。
5. 根据结果拆分后续开发任务，优先修复阻断端到端工作流的确定性缺陷。

## Risks and Mitigations

- **隐私泄露**：只记录文件角色和统计，不复制正文；所有生成物放临时目录。
- **误读文档**：遵守 `static/fragments/task/docx.md`，用 `read-paper` 并
  查看 `observability` 的可见/不可见边界。
- **把信号当结论**：结果必须保留 `needs_human_judgment`、证据编号和
  source status。
- **网络波动**：live 结果标记为 conditional/error，offline 基线独立验收。
- **跨设备漂移**：提交 PRD、研究记录、规范和可复现命令；设备本地身份和
  `.venv` 只按 `DEVELOPMENT.md` 重建。

## Technical Notes

- Relevant specs: `.trellis/spec/backend/index.md`, `error-handling.md`,
  `database-guidelines.md`, `logging-guidelines.md`, `quality-guidelines.md`.
- Workflow references: `references/workflows/retrieval-and-writing.md`,
  `references/workflows/revision-and-analysis.md`, and
  `static/fragments/task/docx.md`.
- Sample input root: repository-external local academic document sample directory;
  the exact device path is intentionally not tracked.
- Baseline environment: Python 3.12.10, HumLit 1.0.2, pytest 8.4.2.
