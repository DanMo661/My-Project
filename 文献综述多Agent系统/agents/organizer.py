"""Organizer Agent：聚类组织论文"""

import json
import logging
import config
from llm.client import LLMClient
from agents.base import BaseAgent

log = logging.getLogger(__name__)

MAX_ANALYSES_PER_CALL = config.ORGANIZER_MAX_ANALYSES

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

ORGANIZER_MERGE_SYSTEM = """你是科研文献组织专家。现在有多个批次的聚类结果，请合并去重。

要求：
1. 合并相似的聚类（名称或主题接近的归为一组）
2. 合并时间线，按年份排序
3. 合并研究空白，去除重复项

输出格式与输入相同（clusters, timeline, research_gaps）。"""


def _format_analyses(analyses: list[dict]) -> str:
    """将分析列表格式化为文本"""
    return "\n".join([
        f"{j+1}. 标题：{a.get('title', '')}\n"
        f"   方法：{a.get('method', '')[:200]}\n"
        f"   贡献：{a.get('contribution', '')[:200]}\n"
        f"   标签：{json.dumps(a.get('category_tags', []), ensure_ascii=False)}\n"
        f"   年份：{a.get('year', '')}"
        for j, a in enumerate(analyses)
    ])


class OrganizerAgent(BaseAgent):
    """论文聚类组织"""

    def _cluster_batch(self, analyses: list[dict], survey_structure: list[str]) -> dict:
        """对单批分析结果聚类"""
        analyses_text = _format_analyses(analyses)

        result = self.llm.structured_output(
            messages=[{
                "role": "user",
                "content": f"综述结构：{json.dumps(survey_structure, ensure_ascii=False)}\n\n"
                           f"请对以下论文分析结果进行聚类，并识别研究空白：\n\n{analyses_text}",
            }],
            system_prompt=ORGANIZER_SYSTEM,
        )

        if "error" in result:
            log.warning("聚类失败，返回空结果")
            return {"clusters": [], "timeline": [], "research_gaps": []}
        return result

    def run(self, analyses: list[dict], survey_structure: list[str]) -> dict:
        """将分析结果聚类，超量时分批处理"""
        if not analyses:
            return {"clusters": [], "timeline": [], "research_gaps": []}

        if len(analyses) <= MAX_ANALYSES_PER_CALL:
            result = self._cluster_batch(analyses, survey_structure)
            log.info(f"聚类完成：{len(result.get('clusters', []))} 个类别")
            return result

        # 分批聚类
        log.info(f"论文数量 {len(analyses)} 超过 {MAX_ANALYSES_PER_CALL}，分批聚类")
        partial_results = []
        for i in range(0, len(analyses), MAX_ANALYSES_PER_CALL):
            chunk = analyses[i:i + MAX_ANALYSES_PER_CALL]
            log.info(f"  聚类批次 {i // MAX_ANALYSES_PER_CALL + 1}（{len(chunk)} 篇）")
            partial = self._cluster_batch(chunk, survey_structure)
            partial_results.append(partial)

        # 合并聚类结果
        merge_prompt = json.dumps(partial_results, ensure_ascii=False, indent=2)
        merged = self.llm.structured_output(
            messages=[{
                "role": "user",
                "content": f"请合并以下 {len(partial_results)} 个批次的聚类结果：\n\n{merge_prompt}",
            }],
            system_prompt=ORGANIZER_MERGE_SYSTEM,
        )

        if "error" in merged:
            log.warning("合并聚类失败，使用第一批结果")
            return partial_results[0]

        log.info(f"分批聚类合并完成：{len(merged.get('clusters', []))} 个类别")
        return merged
