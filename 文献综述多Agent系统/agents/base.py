"""Agent 基类"""

from llm.client import LLMClient


class BaseAgent:
    def __init__(self, llm: LLMClient):
        self.llm = llm
