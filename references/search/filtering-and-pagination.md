# API 过滤、字段、分页与元数据

## 高级过滤

### 期刊过滤（`--journal-filter`）

用于限定期刊或期刊系列：

```bash
search "climate change" --source openalex \
  --journal-filter "Nature" --limit 20
search "CRISPR" --source openalex \
  --journal-filter "Science" --limit 15
```

使用大小写不敏感的子串匹配，`Nature` 会匹配 Nature 系列。所有 API
源均执行客户端过滤。

### 作者过滤（`--author-filter`）

```bash
search "neural networks" --source openalex \
  --author-filter "Hinton" --limit 20
search "deep learning" --source openalex \
  --author-filter "LeCun" --sort date --limit 10
```

OpenAlex 使用 API 过滤，Semantic Scholar 使用客户端过滤。优先使用姓氏，
避免姓名变体导致漏检。

### 学科过滤（`--field-of-study`）

```bash
search "object detection" --source openalex \
  --field-of-study "Computer Vision" --limit 20
search "language model" --source openalex \
  --field-of-study "Natural Language Processing" --limit 15
```

学科名使用英文。过滤可能排除跨学科论文。

### 组合过滤

```bash
search "deep learning" --source openalex \
  --year-from 2020 \
  --journal-filter "Nature" \
  --sort citations \
  --limit 20

search "neural networks" --source openalex \
  --author-filter "Hinton" \
  --field-of-study "Computer Vision" \
  --sort date \
  --limit 10

search "machine learning survey" --source openalex \
  --year-from 2020 \
  --sort priority \
  --limit 15
```

## 字段搜索

标题搜索减少摘要偶然提及造成的噪音：

```bash
search "BERT" --source openalex --field 篇名 --limit 10
```

摘要搜索适合定位方法和技术细节：

```bash
search "transformer architecture" --source openalex \
  --field 摘要 --limit 15
```

OpenAlex 可使用 API 级字段过滤，其他来源可能使用客户端过滤。标题过滤可能
漏掉标题未出现关键词但内容相关的论文。

## 分页

```bash
search "artificial intelligence" --source openalex --limit 20 --page 1
search "artificial intelligence" --source openalex --limit 20 --page 2
search "artificial intelligence" --source openalex --limit 20 --page 3
```

- 每页独立缓存。
- OpenAlex、Semantic Scholar 和 arXiv 支持分页。
- 先以 priority/citations 浏览 1-2 页，再按 date 补查最新论文。
- 后续页面排序较后不代表没有学术价值。

## 去重

多源聚合依次使用：

1. DOI 精确匹配。
2. 标题去标点、统一大小写后的匹配。
3. 保留首次出现的版本。

去重不保证保留元数据最完整版本，也不推断预印本与正式版本关系。

## 摘要完整度

OpenAlex 结果的 `abstract_quality`：

- `full`：摘要超过 200 字符。
- `partial`：1-200 字符。
- `none`：无摘要。

OpenAlex 缺摘要时可条件性尝试 Crossref。覆盖取决于 DOI 和上游记录；失败
不影响主搜索，但缺摘要条目不得作为全文证据。优先核验 `full`，其余需要
访问原文。
