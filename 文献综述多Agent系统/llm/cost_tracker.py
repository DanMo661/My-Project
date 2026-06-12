"""
会话级成本追踪器

每次 LLM 调用后记录 token 用量和估算费用，会话结束时打印摘要。
不做持久化 — 每次运行独立计费。
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field


@dataclass
class TokenUsage:
    """单次调用 token 用量"""
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass
class _CallRecord:
    timestamp: float
    model: str
    usage: TokenUsage
    cost_usd: float


class CostTracker:
    """会话级成本追踪器（线程安全）"""

    def __init__(
        self,
        enabled: bool = True,
        alert_threshold_usd: float = 10.0,
        cost_input_per_m: float = 0.0,
        cost_output_per_m: float = 0.0,
    ):
        self.enabled = enabled
        self.alert_threshold = alert_threshold_usd
        self._cost_input_per_m = cost_input_per_m
        self._cost_output_per_m = cost_output_per_m
        self._lock = threading.Lock()
        self._records: list[_CallRecord] = []
        self._total_input = 0
        self._total_output = 0
        self._total_cost = 0.0
        self._alert_fired = False
        self._start_time = time.monotonic()

    def record(self, model: str, usage: TokenUsage) -> float:
        """
        记录一次调用，返回本次费用（美元）。
        超过阈值时打印警告。
        """
        if not self.enabled:
            return 0.0

        cost = (
            usage.input_tokens * self._cost_input_per_m / 1_000_000
            + usage.output_tokens * self._cost_output_per_m / 1_000_000
        )

        with self._lock:
            self._records.append(_CallRecord(
                timestamp=time.monotonic(),
                model=model,
                usage=usage,
                cost_usd=cost,
            ))
            self._total_input += usage.input_tokens
            self._total_output += usage.output_tokens
            self._total_cost += cost

            if not self._alert_fired and self._total_cost >= self.alert_threshold:
                self._alert_fired = True
                import logging
                logging.getLogger("cost").warning(
                    "成本警告: 累计费用 $%.4f 已超过阈值 $%.2f",
                    self._total_cost, self.alert_threshold,
                )

        return cost

    @property
    def total_input_tokens(self) -> int:
        with self._lock:
            return self._total_input

    @property
    def total_output_tokens(self) -> int:
        with self._lock:
            return self._total_output

    @property
    def total_cost_usd(self) -> float:
        with self._lock:
            return self._total_cost

    @property
    def call_count(self) -> int:
        with self._lock:
            return len(self._records)

    @property
    def elapsed_sec(self) -> float:
        return time.monotonic() - self._start_time

    def summary(self) -> str:
        """返回可打印的成本摘要"""
        elapsed = self.elapsed_sec
        lines = [
            "",
            "=" * 50,
            "  成本追踪摘要",
            "=" * 50,
            f"  调用次数:       {self.call_count}",
            f"  输入 Token:     {self._total_input:,}",
            f"  输出 Token:     {self._total_output:,}",
            f"  总 Token:       {self._total_input + self._total_output:,}",
            f"  估算费用:       ${self._total_cost:.4f}",
            f"  运行时长:       {elapsed:.1f}s",
            "=" * 50,
        ]
        return "\n".join(lines)

    def per_model_breakdown(self) -> dict[str, dict]:
        """按模型统计"""
        with self._lock:
            buckets: dict[str, dict] = {}
            for r in self._records:
                if r.model not in buckets:
                    buckets[r.model] = {
                        "calls": 0, "input": 0, "output": 0, "cost": 0.0,
                    }
                b = buckets[r.model]
                b["calls"] += 1
                b["input"] += r.usage.input_tokens
                b["output"] += r.usage.output_tokens
                b["cost"] += r.cost_usd
            return buckets
