"""Analyzer Agent：论文深度分析"""

from agents.base import BaseAgent
from errors import LLMParseError

from typing import TYPE_CHECKING, Optional, Any
if TYPE_CHECKING:
    from pipeline import PipelineExecutor

ANALYZER_SYSTEM = """你是一个论文分析专家。逐篇深度分析论文，提取关键信息。

输出 JSON 格式：
{
  "analyses": [
    {
      "title": "论文标题",
      "year": 年份,
      "authors": ["作者1", "作者2"],
      "research_problem": "要解决什么问题",
      "method": "提出的方法",
      "contribution": "核心贡献",
      "limitations": "局限性",
      "key_results": "关键结果/实验发现",
      "category_tags": ["方法类", "应用类"],
      "innovation_score": 1-5
    }
  ]
}
"""

_DEFAULTS = {
    "analyzer_batch_size": 5,
    "abstract_max_chars": 500,
}


def _make_placeholder(paper: dict) -> dict:
    return {
        "paper_id": paper.get("id", ""),
        "url": paper.get("url", ""),
        "title": paper.get("title", ""),
        "research_problem": "", "method": "", "contribution": "",
        "limitations": "", "key_results": "",
        "category_tags": [], "innovation_score": 0,
    }


class AnalyzerAgent(BaseAgent):
    """论文深度分析"""

    def __init__(self, llm, config: Optional[Any] = None):
        super().__init__(llm, config)

    def _cfg(self, key: str):
        if self.config and hasattr(self.config, key):
            return getattr(self.config, key)
        return _DEFAULTS[key]

    def run(self, papers: list[dict],
            pipeline: Optional["PipelineExecutor"] = None,
            stage_idx: int = 0) -> list[dict]:
        """分析论文，支持并行和顺序两种模式"""
        self.validate_papers(papers, "papers")

        batch_size = self._cfg("analyzer_batch_size")

        if pipeline and len(papers) > batch_size:
            return self._analyze_parallel(papers, pipeline, stage_idx, batch_size)

        return self._analyze_sequential(papers, batch_size)

    def _analyze_sequential(self, papers: list[dict],
                            batch_size: int) -> list[dict]:
        analyses = []
        max_chars = self._cfg("abstract_max_chars")

        for i in range(0, len(papers), batch_size):
            batch = papers[i:i + batch_size]
            batch_analyses = self._call_analyze_llm(batch, max_chars)

            if batch_analyses is None:
                self.report_progress("批次分析失败，尝试单篇重试", batch=i // batch_size + 1)
                for paper in batch:
                    single_result = self._retry_single_paper(paper, max_chars)
                    analyses.append(single_result)
                continue

            for j, paper in enumerate(batch):
                if j < len(batch_analyses):
                    analysis = batch_analyses[j]
                    analysis["paper_id"] = paper.get("id", "")
                    analysis["url"] = paper.get("url", "")
                    analyses.append(analysis)
                else:
                    self.report_progress("论文未被分析，重试单篇", title=paper.get("title", ""))
                    single_result = self._retry_single_paper(paper, max_chars)
                    analyses.append(single_result)

            self.report_progress("分析进度", analyzed=len(analyses), total=len(papers))

        return analyses

    def _analyze_parallel(self, papers: list[dict],
                          pipeline: "PipelineExecutor", stage_idx: int,
                          batch_size: int) -> list[dict]:
        max_chars = self._cfg("abstract_max_chars")
        batches = [papers[i:i + batch_size] for i in range(0, len(papers), batch_size)]

        def _analyze_batch(batch_info):
            batch_idx, batch = batch_info
            result = self._call_analyze_llm(batch, max_chars)
            return batch_idx, batch, result

        items = list(enumerate(batches))
        results = pipeline.run_parallel_batches(
            items, _analyze_batch, stage_idx, "深度分析论文", preserve_order=True,
        )

        analyses = []
        for item in results:
            if item is None:
                continue
            batch_idx, batch, batch_analyses = item

            if batch_analyses is None:
                self.report_progress("批次分析失败，尝试单篇重试", batch=batch_idx + 1)
                for paper in batch:
                    single_result = self._retry_single_paper(paper, max_chars)
                    analyses.append(single_result)
                continue

            for j, paper in enumerate(batch):
                if j < len(batch_analyses):
                    analysis = batch_analyses[j]
                    analysis["paper_id"] = paper.get("id", "")
                    analysis["url"] = paper.get("url", "")
                    analyses.append(analysis)
                else:
                    self.report_progress("论文未被分析，重试单篇", title=paper.get("title", ""))
                    single_result = self._retry_single_paper(paper, max_chars)
                    analyses.append(single_result)

        self.report_progress("并行分析完成", analyzed=len(analyses), total=len(papers))
        return analyses

    def _call_analyze_llm(self, batch: list[dict], max_chars: int) -> list[dict] | None:
        """调用 LLM 分析一批论文，失败返回 None"""
        paper_list = "\n".join([
            f"{j+1}. 标题：{p.get('title', '')}\n"
            f"   作者：{', '.join((p.get('authors') or [])[:5])}\n"
            f"   年份：{p.get('year', '')}\n"
            f"   摘要：{(p.get('abstract') or '')[:max_chars]}\n"
            f"   会议/期刊：{p.get('venue', '')}"
            for j, p in enumerate(batch)
        ])

        try:
            result = self.llm_structured(
                messages=[{
                    "role": "user",
                    "content": f"请逐篇分析以下论文：\n\n{paper_list}",
                }],
                system_prompt=ANALYZER_SYSTEM,
                required_keys=["analyses"],
            )
            return result.get("analyses", [])
        except (LLMParseError, ValueError):
            return None

    def _retry_single_paper(self, paper: dict, max_chars: int) -> dict:
        """单篇论文重试分析，最终失败返回占位记录"""
        paper_text = (
            f"标题：{paper.get('title', '')}\n"
            f"作者：{', '.join((paper.get('authors') or [])[:5])}\n"
            f"年份：{paper.get('year', '')}\n"
            f"摘要：{(paper.get('abstract') or '')[:max_chars]}\n"
            f"会议/期刊：{paper.get('venue', '')}"
        )
        try:
            result = self.llm_structured_safe(
                messages=[{"role": "user", "content": f"请分析以下论文：\n\n{paper_text}"}],
                system_prompt=ANALYZER_SYSTEM,
                fallback={"analyses": []},
                context=f"单篇重试: {paper.get('title', '')}",
                required_keys=["analyses"],
            )
            analyses = result.get("analyses", [])
            if analyses:
                analysis = analyses[0]
                analysis["paper_id"] = paper.get("id", "")
                analysis["url"] = paper.get("url", "")
                return analysis
        except Exception:
            pass

        self.report_progress("单篇分析最终失败，创建占位记录", title=paper.get("title", ""))
        return _make_placeholder(paper)
