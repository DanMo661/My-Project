"""
灵活的配置系统 — 支持多 LLM 提供商、环境变量、配置文件、CLI 参数

配置加载优先级（高 → 低）：
  1. 命令行参数（CLI）
  2. 环境变量
  3. 配置文件（YAML/TOML）
  4. 提供商预设默认值
  5. 全局默认值
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

# ---------------------------------------------------------------------------
# 常量 — 应用层参数（向后兼容原 config.py）
# ---------------------------------------------------------------------------

DEFAULT_MAX_TOKENS = 4096
WRITER_MAX_TOKENS = 8192
LLM_TIMEOUT_SEC = 60

SEARCH_MAX_RESULTS = 8
FILTER_BATCH_SIZE = 15
SEARCH_RATE_LIMIT_SEC = 1.5
SEARCH_TIMEOUT_SEC = 30

ANALYZER_BATCH_SIZE = 5
ABSTRACT_MAX_CHARS = 500

ORGANIZER_MAX_ANALYSES = 30
WRITER_MAX_PAPERS = 40
REVIEW_MAX_CHARS = 20000

# 并行执行
MAX_WORKERS = 4  # 线程池最大工作线程数（受 LLM API 并发限制）

# ---------------------------------------------------------------------------
# 提供商预设
# ---------------------------------------------------------------------------

PROVIDER_PRESETS: dict[str, dict[str, Any]] = {
    "deepseek": {
        "base_url": "https://api.deepseek.com",
        "default_model": "deepseek-chat",
        "provider_type": "openai_compatible",
        "env_prefix": "DEEPSEEK",
    },
    "openai": {
        "base_url": "https://api.openai.com",
        "default_model": "gpt-4o",
        "provider_type": "openai_compatible",
        "env_prefix": "OPENAI",
    },
    "moonshot": {
        "base_url": "https://api.moonshot.cn",
        "default_model": "moonshot-v1-128k",
        "provider_type": "openai_compatible",
        "env_prefix": "MOONSHOT",
    },
    "zhipu": {
        "base_url": "https://open.bigmodel.cn/api/paas",
        "default_model": "glm-4-flash",
        "provider_type": "openai_compatible",
        "env_prefix": "ZHIPU",
    },
    "qwen": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode",
        "default_model": "qwen-plus",
        "provider_type": "openai_compatible",
        "env_prefix": "QWEN",
    },
    "siliconflow": {
        "base_url": "https://api.siliconflow.cn",
        "default_model": "deepseek-ai/DeepSeek-V3",
        "provider_type": "openai_compatible",
        "env_prefix": "SILICONFLOW",
    },
    "ollama": {
        "base_url": "http://localhost:11434",
        "default_model": "qwen2.5:14b",
        "provider_type": "ollama",
        "env_prefix": "OLLAMA",
    },
    "anthropic": {
        "base_url": "https://api.anthropic.com",
        "default_model": "claude-sonnet-4-20250514",
        "provider_type": "anthropic",
        "env_prefix": "ANTHROPIC",
    },
    "custom": {
        "base_url": "",
        "default_model": "",
        "provider_type": "openai_compatible",
        "env_prefix": "CUSTOM",
    },
}

# ---------------------------------------------------------------------------
# 典型价格表（每 1M tokens，美元）
# ---------------------------------------------------------------------------

TYPICAL_COSTS: dict[str, dict[str, float]] = {
    "deepseek-chat":     {"input": 0.27,  "output": 1.10},
    "deepseek-reasoner": {"input": 0.55,  "output": 2.19},
    "gpt-4o":            {"input": 2.50,  "output": 10.00},
    "gpt-4o-mini":       {"input": 0.15,  "output": 0.60},
    "claude-sonnet-4-20250514": {"input": 3.00, "output": 15.00},
    "moonshot-v1-128k":  {"input": 0.72,  "output": 0.72},
    "glm-4-flash":       {"input": 0.00,  "output": 0.00},
    "qwen-plus":         {"input": 0.15,  "output": 0.60},
}

VALID_PROVIDER_TYPES = ("openai_compatible", "anthropic", "ollama")

# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------


def _env(key: str, default: Any = None) -> Any:
    """读取环境变量，返回字符串或默认值"""
    val = os.environ.get(key)
    return val if val is not None else default


def _env_float(key: str, default: float = 0.0) -> float:
    val = os.environ.get(key)
    if val is None:
        return default
    try:
        return float(val)
    except ValueError:
        return default


def _env_int(key: str, default: int = 0) -> int:
    val = os.environ.get(key)
    if val is None:
        return default
    try:
        return int(val)
    except ValueError:
        return default


def _env_bool(key: str, default: bool = False) -> bool:
    val = os.environ.get(key)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "y")


def _load_config_file(path: Optional[str]) -> dict[str, Any]:
    """加载 YAML 或 JSON 配置文件"""
    if not path:
        # 按优先级搜索默认位置
        candidates = [
            Path("litreview.yml"),
            Path("litreview.yaml"),
            Path("litreview.json"),
            Path("~/.config/litreview/config.yml").expanduser(),
        ]
        for c in candidates:
            if c.exists():
                path = str(c)
                break
    if not path:
        return {}

    p = Path(path)
    if not p.exists():
        return {}

    text = p.read_text(encoding="utf-8")

    if p.suffix in (".yml", ".yaml"):
        try:
            import yaml
            return yaml.safe_load(text) or {}
        except ImportError:
            return {}
    elif p.suffix == ".json":
        return json.loads(text) or {}
    return {}


# ---------------------------------------------------------------------------
# 验证
# ---------------------------------------------------------------------------


class ConfigError(Exception):
    """配置验证错误，收集所有错误信息"""


class ConfigValidator:
    """配置验证器 — 收集所有错误后统一抛出"""

    def __init__(self):
        self.errors: list[str] = []

    def require(self, value: Any, name: str):
        if not value:
            self.errors.append(f"缺少必需配置: {name}")

    def check(self, condition: bool, msg: str):
        if not condition:
            self.errors.append(msg)

    def validate_range(self, value: float, name: str,
                       lo: float = 0, hi: float = float("inf")):
        if not (lo <= value <= hi):
            self.errors.append(f"{name}={value} 超出范围 [{lo}, {hi}]")

    def raise_if_errors(self):
        if self.errors:
            raise ConfigError("配置验证失败:\n  " + "\n  ".join(self.errors))

    def warnings(self) -> list[str]:
        return list(self.errors)


# ---------------------------------------------------------------------------
# 数据类
# ---------------------------------------------------------------------------


@dataclass
class LLMProviderConfig:
    """单个 LLM 提供商配置"""
    provider: str = "deepseek"
    provider_type: str = "openai_compatible"  # openai_compatible | anthropic | ollama
    api_key: str = ""
    base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-chat"
    max_tokens: int = DEFAULT_MAX_TOKENS
    timeout: int = LLM_TIMEOUT_SEC
    max_retries: int = 3
    # 限流
    rate_limit_rpm: int = 60
    rate_limit_rpd: int = 10000
    rate_limit_tpm: int = 180000
    # 费用（每 1M tokens，美元）
    cost_input_per_m: float = 0.0
    cost_output_per_m: float = 0.0

    @classmethod
    def from_provider(
        cls,
        provider_name: str = "deepseek",
        cli_args: Optional[dict[str, Any]] = None,
    ) -> "LLMProviderConfig":
        """
        从提供商名称 + 环境变量 + CLI 参数构建配置。
        优先级：CLI > 环境变量 > 预设默认值
        """
        cli_args = cli_args or {}

        preset = PROVIDER_PRESETS.get(provider_name, PROVIDER_PRESETS["deepseek"])
        prefix = preset["env_prefix"]

        # API key: CLI > 环境变量
        api_key = (
            cli_args.get("api_key")
            or _env(f"{prefix}_API_KEY")
            or _env("LLM_API_KEY")
            or ""
        )

        # Base URL: CLI > 环境变量 > 预设
        base_url = (
            cli_args.get("base_url")
            or _env(f"{prefix}_BASE_URL")
            or preset["base_url"]
        )

        # Model: CLI > 环境变量 > 预设
        model = (
            cli_args.get("model")
            or _env(f"{prefix}_MODEL")
            or _env("LLM_MODEL")
            or preset["default_model"]
        )

        # Provider type: CLI > 预设
        provider_type = cli_args.get("provider_type") or preset["provider_type"]

        # 费用
        costs = TYPICAL_COSTS.get(model, {"input": 0.0, "output": 0.0})
        cost_input = _env_float(f"{prefix}_COST_INPUT", costs["input"])
        cost_output = _env_float(f"{prefix}_COST_OUTPUT", costs["output"])

        return cls(
            provider=provider_name,
            provider_type=provider_type,
            api_key=api_key,
            base_url=base_url.rstrip("/"),
            model=model,
            max_tokens=cli_args.get("max_tokens") or _env_int("LLM_MAX_TOKENS", DEFAULT_MAX_TOKENS),
            timeout=cli_args.get("timeout") or _env_int("LLM_TIMEOUT", LLM_TIMEOUT_SEC),
            max_retries=cli_args.get("max_retries") or _env_int("LLM_MAX_RETRIES", 3),
            rate_limit_rpm=_env_int(f"{prefix}_RATE_RPM", 60),
            rate_limit_rpd=_env_int(f"{prefix}_RATE_RPD", 10000),
            rate_limit_tpm=_env_int(f"{prefix}_RATE_TPM", 180000),
            cost_input_per_m=cost_input,
            cost_output_per_m=cost_output,
        )

    def validate(self) -> list[str]:
        """验证并返回警告列表"""
        v = ConfigValidator()
        v.check(self.provider_type in VALID_PROVIDER_TYPES,
                f"不支持的 provider_type: {self.provider_type}")
        v.check(bool(self.base_url), "base_url 不能为空")
        v.check(bool(self.model), "model 不能为空")
        v.validate_range(self.timeout, "timeout", lo=1, hi=600)
        v.validate_range(self.max_tokens, "max_tokens", lo=1)
        v.validate_range(self.max_retries, "max_retries", lo=0, hi=10)
        if self.provider_type != "ollama":
            v.check(bool(self.api_key), f"[{self.provider}] 缺少 API Key")
        return v.errors


@dataclass
class AppConfig:
    """应用级配置"""
    # LLM
    llm: LLMProviderConfig = field(default_factory=LLMProviderConfig)
    # 应用参数
    search_max_results: int = SEARCH_MAX_RESULTS
    filter_batch_size: int = FILTER_BATCH_SIZE
    search_rate_limit_sec: float = SEARCH_RATE_LIMIT_SEC
    search_timeout_sec: int = SEARCH_TIMEOUT_SEC
    analyzer_batch_size: int = ANALYZER_BATCH_SIZE
    abstract_max_chars: int = ABSTRACT_MAX_CHARS
    organizer_max_analyses: int = ORGANIZER_MAX_ANALYSES
    writer_max_papers: int = WRITER_MAX_PAPERS
    review_max_chars: int = REVIEW_MAX_CHARS
    writer_max_tokens: int = WRITER_MAX_TOKENS
    # 成本追踪
    cost_tracking: bool = True
    cost_alert_threshold_usd: float = 10.0
    # 配置文件路径
    config_file: Optional[str] = None

    @classmethod
    def from_sources(
        cls,
        cli_args: Optional[dict[str, Any]] = None,
    ) -> "AppConfig":
        """
        从所有来源加载配置。
        优先级：CLI > 环境变量 > 配置文件 > 默认值
        """
        cli_args = cli_args or {}
        file_cfg = _load_config_file(cli_args.get("config_file"))

        # 确定 LLM 提供商
        provider_name = (
            cli_args.get("provider")
            or _env("LLM_PROVIDER")
            or file_cfg.get("provider")
            or "deepseek"
        )

        # 构建 LLM 配置
        llm_cfg = LLMProviderConfig.from_provider(
            provider_name=provider_name,
            cli_args=cli_args,
        )

        # 构建应用配置
        app_file = file_cfg.get("app", {})
        return cls(
            llm=llm_cfg,
            search_max_results=cli_args.get("search_max_results") or _env_int(
                "SEARCH_MAX_RESULTS", app_file.get("search_max_results", SEARCH_MAX_RESULTS)),
            filter_batch_size=cli_args.get("filter_batch_size") or _env_int(
                "FILTER_BATCH_SIZE", app_file.get("filter_batch_size", FILTER_BATCH_SIZE)),
            search_rate_limit_sec=cli_args.get("search_rate_limit_sec") or _env_float(
                "SEARCH_RATE_LIMIT", app_file.get("search_rate_limit_sec", SEARCH_RATE_LIMIT_SEC)),
            search_timeout_sec=cli_args.get("search_timeout_sec") or _env_int(
                "SEARCH_TIMEOUT", app_file.get("search_timeout_sec", SEARCH_TIMEOUT_SEC)),
            analyzer_batch_size=cli_args.get("analyzer_batch_size") or _env_int(
                "ANALYZER_BATCH_SIZE", app_file.get("analyzer_batch_size", ANALYZER_BATCH_SIZE)),
            abstract_max_chars=cli_args.get("abstract_max_chars") or _env_int(
                "ABSTRACT_MAX_CHARS", app_file.get("abstract_max_chars", ABSTRACT_MAX_CHARS)),
            organizer_max_analyses=cli_args.get("organizer_max_analyses") or _env_int(
                "ORGANIZER_MAX_ANALYSES", app_file.get("organizer_max_analyses", ORGANIZER_MAX_ANALYSES)),
            writer_max_papers=cli_args.get("writer_max_papers") or _env_int(
                "WRITER_MAX_PAPERS", app_file.get("writer_max_papers", WRITER_MAX_PAPERS)),
            review_max_chars=cli_args.get("review_max_chars") or _env_int(
                "REVIEW_MAX_CHARS", app_file.get("review_max_chars", REVIEW_MAX_CHARS)),
            writer_max_tokens=cli_args.get("writer_max_tokens") or _env_int(
                "WRITER_MAX_TOKENS", app_file.get("writer_max_tokens", WRITER_MAX_TOKENS)),
            cost_tracking=_env_bool("COST_TRACKING", app_file.get("cost_tracking", True)),
            cost_alert_threshold_usd=_env_float(
                "COST_ALERT_THRESHOLD", app_file.get("cost_alert_threshold_usd", 10.0)),
            config_file=cli_args.get("config_file"),
        )

    def validate(self) -> list[str]:
        """验证所有配置，返回错误列表"""
        errors = self.llm.validate()
        v = ConfigValidator()
        v.validate_range(self.search_max_results, "search_max_results", lo=1, hi=100)
        v.validate_range(self.filter_batch_size, "filter_batch_size", lo=1, hi=100)
        v.validate_range(self.analyzer_batch_size, "analyzer_batch_size", lo=1, hi=50)
        v.validate_range(self.writer_max_papers, "writer_max_papers", lo=1, hi=200)
        v.validate_range(self.review_max_chars, "review_max_chars", lo=1000, hi=100000)
        return errors + v.errors

    def summary(self) -> str:
        """返回配置摘要（隐藏密钥）"""
        masked_key = ""
        if self.llm.api_key:
            k = self.llm.api_key
            masked_key = k[:4] + "****" + k[-4:] if len(k) > 8 else "****"

        lines = [
            f"  LLM 提供商:   {self.llm.provider} ({self.llm.provider_type})",
            f"  模型:         {self.llm.model}",
            f"  Base URL:     {self.llm.base_url}",
            f"  API Key:      {masked_key or '(未设置)'}",
            f"  Max Tokens:   {self.llm.max_tokens}",
            f"  超时:         {self.llm.timeout}s",
            f"  限速:         {self.llm.rate_limit_rpm} RPM / {self.llm.rate_limit_tpm} TPM",
            f"  成本追踪:     {'开启' if self.cost_tracking else '关闭'}",
        ]
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# 向后兼容：旧代码 import config; config.DEFAULT_MAX_TOKENS 仍然可用
# ---------------------------------------------------------------------------

def get_config(cli_args: Optional[dict[str, Any]] = None) -> AppConfig:
    """便捷函数：从所有来源加载并验证配置"""
    cfg = AppConfig.from_sources(cli_args)
    errors = cfg.validate()
    if errors:
        raise ConfigError("配置验证失败:\n  " + "\n  ".join(errors))
    return cfg
