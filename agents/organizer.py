"""Organizer Agent：聚类组织论文"""

import json
import logging
from llm.client import LLMClient

log = logging.getLogger(__name__)

ORGANIZER_SYSTEM = """你是一个科研文献组织专家。根据论文分析结果，进行聚类和分类。

输出 JSON 格式：
{
  "clusters": [
    {
      "name": "聚类名称",
      "description": "这个类别的总体描述",
      "papers": ["论文标题1", "论文标题2"],
      "sub_topics": ["子话题1", "子话题2"]
    }
  ],
  "timeline": [
    {"year": 年份, "milestone": "里程碑事件/论文"},
    ...
  ],
  "research_gaps": [
    {"gap": "研究空白", "description": "说明"}
  ]
}
"""


class OrganizerAgent:
    """论文聚类组织"""

    def __init__(self, llm: LLMClient):
        self.llm = llm

    def run(self, analyses: list[dict], survey_structure: list[str]) -> dict:
        """将分析结果聚类"""
        if not analyses:
            return {"clusters": [], "timeline": [], "research_gaps": []}

        analyses_text = "\n".join([
            f"{j+1}. 标题：{a.get('title', '')}\n"
            f"   方法：{a.get('method', '')[:200]}\n"
            f"   贡献：{a.get('contribution', '')[:200]}\n"
            f"   标签：{json.dumps(a.get('category_tags', []), ensure_ascii=False)}\n"
            f"   年份：{a.get('year', '')}"
            for j, a in enumerate(analyses)
        ])

        result = self.llm.structured_output(
            messages=[{
                "role": "user",
                "content": f"综述结构：{json.dumps(survey_structure, ensure_ascii=False)}\n\n"
                           f"请对以下论文分析结果进行聚类，并识别研究空白：\n\n{analyses_text}",
            }],
            system_prompt=ORGANIZER_SYSTEM,
        )

        log.info(f"聚类完成：{len(result.get('clusters', []))} 个类别")
        return result
