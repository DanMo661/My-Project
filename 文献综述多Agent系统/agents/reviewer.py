"""Reviewer Agent：审校检查"""

import re
from agents.base import BaseAgent

from typing import Optional, Any

_DEFAULTS = {
    "review_max_chars": 20000,
    "writer_max_tokens": 8192,
}

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

DIMENSION_KEYS = ["structure", "logic", "coverage", "citations", "academic_style", "gaps"]


class ReviewerAgent(BaseAgent):
    """综述审校"""

    def __init__(self, llm, config: Optional[Any] = None):
        super().__init__(llm, config)

    def _cfg(self, key: str):
        if self.config and hasattr(self.config, key):
            return getattr(self.config, key)
        return _DEFAULTS[key]

    def _split_by_sections(self, text: str, max_chars: int) -> list[str]:
        parts = re.split(r'(?=^## )', text, flags=re.MULTILINE)
        sections = []
        current = ""
        for part in parts:
            if not part.strip():
                continue
            if len(current) + len(part) <= max_chars:
                current += part
            else:
                if current.strip():
                    sections.append(current)
                current = part
        if current.strip():
            sections.append(current)
        return sections

    def _review_section(self, section_text: str) -> dict:
        return self.llm_structured_safe(
            messages=[{
                "role": "user",
                "content": f"请审查以下综述片段：\n\n{section_text}",
            }],
            system_prompt=REVIEWER_SYSTEM,
            fallback={"score": 0, "error": "审校结果解析失败"},
            context="分段审校",
            required_keys=["score", "dimensions"],
            temperature=0.1,
        )

    def run(self, survey_text: str) -> dict:
        self.validate_non_empty_str(survey_text, "survey_text")
        max_chars = self._cfg("review_max_chars")

        if len(survey_text) <= max_chars:
            result = self.llm_structured_safe(
                messages=[{
                    "role": "user",
                    "content": f"请审查以下综述文章：\n\n{survey_text}",
                }],
                system_prompt=REVIEWER_SYSTEM,
                fallback={"score": 0, "error": "审校结果解析失败"},
                context="审校",
                required_keys=["score", "dimensions"],
                temperature=0.1,
            )
            if "error" not in result:
                self.report_progress("审校完成", score=result.get("score", "N/A"))
            return result

        sections = self._split_by_sections(survey_text, max_chars)
        self.report_progress(
            "综述过长，分段审校",
            original_length=len(survey_text),
            section_count=len(sections),
        )

        results = []
        for i, section in enumerate(sections):
            self.report_progress(f"审校第 {i+1}/{len(sections)} 段", chars=len(section))
            result = self._review_section(section)
            results.append(result)

        valid = [r for r in results if "error" not in r]
        if not valid:
            return {"score": 0, "error": "所有分段审校均失败"}

        dim_scores = {k: [] for k in DIMENSION_KEYS}
        all_issues = []
        all_suggestions = []
        total_score = 0

        for r in valid:
            total_score += r.get("score", 0)
            dims = r.get("dimensions", {})
            for k in DIMENSION_KEYS:
                if k in dims and "score" in dims[k]:
                    dim_scores[k].append(dims[k]["score"])
            all_issues.extend(r.get("major_issues", []))
            all_suggestions.extend(r.get("improvement_suggestions", []))

        merged_dims = {}
        for k in DIMENSION_KEYS:
            scores = dim_scores[k]
            avg = round(sum(scores) / len(scores), 1) if scores else 0
            merged_dims[k] = {"score": avg, "issues": [], "suggestions": []}

        avg_score = round(total_score / len(valid), 1)

        merged = {
            "score": avg_score,
            "dimensions": merged_dims,
            "major_issues": list(dict.fromkeys(all_issues)),
            "improvement_suggestions": list(dict.fromkeys(all_suggestions)),
        }

        self.report_progress("分段审校完成", score=avg_score, sections=len(valid))
        return merged

    def refine(self, survey_text: str, review: dict) -> str:
        issues = "\n".join(review.get("major_issues", []))
        suggestions = "\n".join(review.get("improvement_suggestions", []))
        max_tokens = self._cfg("writer_max_tokens")

        prompt = (
            f"以下是一篇综述文章。请根据审稿意见进行修改完善。\n\n"
            f"## 主要问题\n{issues}\n\n"
            f"## 改进建议\n{suggestions}\n\n"
            f"## 原文\n{survey_text}\n\n"
            f"请输出修改后的完整版本。"
        )

        self.report_progress("开始改进综述")
        result = self.llm_chat(
            messages=[{"role": "user", "content": prompt}],
            system_prompt="你是一个学术综述撰写专家。请根据审稿意见修改文章。",
            temperature=0.3,
            max_tokens=max_tokens,
        )

        self.report_progress("综述改进完成", length=len(result))
        return result
