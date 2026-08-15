# API 数据源与排序

## 数据源选择

### OpenAlex（推荐首选）
- **优势**：覆盖面广、元数据丰富、API 功能完善、支持高级过滤
- **适用场景**：综合性检索、跨学科研究、需要完整元数据
- **限制**：部分期刊名过滤不可靠（已通过客户端过滤解决）

### Semantic Scholar
- **优势**：引用数据准确、AI 驱动的相关性排序
- **适用场景**：计算机科学、生物医学领域、需要精确引用数据
- **限制**：覆盖面较 OpenAlex 窄、偶尔返回空结果或匿名限流

### arXiv
- **优势**：最新预印本、全文开放获取
- **适用场景**：物理、数学、计算机科学前沿研究
- **限制**：无引用数据、未经同行评审

### DBLP
- **优势**：计算机科学会议、期刊和技术报告覆盖稳定
- **适用场景**：计算机领域作者追踪、会议论文检索、经典系统论文
- **限制**：通常无摘要和被引数据

### BASE（实验入口）
- **优势**：开放获取资源覆盖广
- **适用场景**：欧洲高校和机构仓储补检
- **限制**：可能超时或受访问策略影响；仅显式 `--source base`

### 多源检索

```bash
search "topic" --source api --sort priority --limit 30
search "topic" --source api --async-search --sort priority --limit 30
search "topic" --source semantic --enable-fallback --limit 20
```

`api` 聚合 OpenAlex、Semantic Scholar、arXiv、NSSD、DBLP；BASE 不进入
聚合或 fallback。多源结果自动去重，但任何失败来源都必须保留在
`source_statuses`。

## 排序策略

### 按被引数（`--sort citations`）

适合查找经典、奠基性和高影响力线索：

```bash
search "deep learning" --source openalex --sort citations --limit 20
```

新论文被引数通常较低，因此该排序不适合单独追踪最新进展。

### 按时间（`--sort date`）

适合追踪最新研究和当前热点：

```bash
search "transformer architecture" --source openalex \
  --sort date --year-from 2023 --limit 15
```

最新不代表高质量，应结合年份、来源和原文核验。

### 按检索优先级（`--sort priority`）

用于安排元数据核验和精读顺序：

```bash
search "machine learning" --source openalex --sort priority --limit 20
```

评分维度：

- 摘要完整性：0-30
- DOI：20
- 被引次数：0-20，对数归一化
- 关键词：10
- 开放获取：10
- 基本题录完整性：5
- 年份新近性：0-10

参考区间：

- ≥80：元数据较完整，可优先核验
- 60-79：元数据完整性一般
- <60：可能较新、小众、无 DOI 或元数据不完整

该分数不评价研究设计、论证质量或学术价值。
