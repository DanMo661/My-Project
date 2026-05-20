"""Writer Agent：撰写综述"""

import json
import logging
from llm.client import LLMClient

log = logging.getLogger(__name__)

WRITER_SYSTEM = """你是一个科研综述撰写专家。根据论文分析和聚类结果，撰写高质量的领域综述。

要求：
1. 用中文撰写
2. 学术严谨，引用规范（标注 [编号]）
3. 逻辑清晰，按论文分类组织
4. 每个观点有文献支撑
5. 包含：引言、各分类详述、研究空白与挑战、未来展望、结论

使用 Markdown 格式输出完整的综述文章。
"""


class WriterAgent:
    """综述撰写"""

    def __init__(self, llm: LLMClient):
        self.llm = llm

    def run(self, topic: str, survey_structure: list[str],
            clusters: list[dict], analyses: list[dict],
            timeline: list[dict], research_gaps: list[dict]) -> str:
        """撰写完整综述"""

        # 为论文编号
        ref_list = "\n".join([
            f"[{j+1}] {a.get('authors', [''])[:3]} ({a.get('year', '')}), "
            f"《{a.get('title', '')}》"
            for j, a in enumerate(analyses)
        ])

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

        result = self.llm.chat(
            messages=[{"role": "user", "content": prompt}],
            system_prompt=WRITER_SYSTEM,
            temperature=0.3,
            max_tokens=8192,
        )

        # 添加参考文献附录
        result += "\n\n---\n## 参考文献\n\n"
        for j, a in enumerate(analyses):
            authors = "、".join(a.get('authors', [])[:5])
            result += f"[{j+1}] {authors}, {a.get('year', '')}. {a.get('title', '')}.\n"

        return result
