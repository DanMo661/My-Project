"""Reviewer Agent：审校检查"""

import json
import logging
import config
from llm.client import LLMClient
from agents.base import BaseAgent

log = logging.getLogger(__name__)

REVIEWER_SYSTEM = """你是一个学术审稿专家。审查综述文章的质量，给出修改建议。

从以下维度评估：
1. 结构完整性 - 是否有清晰的引言、正文、结论
2. 逻辑连贯性 - 各章节之间的递进关系
3. 文献覆盖度 - 是否涵盖了主要相关工作
4. 引用准确性 - 引用标注是否规范
5. 学术规范性 - 语言是否学术化
6. 研究空白识别 - 是否明确指出当前不足

输出 JSON 格式：
{
  "score": 总体评分1-10,
  "dimensions": {
    "structure": {"score": 1-10, "issues": ["问题1", "问题2"], "suggestions": ["建议1"]},
    "logic": {"score": 1-10, ...},
    "coverage": {"score": 1-10, ...},
    "citations": {"score": 1-10, ...},
    "academic_style": {"score": 1-10, ...},
    "gaps": {"score": 1-10, ...}
  },
  "major_issues": ["主要问题"],
  "improvement_suggestions": ["改进建议"]
}
"""


class ReviewerAgent(BaseAgent):
    """综述审校"""

    def run(self, survey_text: str) -> dict:
        """审校综述"""
        if len(survey_text) > config.REVIEW_MAX_CHARS:
            log.warning(f"综述过长（{len(survey_text)} 字），截取前 {config.REVIEW_MAX_CHARS} 字审校")
        text_for_review = survey_text[:config.REVIEW_MAX_CHARS]

        result = self.llm.structured_output(
            messages=[{
                "role": "user",
                "content": f"请审查以下综述文章：\n\n{text_for_review}",
            }],
            system_prompt=REVIEWER_SYSTEM,
            temperature=0.1,
        )

        if "error" in result:
            log.warning("审校结果解析失败")
        else:
            log.info(f"审校完成，总体评分：{result.get('score', 'N/A')}/10")
        return result

    def refine(self, survey_text: str, review: dict) -> str:
        """根据审校意见改进综述"""
        issues = "\n".join(review.get("major_issues", []))
        suggestions = "\n".join(review.get("improvement_suggestions", []))

        prompt = (
            f"以下是一篇综述文章。请根据审稿意见进行修改完善。\n\n"
            f"## 主要问题\n{issues}\n\n"
            f"## 改进建议\n{suggestions}\n\n"
            f"## 原文\n{survey_text}\n\n"
            f"请输出修改后的完整版本。"
        )

        result = self.llm.chat(
            messages=[{"role": "user", "content": prompt}],
            system_prompt="你是一个学术综述撰写专家。请根据审稿意见修改文章。",
            temperature=0.3,
            max_tokens=config.WRITER_MAX_TOKENS,
        )

        return result
