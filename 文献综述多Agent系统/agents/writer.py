"""Writer Agent：撰写综述"""

import json
import logging
import config
from agents.base import BaseAgent

log = logging.getLogger(__name__)

MAX_PAPERS_FOR_WRITER = config.WRITER_MAX_PAPERS

WRITER_SYSTEM = """你是一个科研综述撰写专家。根据论文分析和聚类结果，撰写高质量的领域综述。

要求：
1. 用中文撰写
2. 学术严谨，引用规范（标注 [编号]）
3. 逻辑清晰，按论文分类组织
4. 每个观点有文献支撑
5. 包含：引言、各分类详述、研究空白与挑战、未来展望、结论

使用 Markdown 格式输出完整的综述文章。
"""


def _select_top_papers(analyses: list[dict], clusters: list[dict],
                       max_count: int) -> list[dict]:
    """按 cluster 比例采样论文，保证覆盖度"""
    if len(analyses) <= max_count:
        return analyses

    cluster_titles = set()
    for c in clusters:
        for t in c.get("papers", []):
            cluster_titles.add(t.strip().lower())

    per_cluster = max(2, max_count // max(1, len(clusters)))
    selected = []
    selected_ids = set()

    for c in clusters:
        papers_in_cluster = []
        for a in analyses:
            title = a.get("title", "").strip().lower()
            if title in {t.strip().lower() for t in c.get("papers", [])}:
                papers_in_cluster.append(a)

        for p in papers_in_cluster[:per_cluster]:
            pid = p.get("paper_id") or p.get("title", "")
            if pid not in selected_ids:
                selected_ids.add(pid)
                selected.append(p)

    if len(selected) < max_count:
        remaining = [a for a in analyses
                     if (a.get("paper_id") or a.get("title", "")) not in selected_ids]
        remaining.sort(key=lambda x: x.get("innovation_score", 0), reverse=True)
        for p in remaining[:max_count - len(selected)]:
            selected.append(p)

    log.info(f"论文裁剪：{len(analyses)} → {len(selected)} 篇")
    return selected


def _build_ref_list(analyses: list[dict]) -> str:
    """构建参考文献编号列表"""
    lines = []
    for j, a in enumerate(analyses):
        authors = a.get("authors", [])
        author_str = "、".join(authors[:3]) if authors else "Unknown"
        lines.append(f"[{j+1}] {author_str} ({a.get('year', '')}), 《{a.get('title', '')}》")
    return "\n".join(lines)


class WriterAgent(BaseAgent):
    """综述撰写"""

    def run(self, topic: str, survey_structure: list[str],
            clusters: list[dict], analyses: list[dict],
            timeline: list[dict], research_gaps: list[dict]) -> str:
        """撰写完整综述"""
        self.validate_non_empty_str(topic, "topic")
        self.validate_papers(analyses, "analyses")

        selected = _select_top_papers(analyses, clusters, MAX_PAPERS_FOR_WRITER)
        ref_list = _build_ref_list(selected)

        clusters_text = json.dumps(clusters, ensure_ascii=False, indent=2)
        gaps_text = json.dumps(research_gaps, ensure_ascii=False, indent=2)
        timeline_text = json.dumps(timeline, ensure_ascii=False, indent=2)

        prompt = (
            f"## 综述主题\n{topic}\n\n"
            f"## 建议结构\n{json.dumps(survey_structure, ensure_ascii=False)}\n\n"
            f"## 论文聚类\n{clusters_text}\n\n"
            f"## 发展时间线\n{timeline_text}\n\n"
            f"## 研究空白与挑战\n{gaps_text}\n\n"
            f"## 参考文献列表\n{ref_list}\n\n"
            f"请根据以上信息，撰写一篇完整的中文领域综述。要求引用的文献用 [编号] 标注。"
        )

        self.report_progress("开始撰写综述", papers=len(selected))
        result = self.llm_chat(
            messages=[{"role": "user", "content": prompt}],
            system_prompt=WRITER_SYSTEM,
            temperature=0.3,
            max_tokens=config.WRITER_MAX_TOKENS,
        )

        # 添加参考文献附录
        result += "\n\n---\n## 参考文献\n\n"
        for j, a in enumerate(selected):
            authors = a.get("authors", [])
            author_str = "、".join(authors[:5]) if authors else "Unknown"
            result += f"[{j+1}] {author_str}, {a.get('year', '')}. {a.get('title', '')}.\n"

        self.report_progress("综述撰写完成", length=len(result))
        return result
