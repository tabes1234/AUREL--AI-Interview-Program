"""T10：模型调用观测——把每次真实模型调用的结果写入 llm_call_records。

观测使用独立的数据库会话，且写入失败只记日志、绝不影响业务调用。
测试可通过替换本模块的 `_session_factory` 指向测试引擎。
"""

import logging
from collections.abc import Callable

logger = logging.getLogger("aurel.observability")

_session_factory: Callable | None = None


def _factory() -> Callable:
    if _session_factory is not None:
        return _session_factory
    from app.database import SessionLocal

    return SessionLocal


def record_llm_call(
    *,
    service: str,
    model: str,
    prompt_version: str,
    status: str,
    attempts: int,
    latency_ms: int,
    error_type: str | None = None,
    error_message: str | None = None,
    experiment: bool = False,
    usage: dict | None = None,
) -> None:
    """记录一次模型调用。任何异常都被吞掉并降级为日志告警。"""
    try:
        session = _factory()()
        try:
            from app.models import LlmCallRecord

            session.add(
                LlmCallRecord(
                    service=service[:50],
                    model=model[:120] if model else "unknown",
                    prompt_version=prompt_version[:20],
                    status=status,
                    attempts=attempts,
                    latency_ms=latency_ms,
                    experiment=experiment,
                    error_type=error_type[:80] if error_type else None,
                    error_message=error_message[:2000] if error_message else None,
                    usage=usage,
                )
            )
            session.commit()
        finally:
            session.close()
    except Exception:
        logger.warning("记录 LLM 调用观测数据失败（不影响业务）", exc_info=True)
