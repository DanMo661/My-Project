"""Analyzer Agent：论文深度分析"""

import config
from agents.base import BaseAgent
from errors import LLMParseError

from typing import TYPE_CHECKING
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


def _make_placeholder(paper: dict) -> dict:
    """为 LLM 未覆盖的论文创建占位分析记录"""
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

    def run(self, papers: list[dict]) -> list[dict]:
        """逐篇分析论文"""
        self.validate_papers(papers, "papers")

        analyses = []
        batch_size = config.ANALYZER_BATCH_SIZE

        for i in range(0, len(papers), batch_size):
            batch = papers[i:i+batch_size]
            paper_list = "\n".join([
                f"{j+1}. 标题：{p.get('title', '')}\n"
                f"   作者：{', '.join(p.get('authors', [])[:5])}\n"
                f"   年份：{p.get('year', '')}\n"
                f"   摘要：{p.get('abstract', '')[:config.ABSTRACT_MAX_CHARS]}\n"
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
            except (LLMParseError, ValueError):
                self.report_progress(
                    "批次分析失败，跳过",
                    batch=i // batch_size + 1,
                )
                continue

            batch_analyses = result.get("analyses", [])
            for j, paper in enumerate(batch):
                if j < len(batch_analyses):
                    analysis = batch_analyses[j]
                    analysis["paper_id"] = paper.get("id", "")
                    analysis["url"] = paper.get("url", "")
                    analyses.append(analysis)
                else:
                    self.report_progress(
                        "论文未被分析，创建占位记录",
                        title=paper.get("title", ""),
                    )
                    analyses.append(_make_placeholder(paper))

            self.report_progress(
                "分析进度",
                analyzed=len(analyses),
                total=len(papers),
            )

        return analyses

    def analyze_parallel(self, papers: list[dict],
                         pipeline: "PipelineExecutor", stage_idx: int) -> list[dict]:
        """并行分析论文批次"""
        if not papers:
            return []

        batch_size = config.ANALYZER_BATCH_SIZE
        batches = [papers[i:i + batch_size] for i in range(0, len(papers), batch_size)]

        def _analyze_batch(batch_info):
            batch_idx, batch = batch_info
            paper_list = "\n".join([
                f"{j + 1}. 标题：{p.get('title', '')}\n"
                f"   作者：{', '.join(p.get('authors', [])[:5])}\n"
                f"   年份：{p.get('year', '')}\n"
                f"   摘要：{p.get('abstract', '')[:config.ABSTRACT_MAX_CHARS]}\n"
                f"   会议/期刊：{p.get('venue', '')}"
                for j, p in enumerate(batch)
            ])
            result = self.llm.structured_output(
                messages=[{
                    "role": "user",
                    "content": f"请逐篇分析以下论文：\n\n{paper_list}",
                }],
                system_prompt=ANALYZER_SYSTEM,
            )
            return batch_idx, batch, result

        items = list(enumerate(batches))
        results = pipeline.run_parallel_batches(
            items, _analyze_batch, stage_idx, "深度分析论文", preserve_order=True,
        )

        analyses = []
        for item in results:
            if item is None:
                continue
            batch_idx, batch, result = item

            # 并行结果可能直接是 dict、也可能是 Exception
            if isinstance(result, Exception) or not isinstance(result, dict):
                self.report_progress("批次分析失败，跳过", batch=batch_idx + 1)
                continue

            batch_analyses = result.get("analyses", [])
            for j, paper in enumerate(batch):
                if j < len(batch_analyses):
                    analysis = batch_analyses[j]
                    analysis["paper_id"] = paper.get("id", "")
                    analysis["url"] = paper.get("url", "")
                    analyses.append(analysis)
                else:
                    self.report_progress(
                        "论文未被分析，创建占位记录",
                        title=paper.get("title", ""),
                    )
                    analyses.append(_make_placeholder(paper))

        self.report_progress(
            "并行分析完成",
            analyzed=len(analyses),
            total=len(papers),
        )
        return analyses
