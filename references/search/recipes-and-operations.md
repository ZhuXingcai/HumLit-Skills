# API 检索工作流与运行建议

## 综述检索

```bash
# 经典高引线索
search "deep learning" --source openalex \
  --sort citations --year-from 2015 --limit 20

# 最新进展
search "deep learning" --source openalex \
  --sort date --year-from 2023 --limit 15

# 元数据完整、便于优先核验的线索
search "deep learning applications" --source openalex \
  --sort priority --limit 10
```

## 特定主题深度检索

```bash
# 先宽后窄
search "transformer model" --source openalex --sort priority --limit 30

search "transformer model" --source openalex \
  --journal-filter "Nature" \
  --year-from 2020 \
  --sort citations \
  --limit 15

# 追踪作者
search "transformer" --source openalex \
  --author-filter "Vaswani" \
  --sort date \
  --limit 10
```

## 跨学科检索

```bash
search "AI in healthcare" --source api --sort priority --limit 30

search "AI in healthcare" --source openalex \
  --field-of-study "Medicine" \
  --year-from 2020 \
  --limit 20

search "AI in healthcare" --source openalex \
  --journal-filter "Nature Medicine" \
  --sort citations \
  --limit 15
```

## 常见问题

### 期刊过滤结果很少

确认期刊名拼写。过滤使用子串匹配，但错误缩写不会自动纠正。

### 作者过滤没有结果

确认拼写并尝试只使用姓氏。作者可能使用不同姓名变体。

### priority 较低是否不值得阅读

不是。低分可能来自新发表、预印本、无 DOI、小众主题或元数据不完整。

### 如何平衡全面性与精确性

1. 覆盖优先：`--source api`，少加过滤，但不声称穷尽所有数据库。
2. 精确优先：组合年份、期刊、作者和学科过滤。
3. 通常先宽泛检索，再逐步缩小。

### 分页如何减少遗漏

第 1 页使用 priority/citations，浏览 2-3 页后再切换 date 补查最新研究。

## 性能与缓存

- 搜索结果按 `cache_ttl_days` 缓存，默认 30 天。
- 查询参数和页码相同才可能直接命中缓存。
- 单源和多源耗时取决于网络、限流和上游响应。
- `--source api --async-search` 通常快于顺序执行，但不承诺固定提升。
- NSSD 在线程中并发调度，仍可能成为慢源。
- 大量结果优先分页，不要无限增加 `--limit`。

## 快速选择

| 需求 | 参数 |
|------|------|
| 经典线索 | `--sort citations --year-from 2015` |
| 最新进展 | `--sort date --year-from 2023` |
| 优先核验 | `--sort priority` |
| 期刊 | `--journal-filter "Nature"` |
| 作者 | `--author-filter "姓氏"` |
| 精确标题 | `--field 篇名` |
| 综合检索 | `--source api --async-search --sort priority` |
| 后续页面 | `--page 2` |

相关说明：

- [数据源与排序](api-sources-and-ranking.md)
- [过滤、分页与元数据](filtering-and-pagination.md)
- [工作流索引](../workflows.md)
