"""Coordinator Agent：制定调研计划"""

from agents.base import BaseAgent
from errors import ValidationError

COORDINATOR_SYSTEM = """你是一个科研综述协调员。你的职责是：
1. 根据用户给定的主题，制定详细的调研计划
2. 将主题拆解成多个子方向
3. 为每个子方向生成搜索关键词（英文）
4. 规划综述的结构

输出 JSON 格式：
{
  "topic": "综述主题",
  "sub_directions": [
    {
      "name": "子方向名称",
      "keywords": ["英文关键词1", "英文关键词2"],
      "description": "这个子方向关注什么"
    }
  ],
  "survey_structure": [
    "章节1：引言",
    "章节2：...",
    ...
  ]
}
"""


class CoordinatorAgent(BaseAgent):
    """制定综述调研计划"""

    def __init__(self, llm, config=None):
        super().__init__(llm, config)

    def run(self, topic: str, extra_context: str = "") -> dict:
        """制定计划（直接覆写 run，不走 execute 模板）"""
        topic = self.validate_non_empty_str(topic, "topic")

        user_msg = f"研究主题：{topic}\n"
        if extra_context:
            user_msg += f"额外信息：{extra_context}\n"

        result = self.llm_structured(
            messages=[{"role": "user", "content": user_msg}],
            system_prompt=COORDINATOR_SYSTEM,
            required_keys=["sub_directions", "survey_structure"],
        )

        # 验证 sub_directions 非空
        sub_directions = result.get("sub_directions", [])
        if not sub_directions:
            raise ValidationError("CoordinatorAgent: LLM 返回的 sub_directions 为空")

        self.report_progress(
            "计划完成",
            sub_directions=len(sub_directions),
        )
        return result
