"""标准化错误类型层次结构"""


class SurveyError(Exception):
    """所有本系统错误的基类"""
    pass


class LLMError(SurveyError):
    """LLM 调用相关错误的基类"""
    pass


class LLMAPIError(LLMError):
    """LLM API 返回的 HTTP 错误"""

    def __init__(self, message: str, status_code: int = 0, response_body: str = ""):
        self.status_code = status_code
        self.response_body = response_body
        super().__init__(message)


class LLMRateLimitError(LLMAPIError):
    """API 限流 (429)"""
    pass


class LLMAuthError(LLMAPIError):
    """认证失败 (401/403)"""
    pass


class LLMTimeoutError(LLMError):
    """请求超时"""
    pass


class LLMNetworkError(LLMError):
    """网络连接错误"""
    pass


class LLMParseError(LLMError):
    """LLM 返回内容无法解析为目标格式"""

    def __init__(self, message: str, raw_text: str = ""):
        self.raw_text = raw_text
        super().__init__(message)


class ValidationError(SurveyError):
    """输入数据验证失败"""
    pass


class AgentError(SurveyError):
    """Agent 执行过程中的可恢复错误"""
    pass
