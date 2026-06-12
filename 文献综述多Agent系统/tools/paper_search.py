"""论文检索工具：Semantic Scholar + ArXiv"""

import time
import logging
import requests
import xml.etree.ElementTree as ET

log = logging.getLogger(__name__)

MAX_RETRIES = 3
REQUEST_TIMEOUT = 30


def _validate_query(query: str) -> str:
    """验证并清理搜索关键词"""
    if not query or not query.strip():
        raise ValueError("搜索关键词不能为空")
    return query.strip()


def _is_retryable_status(status_code: int) -> bool:
    """判断 HTTP 状态码是否可重试"""
    return status_code in (429, 500, 502, 503, 504)


def _wait_retry(attempt: int, base: float = 2.0):
    """指数退避等待"""
    time.sleep(base * (attempt + 1))


class PaperSearchTool:
    """多源论文检索"""

    def search(self, query: str, max_results: int = 20) -> list[dict]:
        """从多个来源检索论文，去重合并"""
        query = _validate_query(query)
        max_results = max(1, min(max_results, 100))
        all_papers = []

        # Semantic Scholar
        try:
            ss_papers = self._search_semantic_scholar(query, max_results)
            all_papers.extend(ss_papers)
            log.info(f"Semantic Scholar 返回 {len(ss_papers)} 篇")
        except Exception as e:
            log.warning(f"Semantic Scholar 搜索失败: {e}")

        # ArXiv
        try:
            arxiv_papers = self._search_arxiv(query, max_results // 2)
            all_papers.extend(arxiv_papers)
            log.info(f"ArXiv 返回 {len(arxiv_papers)} 篇")
        except Exception as e:
            log.warning(f"ArXiv 搜索失败: {e}")

        if not all_papers:
            log.warning(f"所有来源均未返回结果，关键词: {query}")
            return []

        # 去重（按title）
        seen = set()
        deduped = []
        for p in all_papers:
            key = p.get("title", "").lower().strip()
            if key and key not in seen:
                seen.add(key)
                deduped.append(p)

        log.info(f"去重后共 {len(deduped)} 篇论文")
        return deduped[:max_results]

    def _search_semantic_scholar(self, query: str, limit: int = 20) -> list[dict]:
        """Semantic Scholar API 搜索（带重试和退避）"""
        url = "https://api.semanticscholar.org/graph/v1/paper/search"
        params = {
            "query": query,
            "limit": min(limit, 100),
            "fields": "title,authors,year,abstract,externalIds,url,citationCount,venue,publicationDate",
        }

        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                resp = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)

                if resp.status_code == 200:
                    return self._parse_semantic_scholar_response(resp.json())

                if _is_retryable_status(resp.status_code):
                    wait = 3 * (attempt + 1)
                    log.warning(f"Semantic Scholar 返回 {resp.status_code} (第 {attempt + 1} 次)，等待 {wait}s")
                    last_error = RuntimeError(f"Semantic Scholar HTTP {resp.status_code}")
                    time.sleep(wait)
                    continue

                # 不可重试的错误
                log.warning(f"Semantic Scholar 返回 {resp.status_code}，不重试")
                return []

            except requests.Timeout:
                last_error = RuntimeError("Semantic Scholar 请求超时")
                log.warning(f"Semantic Scholar 超时 (第 {attempt + 1} 次)")
                _wait_retry(attempt)
                continue
            except requests.ConnectionError as e:
                last_error = RuntimeError(f"Semantic Scholar 连接失败: {e}")
                log.warning(f"Semantic Scholar 连接错误 (第 {attempt + 1} 次): {e}")
                _wait_retry(attempt)
                continue
            except Exception as e:
                last_error = RuntimeError(f"Semantic Scholar 未知错误: {e}")
                log.warning(f"Semantic Scholar 错误 (第 {attempt + 1} 次): {e}")
                _wait_retry(attempt)
                continue

        log.warning(f"Semantic Scholar 重试耗尽: {last_error}")
        return []

    @staticmethod
    def _parse_semantic_scholar_response(data: dict) -> list[dict]:
        """解析 Semantic Scholar API 响应"""
        papers = []
        for p in data.get("data", []):
            if not p.get("title"):
                continue
            papers.append({
                "id": p.get("paperId", ""),
                "title": p.get("title", ""),
                "year": p.get("year"),
                "abstract": p.get("abstract", ""),
                "authors": [a.get("name", "") for a in p.get("authors", [])],
                "url": p.get("url", ""),
                "citations": p.get("citationCount", 0),
                "venue": p.get("venue", ""),
                "date": p.get("publicationDate", ""),
                "source": "semantic_scholar",
                "external_ids": p.get("externalIds", {}),
            })
        return papers

    def _search_arxiv(self, query: str, max_results: int = 10) -> list[dict]:
        """ArXiv API 搜索（带重试）"""
        url = "https://export.arxiv.org/api/query"
        params = {
            "search_query": f"all:{query}",
            "start": 0,
            "max_results": max_results,
            "sortBy": "relevance",
            "sortOrder": "descending",
        }

        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                resp = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)

                if resp.status_code != 200:
                    if _is_retryable_status(resp.status_code):
                        last_error = RuntimeError(f"ArXiv HTTP {resp.status_code}")
                        log.warning(f"ArXiv 返回 {resp.status_code} (第 {attempt + 1} 次)")
                        _wait_retry(attempt)
                        continue
                    log.warning(f"ArXiv 返回 {resp.status_code}，不重试")
                    return []

                return self._parse_arxiv_response(resp.text)

            except requests.Timeout:
                last_error = RuntimeError("ArXiv 请求超时")
                log.warning(f"ArXiv 超时 (第 {attempt + 1} 次)")
                _wait_retry(attempt)
                continue
            except requests.ConnectionError as e:
                last_error = RuntimeError(f"ArXiv 连接失败: {e}")
                log.warning(f"ArXiv 连接错误 (第 {attempt + 1} 次): {e}")
                _wait_retry(attempt)
                continue
            except ET.ParseError as e:
                last_error = RuntimeError(f"ArXiv XML 解析失败: {e}")
                log.warning(f"ArXiv XML 解析错误 (第 {attempt + 1} 次): {e}")
                # XML 解析错误可能是内容不完整，重试可能有效
                _wait_retry(attempt)
                continue
            except Exception as e:
                last_error = RuntimeError(f"ArXiv 未知错误: {e}")
                log.warning(f"ArXiv 错误 (第 {attempt + 1} 次): {e}")
                _wait_retry(attempt)
                continue

        log.warning(f"ArXiv 重试耗尽: {last_error}")
        return []

    @staticmethod
    def _parse_arxiv_response(xml_text: str) -> list[dict]:
        """解析 ArXiv XML 响应"""
        root = ET.fromstring(xml_text)
        ns = {
            "atom": "http://www.w3.org/2005/Atom",
            "arxiv": "http://arxiv.org/schemas/atom",
        }

        papers = []
        for entry in root.findall("atom:entry", ns):
            title = entry.find("atom:title", ns)
            summary = entry.find("atom:summary", ns)
            published = entry.find("atom:published", ns)
            arxiv_id = entry.find("atom:id", ns)
            authors = entry.findall("atom:author", ns)

            title_text = title.text.strip().replace("\n", " ") if title is not None and title.text else ""
            if not title_text:
                continue

            papers.append({
                "id": arxiv_id.text.strip() if arxiv_id is not None and arxiv_id.text else "",
                "title": title_text,
                "abstract": summary.text.strip().replace("\n", " ") if summary is not None and summary.text else "",
                "authors": [
                    a.find("atom:name", ns).text
                    for a in authors
                    if a.find("atom:name", ns) is not None and a.find("atom:name", ns).text
                ],
                "year": published.text[:4] if published is not None and published.text else None,
                "date": published.text[:10] if published is not None and published.text else "",
                "url": arxiv_id.text.strip() if arxiv_id is not None and arxiv_id.text else "",
                "citations": 0,
                "venue": "arXiv",
                "source": "arxiv",
                "external_ids": {},
            })

        return papers
