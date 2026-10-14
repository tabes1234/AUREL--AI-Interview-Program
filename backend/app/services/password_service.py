"""密码摘要：PBKDF2-SHA256（标准库实现，不引入额外依赖）。

- 库内格式：pbkdf2_sha256$迭代次数$盐(hex)$哈希(hex)
- 校验使用 hmac.compare_digest 常量时间比较
- 密码明文绝不落库、绝不写入日志
"""

import hashlib
import hmac
import secrets

ITERATIONS = 240_000
_ALGORITHM = "pbkdf2_sha256"


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("ascii"), ITERATIONS)
    return f"{_ALGORITHM}${ITERATIONS}${salt}${digest.hex()}"


def verify_password(password: str, stored: str | None) -> bool:
    """校验密码；摘要格式异常一律返回 False（不抛异常、不泄露细节）。"""
    if not stored:
        return False
    parts = stored.split("$")
    if len(parts) != 4 or parts[0] != _ALGORITHM:
        return False
    try:
        iterations = int(parts[1])
    except ValueError:
        return False
    salt, expected_hex = parts[2], parts[3]
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("ascii"), iterations)
    return hmac.compare_digest(digest.hex(), expected_hex)
