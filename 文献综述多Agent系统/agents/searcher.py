"""Searcher Agent：论文检索"""

import logging
import time
import config
from llm.client import LLMClient
from tools.paper_search import PaperSearchTool
from agents.base import BaseAgent

log = logging.getLogger(__name__)

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


class SearcherAgent(BaseAgent):
    """执行论文检索"""

    def __init__(self, llm: LLMClient):
        super().__init__(llm)
        self.search_tool = PaperSearchTool()

    def run(self, sub_directions: list[dict]) -> list[dict]:
        """为每个子方向搜索论文"""
        all_papers = []
        all_titles = set()

        for direction in sub_directions:
            keywords = direction.get("keywords", [])
            name = direction.get("name", "")

            for keyword in keywords:
                log.info(f"搜索: {keyword}")
                papers = self.search_tool.search(keyword, max_results=config.SEARCH_MAX_RESULTS)

                for paper in papers:
                    title = paper.get("title", "").strip().lower()
                    if title and title not in all_titles:
                        all_titles.add(title)
                        paper["sub_direction"] = name
                        paper["search_keyword"] = keyword
                        all_papers.append(paper)

                time.sleep(config.SEARCH_RATE_LIMIT_SEC)

        log.info(f"检索共获得 {len(all_papers)} 篇论文")
        return all_papers

    def filter_relevant(self, papers: list[dict], topic: str) -> list[dict]:
        """用LLM评估相关性，筛选高相关论文"""
        if not papers:
            return []

        # 分批评估
        batch_size = config.FILTER_BATCH_SIZE
        relevant = []

        for i in range(0, len(papers), batch_size):
            batch = papers[i:i+batch_size]
            paper_list = "\n".join([
                f"{j+1}. [{p.get('year', '')}] {p.get('title', '')} - {p.get('abstract', '')[:200]}"
                for j, p in enumerate(batch)
            ])

            result = self.llm.structured_output(
                messages=[{
                    "role": "user",
                    "content": f"研究主题：{topic}\n\n请评估以下论文的相关性：\n{paper_list}",
                }],
                system_prompt=SEARCHER_SYSTEM,
            )

            if "error" in result:
                log.warning(f"批次 {i//batch_size + 1} 相关性判断失败，保留全部 {len(batch)} 篇")
                relevant.extend(batch)
                continue

            judgments = result.get("relevance_judgments", [])
            for j, paper in enumerate(batch):
                if j < len(judgments) and judgments[j].get("relevance") in ["high", "medium"]:
                    paper["relevance_reason"] = judgments[j].get("reason", "")
                    relevant.append(paper)
                elif j >= len(judgments):
                    relevant.append(paper)  # 保底

        log.info(f"筛选后保留 {len(relevant)} 篇相关论文")
        return relevant
