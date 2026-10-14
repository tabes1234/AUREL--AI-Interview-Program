"""T7：日志初始化与密钥脱敏。

约定：API Key / 令牌绝不进入日志。防御性地再给所有日志记录套一层脱敏过滤器，
即使某处代码意外打印了凭证形态的字符串，也会被遮蔽为 ***。
"""

import logging
import os
import re

_SECRET_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(Bearer\s+)[A-Za-z0-9\-._~+/]+=*", re.IGNORECASE), r"\1***"),
    (re.compile(r"(api[_-]?key\s*[=:]\s*)\S+", re.IGNORECASE), r"\1***"),
    (re.compile(r"(access[_-]?token\s*[=:]\s*)\S+", re.IGNORECASE), r"\1***"),
]


class SecretRedactionFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
            redacted = message
            for pattern, replacement in _SECRET_PATTERNS:
                redacted = pattern.sub(replacement, redacted)
            if redacted != message:
                record.msg = redacted
                record.args = ()
        except Exception:
            return True
        return True


def setup_logging() -> None:
    level = os.getenv("AUREL_LOG_LEVEL", "INFO").strip().upper() or "INFO"
    handler = logging.StreamHandler()
    handler.addFilter(SecretRedactionFilter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
