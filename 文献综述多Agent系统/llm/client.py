"""
LLM 调用封装 — 支持多提供商（OpenAI 兼容 / Anthropic / Ollama）

向后兼容：
  - LLMClient(api_key="...", model="deepseek-chat", base_url="...")
    仍然可用，等价于 OpenAI-compatible 模式。
  - check_structured() 仍然可用。
  - config.DEFAULT_MAX_TOKENS 等常量仍可通过 config 模块访问。
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Optional

from config import (
    AppConfig,
    LLMProviderConfig,
    DEFAULT_MAX_TOKENS,
    LLM_TIMEOUT_SEC,
)
from llm.rate_limiter import RateLimiter
from llm.cost_tracker import CostTracker, TokenUsage
from errors import (
    LLMError, LLMAPIError, LLMRateLimitError, LLMAuthError,
    LLMTimeoutError, LLMNetworkError, LLMParseError,
)

log = logging.getLogger("llm")

# 重试配置
MAX_RETRIES = 3
BASE_BACKOFF = 2

# ---------------------------------------------------------------------------
# 重试辅助（兼容 errors.py 错误层次）
# ---------------------------------------------------------------------------


def _classify_api_error(status_code: int, body: str) -> LLMAPIError:
    if status_code == 429:
        return LLMRateLimitError(
            f"API 限流 (429)", status_code=status_code, response_body=body[:500]
        )
    if status_code in (401, 403):
        return LLMAuthError(
            f"认证失败 ({status_code})", status_code=status_code, response_body=body[:500]
        )
    return LLMAPIError(
        f"API 返回 {status_code}", status_code=status_code, response_body=body[:500]
    )


def _should_retry(error: Exception, attempt: int, max_retries: int) -> bool:
    if attempt >= max_retries - 1:
        return False
    if isinstance(error, LLMAuthError):
        return False
    return isinstance(error, LLMError)


def _wait_backoff(error: Exception, attempt: int):
    if isinstance(error, LLMRateLimitError):
        wait = 5 * (attempt + 1)
    else:
        wait = BASE_BACKOFF ** attempt
    log.debug(f"等待 {wait}s 后重试 (第 {attempt + 1} 次)")
    time.sleep(wait)


# ---------------------------------------------------------------------------
# Provider 基础协议
# ---------------------------------------------------------------------------


def _extract_json_strict(text: str) -> str:
    return text.strip()


def _extract_json_fallback(text: str) -> str:
    start = text.index("{")
    end = text.rindex("}") + 1
    return text[start:end]


def _parse_json(text: str) -> dict:
    for extractor in (_extract_json_strict, _extract_json_fallback):
        try:
            return json.loads(extractor(text))
        except (ValueError, json.JSONDecodeError):
            continue
    raise LLMParseError("LLM 返回内容无法解析为 JSON", raw_text=text[:1000])


# ---------------------------------------------------------------------------
# OpenAI 兼容 Provider（DeepSeek / OpenAI / Moonshot / 智谱 / 通义 / SiliconFlow）
# ---------------------------------------------------------------------------


class _OpenAICompatibleProvider:
    """OpenAI 兼容 API 封装"""

    def __init__(self, cfg: LLMProviderConfig):
        import requests
        self._requests = requests
        self.cfg = cfg

    def chat(
        self,
        messages: list[dict],
        system_prompt: str = "",
        temperature: float = 0.3,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        response_format: Optional[dict] = None,
        cost_tracker: Optional[CostTracker] = None,
        rate_limiter: Optional[RateLimiter] = None,
    ) -> str:
        if not messages:
            raise ValueError("messages 不能为空")
        if rate_limiter:
            rate_limiter.wait(estimated_tokens=max_tokens)

        full_messages = []
        if system_prompt:
            full_messages.append({"role": "system", "content": system_prompt})
        full_messages.extend(messages)

        headers = {
            "Authorization": f"Bearer {self.cfg.api_key}",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "model": self.cfg.model,
            "messages": full_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format:
            payload["response_format"] = response_format

        last_error: Optional[Exception] = None
        for attempt in range(self.cfg.max_retries + 1):
            try:
                resp = self._requests.post(
                    f"{self.cfg.base_url}/v1/chat/completions",
                    headers=headers, json=payload, timeout=self.cfg.timeout,
                )

                if resp.status_code != 200:
                    error = _classify_api_error(resp.status_code, resp.text)
                    log.warning("LLM API 错误 (第%d次): %s", attempt + 1, error)
                    last_error = error
                    if _should_retry(error, attempt, self.cfg.max_retries + 1):
                        _wait_backoff(error, attempt)
                        continue
                    raise error

                data = resp.json()
                if "choices" not in data:
                    error = LLMParseError(
                        "API 响应缺少 'choices' 字段",
                        raw_text=json.dumps(data, ensure_ascii=False)[:500],
                    )
                    log.warning("LLM 响应异常 (第%d次): %s", attempt + 1, error)
                    last_error = error
                    if _should_retry(error, attempt, self.cfg.max_retries + 1):
                        _wait_backoff(error, attempt)
                        continue
                    raise error

                content = data["choices"][0]["message"]["content"]
                if not content:
                    log.warning("LLM 返回空内容 (第%d次)", attempt + 1)
                    last_error = LLMParseError("LLM 返回空内容")
                    _wait_backoff(last_error, attempt)
                    continue

                # Token 统计
                usage = TokenUsage()
                if "usage" in data:
                    usage = TokenUsage(
                        input_tokens=data["usage"].get("prompt_tokens", 0),
                        output_tokens=data["usage"].get("completion_tokens", 0),
                    )
                finish = data["choices"][0].get("finish_reason")
                if finish == "length":
                    log.warning("输出被截断 (max_tokens=%d)", max_tokens)
                if cost_tracker:
                    cost_tracker.record(self.cfg.model, usage)
                return content

            except self._requests.Timeout:
                last_error = LLMTimeoutError(f"LLM 请求超时 ({self.cfg.timeout}s)")
                log.warning("LLM 超时 (第%d次)", attempt + 1)
                if attempt < self.cfg.max_retries:
                    _wait_backoff(last_error, attempt)
                    continue
            except self._requests.ConnectionError as e:
                last_error = LLMNetworkError(f"网络连接失败: {e}")
                log.warning("LLM 网络错误 (第%d次): %s", attempt + 1, e)
                if attempt < self.cfg.max_retries:
                    _wait_backoff(last_error, attempt)
                    continue
            except (LLMAuthError, LLMAPIError):
                raise
            except Exception as e:
                last_error = LLMError(f"未知 LLM 错误: {e}")
                log.warning("LLM 未知错误 (第%d次): %s", attempt + 1, e)
                if attempt < self.cfg.max_retries:
                    _wait_backoff(last_error, attempt)
                    continue

        raise last_error or LLMError("LLM 调用失败（重试耗尽）")

    def structured_output(
        self,
        messages: list[dict],
        system_prompt: str,
        temperature: float = 0.1,
        cost_tracker: Optional[CostTracker] = None,
        rate_limiter: Optional[RateLimiter] = None,
    ) -> dict:
        text = self.chat(
            messages, system_prompt,
            temperature=temperature,
            response_format={"type": "json_object"},
            cost_tracker=cost_tracker,
            rate_limiter=rate_limiter,
        )
        return _parse_json(text)


# ---------------------------------------------------------------------------
# Anthropic Provider（Claude 系列）
# ---------------------------------------------------------------------------


class _AnthropicProvider:
    """Anthropic Claude API 封装"""

    def __init__(self, cfg: LLMProviderConfig):
        try:
            import anthropic
        except ImportError:
            raise ImportError(
                "使用 Anthropic 提供商需安装：pip install anthropic"
            )
        self.cfg = cfg
        self.client = anthropic.Anthropic(
            api_key=cfg.api_key,
            base_url=cfg.base_url,
            timeout=cfg.timeout,
            max_retries=0,
        )

    def chat(
        self,
        messages: list[dict],
        system_prompt: str = "",
        temperature: float = 0.3,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        response_format: Optional[dict] = None,
        cost_tracker: Optional[CostTracker] = None,
        rate_limiter: Optional[RateLimiter] = None,
    ) -> str:
        if rate_limiter:
            rate_limiter.wait(estimated_tokens=max_tokens)

        # Anthropic 将 system 单独传递，从 messages 中过滤
        anthropic_msgs = [m for m in messages if m.get("role") != "system"]

        kwargs: dict[str, Any] = {
            "model": self.cfg.model,
            "messages": anthropic_msgs,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system_prompt:
            kwargs["system"] = system_prompt

        last_error: Optional[Exception] = None
        for attempt in range(self.cfg.max_retries + 1):
            try:
                result = self.client.messages.create(**kwargs)
                content = result.content[0].text if result.content else ""

                usage = TokenUsage()
                if result.usage:
                    usage = TokenUsage(
                        input_tokens=result.usage.input_tokens,
                        output_tokens=result.usage.output_tokens,
                    )
                if result.stop_reason == "max_tokens":
                    log.warning("输出被截断 (max_tokens=%d)", max_tokens)
                if cost_tracker:
                    cost_tracker.record(self.cfg.model, usage)
                return content

            except Exception as e:
                import anthropic as _ant
                if isinstance(e, _ant.AuthenticationError):
                    raise LLMAuthError(f"Anthropic 认证失败: {e}")
                if isinstance(e, _ant.RateLimitError):
                    last_error = LLMRateLimitError(f"Anthropic 限流: {e}")
                elif isinstance(e, (_ant.APITimeoutError, _ant.APIConnectionError)):
                    last_error = LLMTimeoutError(f"Anthropic 超时/连接错误: {e}")
                else:
                    last_error = LLMError(f"Anthropic 错误: {e}")
                log.warning("Anthropic 错误 (第%d次): %s", attempt + 1, e)
                if attempt < self.cfg.max_retries:
                    _wait_backoff(last_error, attempt)
                    continue

        raise last_error or LLMError("Anthropic 调用失败（重试耗尽）")

    def structured_output(
        self,
        messages: list[dict],
        system_prompt: str,
        temperature: float = 0.1,
        cost_tracker: Optional[CostTracker] = None,
        rate_limiter: Optional[RateLimiter] = None,
    ) -> dict:
        json_instruction = "\n\n请严格以 JSON 对象格式输出，不要包含任何其他文本。"
        augmented = list(messages)
        if augmented:
            last = dict(augmented[-1])
            last["content"] = last["content"] + json_instruction
            augmented[-1] = last
        text = self.chat(
            augmented, system_prompt,
            temperature=temperature,
            cost_tracker=cost_tracker,
            rate_limiter=rate_limiter,
        )
        return _parse_json(text)


# ---------------------------------------------------------------------------
# Ollama Provider（本地模型）
# ---------------------------------------------------------------------------


class _OllamaProvider:
    """Ollama 本地模型 API 封装"""

    def __init__(self, cfg: LLMProviderConfig):
        import requests
        self._requests = requests
        self.cfg = cfg
        self.base_url = cfg.base_url.rstrip("/")

    def chat(
        self,
        messages: list[dict],
        system_prompt: str = "",
        temperature: float = 0.3,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        response_format: Optional[dict] = None,
        cost_tracker: Optional[CostTracker] = None,
        rate_limiter: Optional[RateLimiter] = None,
    ) -> str:
        if rate_limiter:
            rate_limiter.wait()

        full_messages = []
        if system_prompt:
            full_messages.append({"role": "system", "content": system_prompt})
        full_messages.extend(messages)

        payload: dict[str, Any] = {
            "model": self.cfg.model,
            "messages": full_messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        if response_format:
            payload["format"] = "json"

        last_error: Optional[Exception] = None
        for attempt in range(self.cfg.max_retries + 1):
            try:
                resp = self._requests.post(
                    f"{self.base_url}/api/chat",
                    json=payload, timeout=self.cfg.timeout,
                )
                resp.raise_for_status()
                data = resp.json()
                content = data.get("message", {}).get("content", "")
                if not content:
                    last_error = LLMParseError("Ollama 返回空内容")
                    _wait_backoff(last_error, attempt)
                    continue

                usage = TokenUsage(
                    input_tokens=data.get("prompt_eval_count", 0),
                    output_tokens=data.get("eval_count", 0),
                )
                if cost_tracker:
                    cost_tracker.record(self.cfg.model, usage)
                return content

            except self._requests.Timeout:
                last_error = LLMTimeoutError(f"Ollama 超时 ({self.cfg.timeout}s)")
                if attempt < self.cfg.max_retries:
                    _wait_backoff(last_error, attempt)
                    continue
            except self._requests.ConnectionError as e:
                last_error = LLMNetworkError(f"Ollama 连接失败: {e}")
                if attempt < self.cfg.max_retries:
                    _wait_backoff(last_error, attempt)
                    continue
            except Exception as e:
                last_error = LLMError(f"Ollama 错误: {e}")
                if attempt < self.cfg.max_retries:
                    _wait_backoff(last_error, attempt)
                    continue

        raise last_error or LLMError("Ollama 调用失败（重试耗尽）")

    def structured_output(
        self,
        messages: list[dict],
        system_prompt: str,
        temperature: float = 0.1,
        cost_tracker: Optional[CostTracker] = None,
        rate_limiter: Optional[RateLimiter] = None,
    ) -> dict:
        json_instruction = "\n\n请严格以 JSON 对象格式输出，不要包含任何其他文本。"
        augmented = list(messages)
        if augmented:
            last = dict(augmented[-1])
            last["content"] = last["content"] + json_instruction
            augmented[-1] = last
        text = self.chat(
            augmented, system_prompt,
            temperature=temperature,
            response_format={"type": "json_object"},
            cost_tracker=cost_tracker,
            rate_limiter=rate_limiter,
        )
        return _parse_json(text)


# ---------------------------------------------------------------------------
# Provider 工厂 + 统一 LLMClient
# ---------------------------------------------------------------------------

_PROVIDER_MAP = {
    "openai_compatible": _OpenAICompatibleProvider,
    "anthropic": _AnthropicProvider,
    "ollama": _OllamaProvider,
}


def _create_provider(cfg: LLMProviderConfig):
    cls = _PROVIDER_MAP.get(cfg.provider_type)
    if cls is None:
        raise ValueError(f"不支持的 provider_type: {cfg.provider_type}")
    return cls(cfg)


class LLMClient:
    """
    统一 LLM 调用接口（向后兼容）

    新用法：
        cfg = AppConfig.from_sources({"provider": "openai", "api_key": "..."})
        llm = LLMClient(config=cfg)

    旧用法（仍然有效）：
        llm = LLMClient(api_key="sk-xxx", model="deepseek-chat")
    """

    def __init__(
        self,
        api_key: str = "",
        model: str = "deepseek-chat",
        base_url: str = "https://api.deepseek.com",
        config: Optional[AppConfig] = None,
    ):
        if config is not None:
            self._config = config
        else:
            # 旧接口兼容：从参数构建配置
            self._config = AppConfig.from_sources({
                "api_key": api_key,
                "model": model,
                "base_url": base_url,
            })

        self._provider = _create_provider(self._config.llm)
        self._cost_tracker = CostTracker(
            enabled=self._config.cost_tracking,
            alert_threshold_usd=self._config.cost_alert_threshold_usd,
            cost_input_per_m=self._config.llm.cost_input_per_m,
            cost_output_per_m=self._config.llm.cost_output_per_m,
        )
        self._rate_limiter = RateLimiter(
            rpm=self._config.llm.rate_limit_rpm,
            rpd=self._config.llm.rate_limit_rpd,
            tpm=self._config.llm.rate_limit_tpm,
        )

    @property
    def cost_tracker(self) -> CostTracker:
        return self._cost_tracker

    def chat(self, messages: list[dict], system_prompt: str = "",
             temperature: float = 0.3, max_tokens: int = DEFAULT_MAX_TOKENS,
             response_format: Optional[dict] = None) -> str:
        """调用 LLM chat，返回文本内容。"""
        return self._provider.chat(
            messages=messages,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format,
            cost_tracker=self._cost_tracker,
            rate_limiter=self._rate_limiter,
        )

    def structured_output(self, messages: list[dict], system_prompt: str,
                          temperature: float = 0.1) -> dict:
        """返回 JSON 结构化结果。解析失败抛出 LLMParseError。"""
        return self._provider.structured_output(
            messages=messages,
            system_prompt=system_prompt,
            temperature=temperature,
            cost_tracker=self._cost_tracker,
            rate_limiter=self._rate_limiter,
        )


def check_structured(result: dict, required_keys: list[str], context: str) -> dict:
    """检查 structured_output 结果的字段完整性（向后兼容）。"""
    missing = [k for k in required_keys if k not in result]
    if missing:
        raise LLMParseError(
            f"[{context}] LLM 返回缺少字段: {missing}",
            raw_text=json.dumps(result, ensure_ascii=False)[:500],
        )
    return result
