# API 源检索最佳实践

本文档提供使用 OpenAlex、Semantic Scholar、arXiv、NSSD、DBLP 等维护中公开源，以及实验性 BASE 入口进行文献检索的实践指南。

---

## 数据源选择

### OpenAlex（推荐首选）
- **优势**：覆盖面广、元数据丰富、API 功能完善、支持高级过滤
- **适用场景**：综合性检索、跨学科研究、需要完整元数据
- **限制**：部分期刊名过滤不可靠（已通过客户端过滤解决）

### Semantic Scholar
- **优势**：引用数据准确、AI 驱动的相关性排序
- **适用场景**：计算机科学、生物医学领域、需要精确引用数据
- **限制**：覆盖面较 OpenAlex 窄、偶尔返回空结果

### arXiv
- **优势**：最新预印本、全文开放获取
- **适用场景**：物理、数学、计算机科学前沿研究
- **限制**：无引用数据、未经同行评审

### DBLP
- **优势**：计算机科学会议、期刊和技术报告覆盖稳定
- **适用场景**：计算机领域作者追踪、会议论文检索、经典系统论文查找
- **限制**：通常无摘要和被引数据，检索优先级主要依赖其他元数据

### BASE（实验入口）
- **优势**：开放获取资源覆盖广，适合补充欧洲高校和机构仓储文献
- **适用场景**：开放获取全文线索、跨机构资源补检
- **限制**：已知可能超时或受 IP/User-Agent 策略影响；仅显式 `--source base`，不进入聚合或 fallback

### 多源检索
```bash
# 自动去重，综合多个数据源的优势
search "topic" --source api --sort priority --limit 30

# 并发多源检索，覆盖 OpenAlex/S2/arXiv/NSSD/DBLP
search "topic" --source api --async-search --sort priority --limit 30

# 单源失败或无结果时自动尝试备用 API 源
search "topic" --source semantic --enable-fallback --limit 20
```

---

## 排序策略

### 按被引数排序（`--sort citations`）
**适用场景**：
- 查找经典文献、奠基性论文
- 了解领域主流观点和方法
- 需要高影响力论文支撑论点

**示例**：
```bash
search "deep learning" --source openalex --sort citations --limit 20
```

**注意**：
- 新论文被引数低，可能被排除
- 适合回顾性研究，不适合追踪最新进展

### 按时间排序（`--sort date`）
**适用场景**：
- 追踪最新研究进展
- 了解当前研究热点
- 需要最新数据和方法

**示例**：
```bash
search "transformer architecture" --source openalex --sort date --year-from 2023 --limit 15
```

**注意**：
- 最新论文可能质量参差不齐
- 建议结合年份过滤和检索优先级

### 按检索优先级排序（`--sort priority`）
**适用场景**：
- 快速筛选优先核验论文
- 需要完整摘要和元数据的论文
- 综合考虑元数据完整性、影响力线索和获取便利性

**示例**：
```bash
search "machine learning" --source openalex --sort priority --limit 20
```

**检索优先级评分维度**（0-100 分，仅用于安排核验顺序）：
- 摘要完整性（0-30）：>500 字得 30 分
- DOI 存在（20）：有 DOI 得 20 分
- 被引次数（0-20）：对数归一化
- 关键词存在（10）：有关键词得 10 分
- 开放获取（10）：OA 论文得 10 分
- 基本题录完整性（5）：题名、作者、年份、来源字段完整时加分，不按数据源身份加分
- 年份新近性（0-10）：最近 5 年内递减

该分数只用于安排元数据核验和精读顺序，不评价研究设计、论证质量或学术价值。

**优先级分数参考**：
- ≥80：元数据较完整，可优先核验
- 60-79：元数据完整性一般
- <60：可能较新、小众、无 DOI，或元数据不完整，不能据此判定低质量

---

## 高级过滤

### 期刊过滤（`--journal-filter`）
**适用场景**：
- 限定特定期刊或期刊系列
- 查找顶级期刊论文

**示例**：
```bash
# 查找 Nature 系列期刊
search "climate change" --source openalex --journal-filter "Nature" --limit 20

# 查找 Science 期刊
search "CRISPR" --source openalex --journal-filter "Science" --limit 15
```

**注意**：
- 使用子串匹配，"Nature" 会匹配 "Nature", "Nature Communications", "Nature Reviews" 等
- 大小写不敏感
- 所有 API 源使用客户端过滤（可靠性高）

### 作者过滤（`--author-filter`）
**适用场景**：
- 查找特定学者的论文
- 追踪领域专家的研究

**示例**：
```bash
# 查找 Geoffrey Hinton 的论文
search "neural networks" --source openalex --author-filter "Hinton" --limit 20

# 查找 Yann LeCun 的最新论文
search "deep learning" --source openalex --author-filter "LeCun" --sort date --limit 10
```

**注意**：
- OpenAlex 使用 API 级别过滤（效率高）
- Semantic Scholar 使用客户端过滤
- 使用姓氏即可，避免全名拼写错误

### 学科领域过滤（`--field-of-study`）
**适用场景**：
- 限定特定学科领域
- 跨学科检索时排除无关领域

**示例**：
```bash
# 限定计算机视觉领域
search "object detection" --source openalex --field-of-study "Computer Vision" --limit 20

# 限定自然语言处理领域
search "language model" --source openalex --field-of-study "Natural Language Processing" --limit 15
```

**注意**：
- OpenAlex 使用 API 级别过滤
- 学科名称需要英文
- 可能过滤掉跨学科论文

### 组合过滤
**适用场景**：
- 精确定位特定类型论文
- 多维度筛选优先核验文献

**示例**：
```bash
# 查找 2020 年后 Nature 上关于深度学习的高引论文
search "deep learning" --source openalex \
  --year-from 2020 \
  --journal-filter "Nature" \
  --sort citations \
  --limit 20

# 查找 Hinton 在计算机视觉领域的最新论文
search "neural networks" --source openalex \
  --author-filter "Hinton" \
  --field-of-study "Computer Vision" \
  --sort date \
  --limit 10

# 查找元数据较完整、便于优先核验的机器学习综述论文
search "machine learning survey" --source openalex \
  --year-from 2020 \
  --sort priority \
  --limit 15
```

---

## 字段搜索

### 标题搜索（`--field 篇名`）
**适用场景**：
- 查找特定主题的论文
- 减少摘要中偶然提及的噪音

**示例**：
```bash
# 只在标题中搜索 BERT
search "BERT" --source openalex --field 篇名 --limit 10
```

**注意**：
- OpenAlex 使用 API 级别过滤（精确）
- Semantic Scholar 使用客户端过滤
- 可能遗漏标题未提及但内容相关的论文

### 摘要搜索（`--field 摘要`）
**适用场景**：
- 查找方法或技术细节
- 摘要中明确提及的概念

**示例**：
```bash
# 在摘要中搜索 transformer architecture
search "transformer architecture" --source openalex --field 摘要 --limit 15
```

---

## 分页浏览

### 基本用法
**适用场景**：
- 浏览大量搜索结果
- 逐页筛选相关论文

**示例**：
```bash
# 第 1 页
search "artificial intelligence" --source openalex --limit 20 --page 1

# 第 2 页
search "artificial intelligence" --source openalex --limit 20 --page 2

# 第 3 页
search "artificial intelligence" --source openalex --limit 20 --page 3
```

**注意**：
- 每页结果单独缓存，重复访问速度快
- 不同页面之间无重复论文
- 支持 OpenAlex、Semantic Scholar、arXiv

### 分页策略
1. **初步筛选**：第 1 页使用 `--sort priority` 快速找到优先核验论文
2. **深度挖掘**：后续页面可能包含排序较后但仍有学术价值的论文
3. **组合使用**：先按检索优先级排序看第 1-2 页，再按时间排序看最新论文

---

## 结果去重

### 自动去重
**适用场景**：
- 使用 `--source api/all` 多源检索
- 避免重复论文

**机制**：
1. DOI 精确匹配（优先级最高）
2. 标题标准化匹配（去除标点、大小写）
3. 保留第一个出现的版本

**示例**：
```bash
# 自动去重多个数据源的结果
search "neural networks" --source api --sort priority --limit 30
```

去重只处理 DOI 精确相同或标题标准化后相同的记录，并保留首次出现版本；不保证保留元数据最完整版本，也不合并同一论文的版本关系。

---

## 摘要完整度

### 摘要完整度分类
所有 OpenAlex 结果包含 `abstract_quality` 字段：
- **full**：摘要长度 >200 字符（完整摘要）
- **partial**：摘要长度 1-200 字符（部分摘要）
- **none**：无摘要

### Crossref 摘要补充
- OpenAlex 摘要缺失时可条件性尝试 Crossref
- 覆盖率取决于 DOI 和上游记录，不承诺固定比例
- 失败不影响主搜索，但缺摘要条目不得被当作全文证据

### 使用建议
1. 优先选择 `abstract_quality: full` 的论文进行精读
2. `abstract_quality: none` 的论文可能需要访问原文
3. 检索优先级已考虑摘要完整性

---

## 完整工作流示例

### 场景 1：综述写作
```bash
# 1. 查找经典高引论文
search "deep learning" --source openalex --sort citations --year-from 2015 --limit 20

# 2. 查找最新进展
search "deep learning" --source openalex --sort date --year-from 2023 --limit 15

# 3. 按检索优先级筛选待核验文献
search "deep learning applications" --source openalex --sort priority --limit 10
```

### 场景 2：特定主题深度检索
```bash
# 1. 宽泛检索，了解全貌
search "transformer model" --source openalex --sort priority --limit 30

# 2. 精确过滤，定位核心论文
search "transformer model" --source openalex \
  --journal-filter "Nature" \
  --year-from 2020 \
  --sort citations \
  --limit 15

# 3. 追踪特定作者
search "transformer" --source openalex \
  --author-filter "Vaswani" \
  --sort date \
  --limit 10
```

### 场景 3：跨学科研究
```bash
# 1. 多源检索，自动去重
search "AI in healthcare" --source api --sort priority --limit 30

# 2. 限定学科领域
search "AI in healthcare" --source openalex \
  --field-of-study "Medicine" \
  --year-from 2020 \
  --limit 20

# 3. 查找顶级期刊论文
search "AI in healthcare" --source openalex \
  --journal-filter "Nature Medicine" \
  --sort citations \
  --limit 15
```

---

## 常见问题

### Q1: 为什么期刊过滤返回结果很少？
**A**: 期刊过滤使用子串匹配，确保期刊名拼写正确。例如 "Nature" 会匹配所有 Nature 系列期刊，但 "Natur" 不会匹配任何期刊。

### Q2: 作者过滤为什么找不到论文？
**A**:
1. 确认作者姓名拼写正确
2. 尝试只使用姓氏（例如 "Hinton" 而非 "Geoffrey Hinton"）
3. 作者可能使用不同的姓名变体

### Q3: 检索优先级低的论文是否值得阅读？
**A**: 检索优先级反映元数据完整性和影响力，不代表学术价值。低分论文可能是：
- 新发表的论文（被引数低）
- 预印本（无 DOI）
- 小众但重要的研究

### Q4: 如何平衡检索的全面性和精确性？
**A**:
1. **多源覆盖优先**：使用 `--source api`，不加过滤条件；这仍不等于穷尽全部学术数据库
2. **精确性优先**：使用多个过滤条件组合
3. **平衡策略**：先宽泛检索了解全貌，再精确过滤定位核心文献

### Q5: 分页时如何避免遗漏重要论文？
**A**:
1. 第 1 页使用 `--sort priority` 或 `--sort citations` 确保优先核验论文在前
2. 浏览 2-3 页确保覆盖主要文献
3. 必要时调整排序方式（例如改为 `--sort date`）再浏览

---

## 性能优化

### 缓存机制
- 搜索结果按配置的 TTL 缓存（默认 30 天）
- 相同查询参数（包括页码）直接从缓存读取
- 缓存命中通常避免重复网络请求，但不承诺固定耗时

### 搜索效率
- 单源和多源耗时取决于网络、限流与上游响应
- `--source api --async-search` 通常比顺序执行更快，但不承诺固定提升比例
- NSSD 通过同步表单接口在线程中并发调度，仍可能成为慢源

### 建议
1. 复用相同的搜索参数以利用缓存
2. 避免频繁更改过滤条件
3. 大量结果时使用分页而非增加 `--limit`

---

## 总结

### 核心原则
1. **数据源选择**：OpenAlex 首选，多源检索自动去重
2. **排序策略**：根据需求选择 citations/date/priority
3. **精确过滤**：组合使用期刊、作者、学科过滤
4. **核验优先**：利用检索优先级快速筛选优先核验论文
5. **分页浏览**：大量结果时逐页筛选

### 快速参考
| 需求 | 推荐命令 |
|------|---------|
| 经典文献 | `--sort citations --year-from 2015` |
| 最新进展 | `--sort date --year-from 2023` |
| 优先核验论文 | `--sort priority` |
| 顶级期刊 | `--journal-filter "Nature"` |
| 特定作者 | `--author-filter "姓氏"` |
| 精确主题 | `--field 篇名` |
| 综合检索 | `--source api --async-search --sort priority` |
| 大量结果 | `--page 2` |

---

**文档版本**: 1.0
**最后更新**: 2026-06-10
**相关文档**: [SKILL.md](../SKILL.md), [workflows.md](workflows.md)
