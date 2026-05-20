"""Coordinator Agent：制定调研计划"""

import logging
import sys
from llm.client import LLMClient, check_structured
from agents.base import BaseAgent

log = logging.getLogger(__name__)

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

    def run(self, topic: str, extra_context: str = "") -> dict:
        """制定计划"""
        user_msg = f"研究主题：{topic}\n"
        if extra_context:
            user_msg += f"额外信息：{extra_context}\n"

        result = self.llm.structured_output(
            messages=[{"role": "user", "content": user_msg}],
            system_prompt=COORDINATOR_SYSTEM,
        )

        try:
            check_structured(result, ["sub_directions", "survey_structure"], "CoordinatorAgent")
        except RuntimeError as e:
            log.error(str(e))
            sys.exit(1)

        log.info(f"协调员计划完成：{len(result.get('sub_directions', []))} 个子方向")
        return result
