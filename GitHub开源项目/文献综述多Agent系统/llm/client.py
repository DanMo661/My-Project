"""LLM 调用封装（DeepSeek API）"""

import json
import time
from typing import Optional
import requests


class LLMClient:
    """统一 LLM 调用接口"""

    def __init__(self, api_key: str, model: str = "deepseek-chat",
                 base_url: str = "https://api.deepseek.com"):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url

    def chat(self, messages: list[dict], system_prompt: str = "",
             temperature: float = 0.3, max_tokens: int = 4096,
             response_format: Optional[dict] = None) -> str:
        """调用 LLM chat"""
        full_messages = []
        if system_prompt:
            full_messages.append({"role": "system", "content": system_prompt})
        full_messages.extend(messages)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": full_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format:
            payload["response_format"] = response_format

        for attempt in range(3):
            try:
                resp = requests.post(
                    f"{self.base_url}/v1/chat/completions",
                    headers=headers, json=payload, timeout=60,
                )
                data = resp.json()
                if "choices" not in data:
                    time.sleep(2 ** attempt)
                    continue
                return data["choices"][0]["message"]["content"]
            except Exception as e:
                if attempt == 2:
                    raise
                time.sleep(2 ** attempt)
        return ""

    def structured_output(self, messages: list[dict], system_prompt: str,
                          temperature: float = 0.1) -> dict:
        """返回 JSON 结构化结果"""
        text = self.chat(
            messages, system_prompt,
            temperature=temperature,
            response_format={"type": "json_object"},
        )
        try:
            # 尝试提取 JSON
            start = text.index('{')
            end = text.rindex('}') + 1
            return json.loads(text[start:end])
        except (ValueError, json.JSONDecodeError):
            return {"error": "解析失败", "raw": text}
