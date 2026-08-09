"""
search_async.py - 异步并发 API 调用

使用 asyncio + httpx 实现异步版本的搜索函数，用于多源并发搜索。
实际耗时取决于网络、限流和上游响应。
"""

import asyncio
import sys
from typing import List, Dict, Any, Optional
import httpx

from core.search import (
    SearchSourceError,
    _semantic_scholar_headers,
    interleave_results_by_source,
    search_nssd as search_nssd_sync,
)


async def _http_get_async(url: str, params: Optional[Dict] = None,
                          headers: Optional[Dict] = None, timeout: int = 20,
                          source: str = "http") -> Dict:
    """异步 HTTP GET 请求"""
    try:
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            trust_env=False,
        ) as client:
            response = await client.get(url, params=params, headers=headers)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        print(f"[async] HTTP error {e.response.status_code}: {url}", file=sys.stderr)
        code = "API_RATE_LIMIT" if e.response.status_code == 429 else "SOURCE_HTTP_ERROR"
        raise SearchSourceError(
            source,
            code,
            f"{source} HTTP {e.response.status_code}",
            status_code=e.response.status_code,
        ) from e
    except httpx.RequestError as e:
        print(f"[async] Request error: {e}", file=sys.stderr)
        raise SearchSourceError(
            source,
            "SOURCE_UNAVAILABLE",
            f"{source} 请求失败: {e}",
        ) from e
    except Exception as e:
        print(f"[async] Unexpected error: {e}", file=sys.stderr)
        raise SearchSourceError(
            source,
            "SOURCE_SCHEMA_ERROR",
            f"{source} 响应解析失败: {e}",
        ) from e


def _invert_abstract(inverted_index: Optional[Dict] = None) -> str:
    """重建摘要文本（从 OpenAlex 的倒排索引）"""
    if not inverted_index:
        return ""
    word_positions = []
    for word, positions in inverted_index.items():
        for pos in positions:
            word_positions.append((pos, word))
    word_positions.sort()
    return " ".join(w for _, w in word_positions)


async def search_openalex_async(query: str, limit: int = 10,
                                 year_from: Optional[int] = None,
                                 year_to: Optional[int] = None,
                                 sort: str = "relevance",
                                 field: str = "default",
                                 journal: Optional[str] = None,
                                 author: Optional[str] = None,
                                 field_of_study: Optional[str] = None,
                                 page: int = 1) -> List[Dict[str, Any]]:
    """异步搜索 OpenAlex"""
    # 构建过滤器
    filters = []
    params = {
        "per_page": min(limit, 50),
        "page": page,
    }

    # 根据 field 参数调整搜索方式
    if field == "title":
        filters.append(f"display_name.search:{query}")
    elif field == "abstract":
        filters.append(f"abstract.search:{query}")
    else:
        params["search"] = query

    # 年份过滤
    if year_from:
        filters.append(f"from_publication_date:{year_from}-01-01")
    if year_to:
        filters.append(f"to_publication_date:{year_to}-12-31")
    if author:
        filters.append(f"authorships.author.display_name.search:{author}")
    if field_of_study:
        filters.append(f"concepts.display_name.search:{field_of_study}")

    if filters:
        params["filter"] = ",".join(filters)

    # 排序
    if sort == "citations":
        params["sort"] = "cited_by_count:desc"
    elif sort == "date":
        params["sort"] = "publication_date:desc"

    url = "https://api.openalex.org/works"
    data = await _http_get_async(url, params=params, source="openalex")

    if not isinstance(data, dict) or "results" not in data:
        raise SearchSourceError("openalex", "SOURCE_SCHEMA_ERROR", "OpenAlex 响应缺少 results")

    results = []
    for w in data.get("results", []):
        try:
            authors = ", ".join(
                a.get("author", {}).get("display_name", "")
                for a in w.get("authorships", [])
            )
            doi = w.get("doi", "")
            if doi and doi.startswith("https://doi.org/"):
                doi = doi[len("https://doi.org/"):]

            loc = w.get("primary_location") or {}
            src = loc.get("source") or {}

            # 关键词提取
            concepts = sorted(
                w.get("concepts", []),
                key=lambda x: x.get("score", 0),
                reverse=True
            )
            keywords = [
                c.get("display_name", "")
                for c in concepts
                if c.get("display_name") and c.get("score", 0) > 0.5
            ][:10]

            if not keywords:
                keywords = [
                    t.get("display_name", "")
                    for t in w.get("topics", [])[:5]
                    if t.get("display_name")
                ]

            abstract = _invert_abstract(w.get("abstract_inverted_index"))
            abstract_quality = "full" if len(abstract) > 200 else "partial" if abstract else "none"

            results.append({
                "title": w.get("title", ""),
                "authors": authors,
                "year": w.get("publication_year"),
                "journal": src.get("display_name", ""),
                "doi": doi,
                "cited_by": w.get("cited_by_count", 0),
                "url": w.get("id", ""),
                "abstract": abstract,
                "abstract_quality": abstract_quality,
                "is_oa": w.get("open_access", {}).get("is_oa", False),
                "oa_url": w.get("open_access", {}).get("oa_url", ""),
                "keywords": keywords,
                "source": "OpenAlex",
            })
        except Exception:
            continue

    # 客户端期刊过滤
    if journal:
        journal_lower = journal.lower()
        results = [r for r in results if journal_lower in r.get("journal", "").lower()]

    return results


async def search_semantic_scholar_async(query: str, limit: int = 10,
                                        year_from: Optional[int] = None,
                                        year_to: Optional[int] = None,
                                        sort: str = "relevance",
                                        field: str = "default",
                                        journal: Optional[str] = None,
                                        author: Optional[str] = None,
                                        field_of_study: Optional[str] = None,
                                        page: int = 1) -> List[Dict[str, Any]]:
    """异步搜索 Semantic Scholar"""
    offset = (page - 1) * limit

    params = {
        "query": query,
        "limit": min(limit, 100),
        "offset": offset,
        "fields": "title,authors,year,abstract,url,citationCount,externalIds,isOpenAccess,openAccessPdf,fieldsOfStudy,venue",
    }

    # 排序
    if sort == "citations":
        params["sort"] = "citationCount:desc"
    elif sort == "date":
        params["sort"] = "publicationDate:desc"

    # 年份过滤
    if year_from is not None or year_to is not None:
        if year_from is not None and year_to is not None:
            params["year"] = f"{year_from}-{year_to}"
        elif year_from is not None:
            params["year"] = f"{year_from}-"
        else:
            params["year"] = f"-{year_to}"

    url = "https://api.semanticscholar.org/graph/v1/paper/search"
    data = await _http_get_async(
        url,
        params=params,
        headers=_semantic_scholar_headers(),
        source="semantic_scholar",
    )

    if not isinstance(data, dict) or "data" not in data:
        raise SearchSourceError(
            "semantic_scholar",
            "SOURCE_SCHEMA_ERROR",
            "Semantic Scholar 响应缺少 data",
        )

    results = []
    for p in data.get("data", []):
        try:
            ext_ids = p.get("externalIds") or {}
            oa_pdf = p.get("openAccessPdf") or {}
            fos = p.get("fieldsOfStudy") or []

            # 关键词 fallback
            if not fos and p.get("title"):
                title_words = set(p.get("title", "").lower().split())
                stopwords = {"the", "a", "an", "of", "in", "on", "for", "with", "to", "and", "or", "from", "by", "at", "as"}
                fos = [w for w in title_words if len(w) > 3 and w not in stopwords][:5]

            venue = p.get("venue", "") or ""

            results.append({
                "title": p.get("title", ""),
                "authors": ", ".join(a.get("name", "") for a in p.get("authors", [])),
                "year": p.get("year"),
                "journal": venue,
                "doi": ext_ids.get("DOI", ""),
                "arxiv_id": ext_ids.get("ArXiv", ""),
                "cited_by": p.get("citationCount", 0),
                "url": p.get("url", ""),
                "abstract": p.get("abstract", "") or "",
                "keywords": fos,
                "is_oa": p.get("isOpenAccess", False),
                "oa_url": oa_pdf.get("url", ""),
                "source": "Semantic Scholar",
            })
        except Exception:
            continue

    # 客户端过滤
    if field == "title":
        query_lower = query.lower()
        results = [r for r in results if query_lower in r.get("title", "").lower()]
    elif field == "abstract":
        query_lower = query.lower()
        results = [r for r in results if query_lower in r.get("abstract", "").lower()]

    if journal:
        journal_lower = journal.lower()
        results = [r for r in results if journal_lower in r.get("journal", "").lower()]

    if author:
        author_lower = author.lower()
        results = [r for r in results if author_lower in r.get("authors", "").lower()]

    return results


async def search_arxiv_async(query: str, limit: int = 10,
                             sort_by: str = "relevance",
                             year_from: Optional[int] = None,
                             year_to: Optional[int] = None,
                             page: int = 1) -> List[Dict[str, Any]]:
    """异步搜索 arXiv"""
    import xml.etree.ElementTree as ET

    sort_map = {"relevance": "relevance", "date": "lastUpdatedDate"}
    sort_param = sort_map.get(sort_by, "relevance")
    start = (page - 1) * limit

    params = {
        "search_query": f"all:{query}",
        "start": start,
        "max_results": min(limit, 50),
        "sortBy": sort_param,
        "sortOrder": "descending",
    }

    url = "https://export.arxiv.org/api/query"

    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            xml_text = response.text
    except SearchSourceError:
        raise
    except Exception as e:
        print(f"[async] arXiv error: {e}", file=sys.stderr)
        raise SearchSourceError("arxiv", "SOURCE_UNAVAILABLE", f"arXiv 请求失败: {e}") from e

    # 解析 XML
    try:
        root = ET.fromstring(xml_text)
    except Exception as e:
        raise SearchSourceError("arxiv", "SOURCE_SCHEMA_ERROR", f"arXiv XML 解析失败: {e}") from e

    ns = {"atom": "http://www.w3.org/2005/Atom"}
    arxiv_ns = {"arxiv": "http://arxiv.org/schemas/atom"}
    entries = root.findall("atom:entry", ns)

    results = []
    for entry in entries:
        try:
            title = (entry.findtext("atom:title", "", ns) or "").strip().replace("\n", " ")
            summary = (entry.findtext("atom:summary", "", ns) or "").strip().replace("\n", " ")
            authors = ", ".join(
                (a.findtext("atom:name", "", ns) or "")
                for a in entry.findall("atom:author", ns)
            )
            published = entry.findtext("atom:published", "", ns)
            year = int(published[:4]) if published and len(published) >= 4 else None

            arxiv_id = ""
            entry_id = entry.findtext("atom:id", "", ns) or ""
            if "arxiv.org/abs/" in entry_id:
                arxiv_id = entry_id.split("arxiv.org/abs/")[-1]

            pdf_url = ""
            for link in entry.findall("atom:link", ns):
                if link.get("title") == "pdf":
                    pdf_url = link.get("href", "")
                    break

            categories = []
            for cat in entry.findall("atom:category", ns):
                term = cat.get("term", "")
                if term:
                    categories.append(term)
            if not categories:
                for cat in entry.findall("arxiv:primary_category", arxiv_ns):
                    term = cat.get("term", "")
                    if term:
                        categories.append(term)

            # 年份过滤
            if year_from and year and year < year_from:
                continue
            if year_to and year and year > year_to:
                continue

            results.append({
                "title": title,
                "authors": authors,
                "year": year,
                "journal": "arXiv preprint",
                "doi": "",
                "arxiv_id": arxiv_id,
                "cited_by": 0,
                "url": entry_id,
                "abstract": summary,
                "keywords": categories,
                "is_oa": True,
                "oa_url": pdf_url,
                "source": "arXiv",
            })
        except Exception:
            continue

    return results


async def search_nssd_async(query: str, limit: int = 10,
                           year_from: Optional[int] = None,
                           year_to: Optional[int] = None) -> List[Dict[str, Any]]:
    """并发调度中在线程执行 NSSD 的同步表单接口。"""
    return await asyncio.to_thread(
        search_nssd_sync,
        query,
        limit,
        year_from,
        year_to,
    )


async def search_dblp_async(query: str, limit: int = 10,
                           year_from: Optional[int] = None,
                           year_to: Optional[int] = None) -> List[Dict[str, Any]]:
    """异步搜索 DBLP（计算机科学文献数据库）"""
    params = {
        "q": query,
        "h": min(limit, 100),
        "format": "json",
    }

    url = "https://dblp.org/search/publ/api"
    data = await _http_get_async(url, params=params, source="dblp")

    if not isinstance(data, dict) or "result" not in data:
        raise SearchSourceError("dblp", "SOURCE_SCHEMA_ERROR", "DBLP 响应缺少 result")

    hits = data.get("result", {}).get("hits", {}).get("hit", [])
    if not hits:
        return []

    results = []
    for hit in hits:
        try:
            info = hit.get("info", {})

            # 解析作者
            authors_data = info.get("authors", {}).get("author", [])
            if isinstance(authors_data, dict):
                authors_data = [authors_data]
            authors = ", ".join(a.get("text", "") if isinstance(a, dict) else str(a) for a in authors_data)

            # 解析年份
            year = info.get("year")
            if year:
                try:
                    year = int(year)
                except (ValueError, TypeError):
                    year = None

            # 年份过滤
            if year_from and year and year < year_from:
                continue
            if year_to and year and year > year_to:
                continue

            venue = info.get("venue", "")
            doi = info.get("doi", "")
            url = info.get("url", "")
            ee = info.get("ee", "")
            doc_type = info.get("type", "")

            results.append({
                "title": info.get("title", ""),
                "authors": authors,
                "year": year,
                "journal": venue,
                "doi": doi,
                "cited_by": 0,
                "url": url,
                "abstract": "",
                "keywords": [doc_type] if doc_type else [],
                "is_oa": bool(ee),
                "oa_url": ee if isinstance(ee, str) else "",
                "source": "DBLP",
                "doc_type": doc_type,
            })
        except Exception:
            continue

    return results


async def search_base_async(query: str, limit: int = 10,
                            year_from: Optional[int] = None,
                            year_to: Optional[int] = None) -> List[Dict[str, Any]]:
    """Async search for BASE."""
    params = {
        "func": "PerformSearch",
        "query": query,
        "hits": min(limit, 50),
        "format": "json",
    }
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }

    data = await _http_get_async(
        "https://api.base-search.net/cgi-bin/BaseHttpSearchInterface.fcgi",
        params=params,
        headers=headers,
        source="base",
    )
    if isinstance(data, dict) and "error" in data:
        raise SearchSourceError("base", "SOURCE_UNAVAILABLE", f"BASE API: {data.get('error')}")
    if not isinstance(data, dict) or "response" not in data:
        raise SearchSourceError("base", "SOURCE_SCHEMA_ERROR", "BASE 响应缺少 response")

    docs = data.get("response", {}).get("docs", [])
    results = []
    for doc in docs:
        try:
            authors_data = doc.get("dcauthor", [])
            if isinstance(authors_data, str):
                authors_data = [authors_data]
            authors = ", ".join(authors_data)

            year = None
            year_data = doc.get("dcyear")
            if year_data:
                try:
                    year = int(year_data[0]) if isinstance(year_data, list) else int(year_data)
                except (ValueError, TypeError, IndexError):
                    year = None

            if year_from and year and year < year_from:
                continue
            if year_to and year and year > year_to:
                continue

            title_data = doc.get("dctitle", [])
            title = title_data[0] if isinstance(title_data, list) and title_data else str(title_data) if title_data else ""

            abstract_data = doc.get("dcdescription", [])
            abstract = abstract_data[0] if isinstance(abstract_data, list) and abstract_data else str(abstract_data) if abstract_data else ""

            source_data = doc.get("dcsource", [])
            journal = source_data[0] if isinstance(source_data, list) and source_data else str(source_data) if source_data else ""

            doi_data = doc.get("dcdoi", [])
            doi = doi_data[0] if isinstance(doi_data, list) and doi_data else str(doi_data) if doi_data else ""

            link_data = doc.get("dclink", [])
            url = link_data[0] if isinstance(link_data, list) and link_data else str(link_data) if link_data else ""

            subject_data = doc.get("dcsubject", [])
            if isinstance(subject_data, str):
                subject_data = [subject_data]

            results.append({
                "title": title,
                "authors": authors,
                "year": year,
                "journal": journal,
                "doi": doi,
                "cited_by": 0,
                "url": url,
                "abstract": abstract,
                "keywords": subject_data[:10] if subject_data else [],
                "is_oa": True,
                "oa_url": url,
                "source": "BASE",
            })
        except Exception:
            continue

    return results


async def search_all_async(query: str, limit: int = 10,
                          year_from: Optional[int] = None,
                          year_to: Optional[int] = None,
                          sort: str = "relevance",
                          sources: Optional[List[str]] = None,
                          field: str = "default",
                          journal: Optional[str] = None,
                          author: Optional[str] = None,
                          field_of_study: Optional[str] = None,
                          page: int = 1) -> Dict[str, Any]:
    """
    异步并发搜索多个数据源

    Args:
        query: 搜索关键词
        limit: 每个数据源的结果数量
        year_from: 起始年份
        year_to: 截止年份
        sort: 排序方式
        sources: 数据源列表，默认 ["openalex", "semantic_scholar", "arxiv", "nssd"]

    Returns:
        {"results": List[Dict], "sources_used": List[str], "elapsed_ms": int}
    """
    import time

    if sources is None:
        sources = ["openalex", "semantic_scholar", "arxiv", "nssd", "dblp"]

    start_time = time.time()

    # 创建并发任务
    tasks = []
    source_names = []

    if "openalex" in sources:
        tasks.append(search_openalex_async(
            query,
            limit,
            year_from,
            year_to,
            sort,
            field=field,
            journal=journal,
            author=author,
            field_of_study=field_of_study,
            page=page,
        ))
        source_names.append("openalex")

    if "semantic_scholar" in sources:
        tasks.append(search_semantic_scholar_async(
            query,
            limit,
            year_from,
            year_to,
            sort,
            field=field,
            journal=journal,
            author=author,
            field_of_study=field_of_study,
            page=page,
        ))
        source_names.append("semantic_scholar")

    if "arxiv" in sources:
        tasks.append(search_arxiv_async(
            query,
            limit,
            sort,
            year_from,
            year_to,
            page=page,
        ))
        source_names.append("arxiv")

    if "nssd" in sources:
        tasks.append(search_nssd_async(query, limit, year_from, year_to))
        source_names.append("nssd")

    if "dblp" in sources:
        tasks.append(search_dblp_async(query, limit, year_from, year_to))
        source_names.append("dblp")

    if "base" in sources:
        tasks.append(search_base_async(query, limit, year_from, year_to))
        source_names.append("base")

    # 并发执行
    results_list = await asyncio.gather(*tasks, return_exceptions=True)

    # 合并结果
    all_results = []
    sources_used = []
    source_statuses = {}

    for i, result in enumerate(results_list):
        source_name = source_names[i]
        if isinstance(result, Exception):
            print(f"[async] {source_name} failed: {result}", file=sys.stderr)
            if isinstance(result, SearchSourceError):
                source_statuses[source_name] = result.as_dict()
            else:
                source_statuses[source_name] = {
                    "status": "error",
                    "code": "SOURCE_UNAVAILABLE",
                    "message": str(result),
                }
            continue

        if result:
            all_results.extend(result)
            sources_used.append(source_name)
            source_statuses[source_name] = {
                "status": "success",
                "count": len(result),
            }
        else:
            source_statuses[source_name] = {
                "status": "empty",
                "count": 0,
            }

    all_results = interleave_results_by_source(all_results)
    elapsed_ms = int((time.time() - start_time) * 1000)

    return {
        "results": all_results,
        "sources_used": sources_used,
        "source_statuses": source_statuses,
        "elapsed_ms": elapsed_ms,
        "count": len(all_results)
    }


def search_all_sync(query: str, limit: int = 10,
                   year_from: Optional[int] = None,
                   year_to: Optional[int] = None,
                   sort: str = "relevance",
                   sources: Optional[List[str]] = None,
                   field: str = "default",
                   journal: Optional[str] = None,
                   author: Optional[str] = None,
                   field_of_study: Optional[str] = None,
                   page: int = 1) -> Dict[str, Any]:
    """
    同步包装器：在同步代码中调用异步搜索

    用法：
        result = search_all_sync("machine learning", limit=10)
        papers = result["results"]
    """
    return asyncio.run(search_all_async(
        query,
        limit,
        year_from,
        year_to,
        sort,
        sources,
        field=field,
        journal=journal,
        author=author,
        field_of_study=field_of_study,
        page=page,
    ))
