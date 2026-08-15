# Progress
- 目标/基线：保持 CLI 与核心行为不变；HEAD 5b9ed82，292 passed、9 skipped，offline smoke 5/5。
- 顺序：架构门禁 → manifest 单一真源 → 索引瘦身 → 内容分片 → 路由与 canary。
- 最大风险：迁移规则时丢失触发/负边界，或把条件性上游失败误判为成功。
- 止损：每阶段相关测试；同一验收三次失败换项；最多三轮全量回归。
- 任务 1：架构验证器、生成器、预算门禁与红→绿反向验证完成。
- 任务 2：manifest 单一真源；SKILL 68 行、always-load 78 行、pre-task 146 行/5628 字符。
- 任务 3：12 fragment 标准化，参考文档分片，48 案例和 Live Canary 分流完成。
- 独立评测：gpt-5.5-2026-04-24，只读会话，48 条三项准确率均为 100%。
- 验收：306 passed、9 skipped；offline 5/5；真实 semantic=conditional；wheel 安装通过；核心 diff=0。
