"""应用配置：从环境变量与 .env 读取，密钥只存在于服务端。"""

import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()

SERVICE_NAME = "aurel-api"
VERSION = "0.3.0"

DEFAULT_ARK_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
DEFAULT_DATABASE_URL = "sqlite:///./aurel.db"


def cors_origins() -> list[str]:
    default = "http://localhost:5173,http://127.0.0.1:5173"
    raw = os.getenv("AUREL_CORS_ORIGINS", default)
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


def database_url() -> str:
    return os.getenv("AUREL_DATABASE_URL", DEFAULT_DATABASE_URL).strip()


def ark_api_key() -> str:
    return os.getenv("ARK_API_KEY", "").strip()


def ark_base_url() -> str:
    return os.getenv("ARK_BASE_URL", DEFAULT_ARK_BASE_URL).strip()


def ark_model() -> str:
    return os.getenv("ARK_MODEL", "").strip()


@lru_cache(maxsize=1)
def ark_configured() -> bool:
    return bool(ark_api_key() and ark_model())


# ---- 语音识别（豆包语音 openspeech.bytedance.com，与方舟凭证相互独立）----

def speech_app_id() -> str:
    return os.getenv("SPEECH_APP_ID", "").strip()


def speech_access_token() -> str:
    return os.getenv("SPEECH_ACCESS_TOKEN", "").strip()


def speech_api_url() -> str:
    return os.getenv(
        "SPEECH_API_URL",
        "https://openspeech.bytedance.com/api/v3/auc/bigmodel/recognize/flash",
    ).strip()


@lru_cache(maxsize=1)
def asr_configured() -> bool:
    return bool(speech_app_id() and speech_access_token())


# ---- 语音识别提供方选择：auto | siliconflow | local | volcengine ----

def asr_provider_preference() -> str:
    return os.getenv("ASR_PROVIDER", "auto").strip().lower()


def siliconflow_api_key() -> str:
    return os.getenv("ASR_SILICONFLOW_API_KEY", "").strip()


def local_whisper_model() -> str:
    return os.getenv("ASR_LOCAL_MODEL", "small").strip()


def asr_hf_endpoint() -> str:
    """HuggingFace 下载端点；国内默认走 hf-mirror 镜像。"""
    return os.getenv("HF_ENDPOINT", "https://hf-mirror.com").strip()


# ---- 第五阶段：访问控制 / 限流 / 稳定性 / 模型实验 ----

def access_token() -> str:
    """AUREL_ACCESS_TOKEN：设置后所有 /api/v1 请求需携带 Bearer 令牌（健康与状态端点除外）。"""
    return os.getenv("AUREL_ACCESS_TOKEN", "").strip()


def rate_limit_per_minute() -> int:
    """每客户端 IP 每分钟请求上限；0 表示关闭限流。"""
    try:
        return int(os.getenv("AUREL_RATE_LIMIT_PER_MINUTE", "120").strip() or "120")
    except ValueError:
        return 120


def llm_experiment_model() -> str:
    """T10 实验模型：设置后按比例把部分真实流量路由到该模型做对比。"""
    return os.getenv("LLM_EXPERIMENT_MODEL", "").strip()


def llm_experiment_percent() -> float:
    """实验流量百分比（0-100），0 表示关闭实验。"""
    try:
        return float(os.getenv("LLM_EXPERIMENT_PERCENT", "0").strip() or "0")
    except ValueError:
        return 0.0


# ---- 会话 / 应用配置 ----

def session_ttl_hours() -> int:
    """会话有效期（小时），默认 168（7 天）。"""
    try:
        return int(os.getenv("AUREL_SESSION_TTL_HOURS", "168").strip() or "168")
    except ValueError:
        return 168


def cookie_secure() -> bool:
    """生产 HTTPS 环境应设为 true，使会话 Cookie 仅经 HTTPS 传输。"""
    return os.getenv("AUREL_COOKIE_SECURE", "").strip().lower() in ("1", "true", "yes")


def test_login_enabled() -> bool:
    """一键体验登录开关，默认开启；设 ENABLE_TEST_LOGIN=0 可关闭。"""
    return os.getenv("ENABLE_TEST_LOGIN", "1").strip().lower() not in ("0", "false", "no")
