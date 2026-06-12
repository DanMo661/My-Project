"""Organizer Agent：聚类组织论文"""

import json
from agents.base import BaseAgent

from typing import TYPE_CHECKING, Optional, Any
if TYPE_CHECKING:
    from pipeline import PipelineExecutor

_DEFAULTS = {
    "organizer_max_analyses": 30,
}

_EMPTY_CLUSTER = {"clusters": [], "timeline": [], "research_gaps": []}

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
    return "\n".join([
        f"{j+1}. 标题：{a.get('title', '')}\n"
        f"   方法：{(a.get('method') or '')[:200]}\n"
        f"   贡献：{(a.get('contribution') or '')[:200]}\n"
        f"   标签：{json.dumps(a.get('category_tags', []), ensure_ascii=False)}\n"
        f"   年份：{a.get('year', '')}"
        for j, a in enumerate(analyses)
    ])


class OrganizerAgent(BaseAgent):
    """论文聚类组织"""

    def __init__(self, llm, config: Optional[Any] = None):
        super().__init__(llm, config)

    def _cfg(self, key: str):
        if self.config and hasattr(self.config, key):
            return getattr(self.config, key)
        return _DEFAULTS[key]

    def _cluster_batch(self, analyses: list[dict], survey_structure: list[str]) -> dict:
        analyses_text = _format_analyses(analyses)
        return self.llm_structured_safe(
            messages=[{
                "role": "user",
                "content": f"综述结构：{json.dumps(survey_structure, ensure_ascii=False)}\n\n"
                           f"请对以下论文分析结果进行聚类，并识别研究空白：\n\n{analyses_text}",
            }],
            system_prompt=ORGANIZER_SYSTEM,
            fallback=_EMPTY_CLUSTER,
            context="聚类",
        )

    def run(self, analyses: list[dict], survey_structure: list[str],
            pipeline: Optional["PipelineExecutor"] = None,
            stage_idx: int = 0) -> dict:
        """将分析结果聚类，支持并行和顺序两种模式"""
        if not analyses:
            return _EMPTY_CLUSTER

        max_per_call = self._cfg("organizer_max_analyses")

        if len(analyses) <= max_per_call:
            if pipeline:
                pipeline.progress.start_stage(stage_idx, "聚类分类", 1)
            result = self._cluster_batch(analyses, survey_structure)
            if pipeline:
                pipeline.progress.advance(stage_idx, 1)
                pipeline.progress.finish_stage(stage_idx)
            self.report_progress("聚类完成", clusters=len(result.get("clusters", [])))
            return result

        if pipeline:
            return self._organize_parallel(analyses, survey_structure, pipeline, stage_idx, max_per_call)

        return self._organize_sequential(analyses, survey_structure, max_per_call)

    def _organize_sequential(self, analyses: list[dict], survey_structure: list[str],
                             max_per_call: int) -> dict:
        self.report_progress(
            "论文数量超限，分批聚类",
            total=len(analyses),
            threshold=max_per_call,
        )
        partial_results = []
        for i in range(0, len(analyses), max_per_call):
            chunk = analyses[i:i + max_per_call]
            self.report_progress("聚类批次", batch=i // max_per_call + 1, count=len(chunk))
            partial = self._cluster_batch(chunk, survey_structure)
            partial_results.append(partial)

        return self._merge_results(partial_results)

    def _organize_parallel(self, analyses: list[dict], survey_structure: list[str],
                           pipeline: "PipelineExecutor", stage_idx: int,
                           max_per_call: int) -> dict:
        self.report_progress(
            "论文数量超限，分批并行聚类",
            total=len(analyses),
            threshold=max_per_call,
        )
        chunks = [analyses[i:i + max_per_call]
                  for i in range(0, len(analyses), max_per_call)]

        def _cluster_chunk(chunk_idx):
            chunk = chunks[chunk_idx]
            self.report_progress("聚类批次", batch=chunk_idx + 1, count=len(chunk))
            return self._cluster_batch(chunk, survey_structure)

        items = list(range(len(chunks)))
        partial_results = pipeline.run_parallel_batches(
            items, _cluster_chunk, stage_idx, "聚类分类", preserve_order=True,
        )
        partial_results = [r for r in partial_results if r is not None]

        if not partial_results:
            return _EMPTY_CLUSTER

        if len(partial_results) == 1:
            return partial_results[0]

        return self._merge_results(partial_results)

    def _merge_results(self, partial_results: list[dict]) -> dict:
        merge_prompt = json.dumps(partial_results, ensure_ascii=False, indent=2)
        if len(merge_prompt) > 30000:
            merge_prompt = merge_prompt[:30000] + "\n...(数据过长已截断)"
        merged = self.llm_structured_safe(
            messages=[{
                "role": "user",
                "content": f"请合并以下 {len(partial_results)} 个批次的聚类结果：\n\n{merge_prompt}",
            }],
            system_prompt=ORGANIZER_MERGE_SYSTEM,
            fallback=partial_results[0],
            context="合并聚类",
        )
        self.report_progress("分批聚类合并完成", clusters=len(merged.get("clusters", [])))
        return merged
