"""Searcher Agent：论文检索"""

import time
from tools.paper_search import PaperSearchTool
from agents.base import BaseAgent
from errors import LLMParseError

from typing import TYPE_CHECKING, Optional, Any
if TYPE_CHECKING:
    from pipeline import PipelineExecutor

SEARCHER_SYSTEM = """你是一个论文检索专家。你的职责是：
1. 将中文搜索意图转换为精准的英文搜索词
2. 评估搜索结果的相关性
3. 为每篇论文判断是否与主题相关

输出 JSON 格式：
{
  "search_queries": ["英文搜索词1", "英文搜索词2"],
  "relevance_judgments": [
    {
      "title": "论文标题",
      "relevance": "high/medium/low",
      "reason": "相关原因"
    }
  ]
}
"""

_DEFAULTS = {
    "search_max_results": 8,
    "filter_batch_size": 15,
    "search_rate_limit_sec": 1.5,
}


class SearcherAgent(BaseAgent):
    """执行论文检索"""

    def __init__(self, llm, config: Optional[Any] = None):
        super().__init__(llm, config)
        self.search_tool = PaperSearchTool()

    def _cfg(self, key: str):
        if self.config and hasattr(self.config, key):
            return getattr(self.config, key)
        return _DEFAULTS[key]

    def run(self, sub_directions: list[dict],
            pipeline: Optional["PipelineExecutor"] = None,
            stage_idx: int = 0) -> list[dict]:
        """为每个子方向搜索论文"""
        self.validate_non_empty_list(sub_directions, "sub_directions")

        all_papers = []
        all_titles = set()
        max_results = self._cfg("search_max_results")
        rate_limit = self._cfg("search_rate_limit_sec")

        for direction in sub_directions:
            keywords = direction.get("keywords", [])
            name = direction.get("name", "")
            if not keywords:
                self.report_progress("子方向无关键词，跳过", direction=name)
                continue

            for keyword in keywords:
                self.report_progress("搜索", keyword=keyword)
                papers = self.search_tool.search(keyword, max_results=max_results)

                for paper in papers:
                    title = paper.get("title", "").strip().lower()
                    if title and title not in all_titles:
                        all_titles.add(title)
                        paper["sub_direction"] = name
                        paper["search_keyword"] = keyword
                        all_papers.append(paper)

                time.sleep(rate_limit)

        self.report_progress("检索完成", total_papers=len(all_papers))
        return all_papers

    def filter_papers(self, papers: list[dict], topic: str,
                      pipeline: Optional["PipelineExecutor"] = None,
                      stage_idx: int = 0) -> list[dict]:
        """筛选相关论文，支持并行和顺序两种模式"""
        if not papers:
            return []

        batch_size = self._cfg("filter_batch_size")

        if pipeline and len(papers) > batch_size:
            return self._filter_parallel(papers, topic, pipeline, stage_idx, batch_size)

        return self._filter_sequential(papers, topic, batch_size)

    def _filter_sequential(self, papers: list[dict], topic: str,
                           batch_size: int) -> list[dict]:
        relevant = []
        for i in range(0, len(papers), batch_size):
            batch = papers[i:i + batch_size]
            result = self._call_filter_llm(batch, topic)
            if result is None:
                relevant.extend(batch)
                continue
            relevant.extend(self._extract_relevant(batch, result))

        self.report_progress("筛选完成", relevant_count=len(relevant))
        return relevant

    def _filter_parallel(self, papers: list[dict], topic: str,
                         pipeline: "PipelineExecutor", stage_idx: int,
                         batch_size: int) -> list[dict]:
        batches = [papers[i:i + batch_size] for i in range(0, len(papers), batch_size)]

        def _filter_batch(batch_info):
            batch_idx, batch = batch_info
            result = self._call_filter_llm(batch, topic)
            return (batch_idx, batch, result)

        items = list(enumerate(batches))
        results = pipeline.run_parallel_batches(
            items, _filter_batch, stage_idx, "筛选相关论文", preserve_order=True,
        )

        relevant = []
        for item in results:
            if item is None:
                continue
            batch_idx, batch, result = item
            if result is None:
                self.report_progress(
                    "相关性判断失败，保留全部论文",
                    batch=batch_idx + 1,
                    count=len(batch),
                )
                relevant.extend(batch)
                continue
            relevant.extend(self._extract_relevant(batch, result))

        self.report_progress("筛选完成", relevant_count=len(relevant))
        return relevant

    def _call_filter_llm(self, batch: list[dict], topic: str) -> Optional[dict]:
        paper_list = "\n".join([
            f"{j+1}. [{p.get('year', '')}] {p.get('title', '')} - {(p.get('abstract') or '')[:200]}"
            for j, p in enumerate(batch)
        ])
        try:
            return self.llm_structured(
                messages=[{
                    "role": "user",
                    "content": f"研究主题：{topic}\n\n请评估以下论文的相关性：\n{paper_list}",
                }],
                system_prompt=SEARCHER_SYSTEM,
                required_keys=["relevance_judgments"],
            )
        except (LLMParseError, ValueError):
            return None

    @staticmethod
    def _extract_relevant(batch: list[dict], result: dict) -> list[dict]:
        """从 LLM 结果中提取相关论文"""
        relevant = []
        judgments = result.get("relevance_judgments", [])
        for j, paper in enumerate(batch):
            if j < len(judgments) and judgments[j].get("relevance") in ["high", "medium"]:
                paper["relevance_reason"] = judgments[j].get("reason", "")
                relevant.append(paper)
            elif j >= len(judgments):
                relevant.append(paper)
        return relevant
