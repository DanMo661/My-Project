"""Analyzer Agent：论文深度分析"""

import logging
import config
from llm.client import LLMClient
from agents.base import BaseAgent

log = logging.getLogger(__name__)

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


class AnalyzerAgent(BaseAgent):
    """论文深度分析"""

    def run(self, papers: list[dict]) -> list[dict]:
        """逐篇分析论文"""
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

            result = self.llm.structured_output(
                messages=[{
                    "role": "user",
                    "content": f"请逐篇分析以下论文：\n\n{paper_list}",
                }],
                system_prompt=ANALYZER_SYSTEM,
            )

            batch_analyses = result.get("analyses", [])
            if "error" in result:
                log.warning(f"批次 {i//batch_size + 1} 分析失败，跳过")
                continue

            for j, paper in enumerate(batch):
                if j < len(batch_analyses):
                    analysis = batch_analyses[j]
                    analysis["paper_id"] = paper.get("id", "")
                    analysis["url"] = paper.get("url", "")
                    analyses.append(analysis)
                else:
                    log.warning(f"论文 '{paper.get('title', '')}' 未被 LLM 分析，创建占位记录")
                    analyses.append({
                        "paper_id": paper.get("id", ""),
                        "url": paper.get("url", ""),
                        "title": paper.get("title", ""),
                        "research_problem": "", "method": "", "contribution": "",
                        "limitations": "", "key_results": "",
                        "category_tags": [], "innovation_score": 0,
                    })

            log.info(f"已分析 {len(analyses)}/{len(papers)} 篇")

        return analyses
