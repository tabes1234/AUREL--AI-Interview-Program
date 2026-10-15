"""管理中心：使用事件采集（页面访问 + 真实业务操作）。

- record_event：业务操作成功落库后调用，事件随业务事务一起提交；
  采集失败只记日志，绝不影响业务主流程。
- record_page_view：登录用户的前端页面访问上报，带最小间隔去重，
  防止页面刷新/重复渲染导致统计失真。
- 只记录事件元数据（模块、事件名、状态、时间），不记录任何用户输入内容。
"""

import logging
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import UsageEvent, utcnow

logger = logging.getLogger("aurel.usage")

# 模块标识 → 展示名（管理中心与页面上报共用同一套标识）
MODULES: dict[str, str] = {
    "xingzhou": "行舟工作台",
    "zhitu": "知途规划",
    "wenlan": "问澜面试",
    "guanji": "观己图谱",
    "duheng": "度衡挑战",
    "huilan": "回澜错题",
    "zhigang": "知岗解析",
    "zhichao": "知潮岗位库",
    "lvli": "履历成章",
    "shibei": "拾贝模板库",
    "heqi": "合契匹配",
    "zhicang": "知藏知识库",
    "tinglan": "听澜表达",
    "xiezou": "协奏工作流",
    "huixiang": "回响报告",
    "auth": "账户",
}

# 同一用户同一事件的页面访问去重窗口（秒）：页面刷新、路由重渲染不重复计数
PAGE_VIEW_DEDUPE_SECONDS = 30


def module_label(module: str) -> str:
    return MODULES.get(module, module)


def record_event(
    db: Session,
    *,
    user_id: int | None,
    module: str,
    name: str,
    event_type: str = "action",
    status: str | None = "success",
) -> None:
    """记录一次业务事件（随调用方事务提交）。任何异常只记日志。"""
    try:
        db.add(
            UsageEvent(
                user_id=user_id,
                event_type=event_type,
                module=module[:40],
                name=name[:60],
                status=status,
            )
        )
        db.flush()
    except Exception:  # noqa: BLE001 — 观测写入绝不影响业务
        logger.warning("记录使用事件失败（不影响业务）", exc_info=True)
        db.rollback()


def record_page_view(db: Session, *, user_id: int, module: str, name: str) -> bool:
    """记录页面访问（带去重）。返回是否真实写入。"""
    try:
        cutoff = utcnow() - timedelta(seconds=PAGE_VIEW_DEDUPE_SECONDS)
        recent = db.scalar(
            select(UsageEvent.id)
            .where(
                UsageEvent.user_id == user_id,
                UsageEvent.module == module,
                UsageEvent.name == name,
                UsageEvent.event_type == "page_view",
                UsageEvent.created_at >= cutoff,
            )
            .limit(1)
        )
        if recent is not None:
            return False
        record_event(db, user_id=user_id, module=module, name=name, event_type="page_view")
        return True
    except Exception:  # noqa: BLE001 — 观测写入绝不影响业务
        logger.warning("记录页面访问失败（不影响业务）", exc_info=True)
        db.rollback()
        return False
