"""
令牌桶限流器 — 保护 API 调用不超过提供商速率限制

支持三种维度：
  - RPM  每分钟请求数
  - RPD  每天请求数
  - TPM  每分钟 Token 数
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field


@dataclass
class _TokenBucket:
    """单维令牌桶"""
    capacity: float
    refill_rate: float  # tokens/sec
    tokens: float = 0.0
    last_refill: float = field(default_factory=time.monotonic)

    def __post_init__(self):
        self.tokens = self.capacity

    def consume(self, n: float = 1.0) -> float:
        """
        尝试消费 n 个令牌。不足时返回需等待的秒数，0 表示成功。
        """
        self._refill()
        if self.tokens >= n:
            self.tokens -= n
            return 0.0
        deficit = n - self.tokens
        return deficit / self.refill_rate if self.refill_rate > 0 else 999.0

    def _refill(self):
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now


class RateLimiter:
    """
    多维限流器

    每次 LLM 调用前调 wait(tokens)，自动阻塞至速率允许。
    """

    def __init__(
        self,
        rpm: int = 60,
        rpd: int = 10000,
        tpm: int = 180000,
    ):
        self._lock = threading.Lock()
        # 请求维度
        self._rpm_bucket = _TokenBucket(
            capacity=float(rpm),
            refill_rate=rpm / 60.0,
        )
        self._rpd_bucket = _TokenBucket(
            capacity=float(rpd),
            refill_rate=rpd / 86400.0,
        )
        # Token 维度
        self._tpm_bucket = _TokenBucket(
            capacity=float(tpm),
            refill_rate=tpm / 60.0,
        )

    def wait(self, estimated_tokens: int = 0) -> None:
        """
        阻塞直到速率允许。
        estimated_tokens: 本次请求预估 token 数（用于 TPM 限流）
        """
        while True:
            with self._lock:
                waits = []
                w = self._rpm_bucket.consume(1)
                if w > 0:
                    waits.append(w)
                w = self._rpd_bucket.consume(1)
                if w > 0:
                    waits.append(w)
                if estimated_tokens > 0:
                    w = self._tpm_bucket.consume(estimated_tokens)
                    if w > 0:
                        waits.append(w)

                if not waits:
                    return
                sleep_sec = max(waits)

            time.sleep(min(sleep_sec, 5.0))  # 最多睡 5 秒再重试


    def status(self) -> dict[str, float]:
        """返回当前各维度剩余容量（调试用）"""
        with self._lock:
            self._rpm_bucket._refill()
            self._rpd_bucket._refill()
            self._tpm_bucket._refill()
            return {
                "rpm_remaining": round(self._rpm_bucket.tokens, 1),
                "rpd_remaining": round(self._rpd_bucket.tokens, 1),
                "tpm_remaining": round(self._tpm_bucket.tokens, 1),
            }
