"""Agent 基类 — 提供 LLM 调用包装、结果校验、进度报告等共享功能"""

import logging
from abc import ABC
from typing import Any, Optional

from llm.client import LLMClient, check_structured
from errors import ValidationError, LLMParseError


class BaseAgent(ABC):
    """所有 Agent 的基类。

    子类需实现 execute() 方法（接受任务输入，返回结果）。
    也可直接覆写 run()，此时 execute() 不会被调用。

    提供的共享功能：
    - llm_structured(): 带错误检查和日志的结构化 LLM 调用
    - llm_structured_safe(): 结构化调用，失败返回 fallback（不抛异常）
    - llm_chat(): 带日志的文本 LLM 调用
    - validate_result(): 校验 dict 包含必要字段
    - validate_input_*(): 输入数据校验
    - report_progress(): 统一格式的进度日志
    - run(): 标准执行模板（调用 execute()，自动日志和异常处理）
    """

    def __init__(self, llm: LLMClient, config: Optional[Any] = None):
        self.llm = llm
        self.config = config
        self.log = logging.getLogger(self.__class__.__name__)

    # ── 执行接口 ──

    def run(self, *args, **kwargs) -> Any:
        """标准执行入口：自动记录开始/结束、捕获异常。"""
        name = self.__class__.__name__
        self.log.info(f"[{name}] 开始执行")
        try:
            result = self.execute(*args, **kwargs)
            self.log.info(f"[{name}] 执行完成")
            return result
        except Exception:
            self.log.exception(f"[{name}] 执行失败")
            raise

    def execute(self, *args, **kwargs) -> Any:
        """子类实现此方法定义具体业务逻辑。

        默认实现抛出 NotImplementedError，子类必须覆写。
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} 必须实现 execute() 或直接覆写 run()"
        )

    # ── LLM 调用包装 ──

    def llm_structured(self, messages: list[dict], system_prompt: str,
                       required_keys: Optional[list[str]] = None,
                       temperature: float = 0.1) -> dict:
        """调用 LLM 获取结构化 JSON 结果，并自动校验。

        Args:
            messages: 对话消息列表
            system_prompt: 系统提示词
            required_keys: 必须存在的字段列表，缺失则抛 ValueError
            temperature: LLM 温度参数

        Returns:
            解析后的 dict 结果

        Raises:
            ValueError: 当 required_keys 中有字段缺失时
            LLMParseError: LLM 返回无法解析为 JSON 时
        """
        result = self.llm.structured_output(
            messages=messages,
            system_prompt=system_prompt,
            temperature=temperature,
        )
        self.validate_result(result, required_keys or [])
        return result

    def llm_structured_safe(self, messages: list[dict], system_prompt: str,
                            fallback: dict, context: str,
                            required_keys: Optional[list[str]] = None,
                            temperature: float = 0.1) -> dict:
        """调用 structured_output，解析失败时返回 fallback 并记录日志。

        用于非关键步骤（Analyzer、Organizer 等），失败不中断流程。
        """
        try:
            return self.llm_structured(
                messages=messages, system_prompt=system_prompt,
                required_keys=required_keys, temperature=temperature,
            )
        except Exception as e:
            from errors import LLMError
            if isinstance(e, (LLMParseError, ValueError, LLMError)):
                self.log.warning(f"[{context}] LLM 结构化输出失败，使用降级结果: {e}")
                return fallback
            raise

    def llm_chat(self, messages: list[dict], system_prompt: str,
                 temperature: float = 0.3,
                 max_tokens: int = 4096) -> str:
        """调用 LLM 获取文本结果。

        Args:
            messages: 对话消息列表
            system_prompt: 系统提示词
            temperature: LLM 温度参数
            max_tokens: 最大输出 token 数

        Returns:
            LLM 返回的文本

        Raises:
            LLMError: 调用失败（超时、网络、限流且重试耗尽等）
        """
        return self.llm.chat(
            messages=messages,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    # ── 输入校验 ──

    @staticmethod
    def validate_non_empty_list(value: list, name: str) -> list:
        """验证列表非空"""
        if not isinstance(value, list) or len(value) == 0:
            raise ValidationError(f"{name} 不能为空列表")
        return value

    @staticmethod
    def validate_non_empty_str(value: str, name: str) -> str:
        """验证字符串非空"""
        if not isinstance(value, str) or not value.strip():
            raise ValidationError(f"{name} 不能为空字符串")
        return value.strip()

    @staticmethod
    def validate_papers(papers: list[dict], name: str = "papers") -> list[dict]:
        """验证论文列表格式：每项必须是 dict 且包含 title"""
        if not isinstance(papers, list):
            raise ValidationError(f"{name} 必须是列表，实际为 {type(papers).__name__}")
        for i, p in enumerate(papers):
            if not isinstance(p, dict):
                raise ValidationError(f"{name}[{i}] 必须是字典，实际为 {type(p).__name__}")
            if not p.get("title"):
                raise ValidationError(f"{name}[{i}] 缺少 title 字段")
        return papers

    # ── 结果校验 ──

    def validate_result(self, result: dict,
                        required_keys: list[str]) -> dict:
        """校验 LLM 结构化结果。

        - 包含 "error" 键 → 抛 ValueError
        - 缺少 required_keys 中的字段 → 抛 LLMParseError

        Raises:
            LLMParseError: 校验失败（含错误详情）
        """
        if not required_keys and "error" not in result:
            return result
        return check_structured(result, required_keys,
                                self.__class__.__name__)

    # ── 进度报告 ──

    def report_progress(self, message: str, **context) -> None:
        """统一格式的进度日志。

        Args:
            message: 进度描述
            **context: 可选的上下文键值对，附加到日志中
        """
        suffix = ""
        if context:
            parts = [f"{k}={v}" for k, v in context.items()]
            suffix = f" ({', '.join(parts)})"
        self.log.info(f"[{self.__class__.__name__}] {message}{suffix}")
