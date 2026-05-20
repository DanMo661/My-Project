"""论文检索工具：Semantic Scholar + ArXiv"""

import time
import logging
import requests
import xml.etree.ElementTree as ET

log = logging.getLogger(__name__)


class PaperSearchTool:
    """多源论文检索"""

    def search(self, query: str, max_results: int = 20) -> list[dict]:
        """从多个来源检索论文，去重合并"""
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

    def _search_semantic_scholar(self, query: str, limit: int = 20,
                                  retries: int = 3) -> list[dict]:
        """Semantic Scholar API 搜索（带重试和退避）"""
        url = "https://api.semanticscholar.org/graph/v1/paper/search"
        params = {
            "query": query,
            "limit": min(limit, 100),
            "fields": "title,authors,year,abstract,externalIds,url,citationCount,venue,publicationDate",
        }

        for attempt in range(retries):
            try:
                resp = requests.get(url, params=params, timeout=30)

                if resp.status_code == 429:
                    if attempt >= 2:
                        log.warning("Semantic Scholar 限流，改用 arXiv 作为主要来源")
                        return []
                    wait = 3 * (attempt + 1)
                    log.warning(f"Semantic Scholar 限流，等待 {wait}s")
                    time.sleep(wait)
                    continue

                if resp.status_code != 200:
                    log.warning(f"Semantic Scholar 返回 {resp.status_code}")
                    if attempt < retries - 1:
                        time.sleep(2)
                        continue
                    return []

                data = resp.json()
                papers = []
                for p in data.get("data", []):
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

            except requests.Timeout:
                log.warning(f"Semantic Scholar 超时 (第{attempt+1}次重试)")
                time.sleep(3)
                continue
            except Exception as e:
                log.warning(f"Semantic Scholar 错误: {e}")
                if attempt < retries - 1:
                    time.sleep(2)
                    continue
                return []

        return []

    def _search_arxiv(self, query: str, max_results: int = 10) -> list[dict]:
        """ArXiv API 搜索"""
        url = "https://export.arxiv.org/api/query"
        params = {
            "search_query": f"all:{query}",
            "start": 0,
            "max_results": max_results,
            "sortBy": "relevance",
            "sortOrder": "descending",
        }
        resp = requests.get(url, params=params, timeout=30)

        papers = []
        root = ET.fromstring(resp.text)
        ns = {
            "atom": "http://www.w3.org/2005/Atom",
            "arxiv": "http://arxiv.org/schemas/atom",
        }

        for entry in root.findall("atom:entry", ns):
            title = entry.find("atom:title", ns)
            summary = entry.find("atom:summary", ns)
            published = entry.find("atom:published", ns)
            arxiv_id = entry.find("atom:id", ns)
            authors = entry.findall("atom:author", ns)

            papers.append({
                "id": arxiv_id.text.strip() if arxiv_id is not None else "",
                "title": title.text.strip().replace("\n", " ") if title is not None else "",
                "abstract": summary.text.strip().replace("\n", " ") if summary is not None else "",
                "authors": [a.find("atom:name", ns).text for a in authors if a.find("atom:name", ns) is not None],
                "year": published.text[:4] if published is not None else None,
                "date": published.text[:10] if published is not None else "",
                "url": arxiv_id.text.strip() if arxiv_id is not None else "",
                "citations": 0,
                "venue": "arXiv",
                "source": "arxiv",
                "external_ids": {},
            })

        return papers
