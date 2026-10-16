"""管理中心统计服务：全部指标都来自真实数据库记录。

统一口径：
- 时区：统计以 UTC+8（北京时间）为基准；数据库内时间均为 naive UTC，
  查询边界按 +8 换算，按日聚合使用本地化（UTC+8）日期。
- 活跃用户：在指定时间窗口内至少产生一条「真实使用痕迹」的独立用户，
  痕迹来源为各业务表与使用事件表/模型调用表的归属用户（见 _activity_sources）。
  页面自动刷新、无操作停留不计入活跃。
- 页面访问：usage_events 中 event_type=page_view 的事件数（带 30 秒去重），
  自采集上线开始累计，之前的页面访问没有数据，如实显示「尚未采集」。
- 功能使用次数：usage_events 中 event_type=action 的事件数（后端真实业务
  操作成功后记录）；功能的历史累计量另由各业务表直接统计，两者口径分开。
- AI 请求数：llm_call_records 行数（每次真实模型调用一行，含重试最终结果）。
- 成功率：status=success 的占比（error 视为失败；取消事件暂无可靠采集来源）。
- 响应时间：llm_call_records.latency_ms，起点为发起模型请求、终点为拿到最终
  结果/错误，包含重试等待；首段输出时间（TTFT）尚未采集，不伪装成推理耗时。
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import Select, func, select, union_all
from sqlalchemy.orm import Session

from app.models import (
    AdminAuditLog,
    CareerConversation,
    CareerPathComparison,
    ChallengeRun,
    ExpressionAnalysis,
    InterviewTask,
    JobAnalysis,
    KnowledgeDocument,
    LlmCallRecord,
    MistakeCard,
    Resume,
    ResumeMatchRecord,
    UsageEvent,
    User,
)
from app.services.usage_tracking import MODULES, module_label

STATS_TZ = timezone(timedelta(hours=8))
STATS_TZ_LABEL = "UTC+8（北京时间）"
MAX_RANGE_DAYS = 366

# AI 服务标识 → 功能模块归属（与 ark_client 调用处的 service 参数一致）
AI_SERVICE_MODULES: dict[str, str] = {
    "question_set": "wenlan",
    "question_generator": "wenlan",
    "follow_up": "wenlan",
    "scoring": "wenlan",
    "career_guide": "zhitu",
    "career_analyst": "zhitu",
    "career_planner": "zhitu",
    "career_review": "zhitu",
    "career_summary": "zhitu",
    "career_fact_extract": "zhitu",
    "career_path_compare": "zhitu",
    "career_graph_extract": "zhitu",
    "resume_polish": "lvli",
    "resume_optimize": "lvli",
    "resume_parse": "lvli",
    "matching_suggestions": "heqi",
    "job_analysis": "zhigang",
    "gap_analysis": "guanji",
    "expression_workflow": "xiezou",
    "weekly_note": "xingzhou",
}

STATS_DEFINITIONS: dict[str, str] = {
    "累计注册用户": "截至统计时刻已注册且未删除的账户总数（users 表全量）。",
    "新增用户": "所选时间窗口内完成注册的独立用户数（users.created_at 落在窗口内）。",
    "活跃用户": (
        "所选窗口内至少产生一条真实使用痕迹的独立用户数；痕迹来源：使用事件、"
        "模型调用归属、面试任务、知途会话、简历、岗位解析、表达分析、挑战、"
        "错题、知识库、匹配记录、路径比较。页面停留与自动刷新不计入。"
    ),
    "DAU/WAU/MAU": (
        "以所选窗口结束日（UTC+8）为基准日：当天 / 最近 7 天 / 最近 30 天内"
        "至少一次真实使用痕迹的独立用户数。"
    ),
    "页面访问": (
        "登录用户在工作区页面的路由访问事件（usage_events.page_view，"
        "同一用户同一页面 30 秒内去重）。自采集上线起累计，此前无数据。"
    ),
    "功能使用次数": (
        "后端真实业务操作成功后记录的事件数（usage_events.action），"
        "与页面访问分开统计；功能的历史累计量由各业务表直接统计。"
    ),
    "AI 请求数": "每次真实模型调用一行（llm_call_records），含重试后的最终结果。",
    "AI 成功率": "status=success 的调用占比；error 视为失败；取消暂无可靠采集来源。",
    "AI 响应时间": (
        "latency_ms：从发起模型请求到拿到最终结果/错误的总耗时（含重试等待）；"
        "首段输出时间（TTFT）尚未采集，另行标注。"
    ),
    "Token 用量": "模型服务响应中返回的真实 usage 字段汇总；未返回用量的调用不计入。",
}


class RangeError(ValueError):
    """统计时间范围不合法。"""


def parse_range(
    start: str | None, end: str | None
) -> tuple[datetime, datetime, str, str]:
    """解析 YYYY-MM-DD（UTC+8 语义）为 naive UTC 半开区间 [utc_start, utc_end)。

    缺省最近 30 天；end 允许到今天。返回 (utc_start, utc_end, start_str, end_str)。
    """
    today = datetime.now(STATS_TZ).date()
    try:
        end_date = datetime.strptime(end, "%Y-%m-%d").date() if end else today
        start_date = (
            datetime.strptime(start, "%Y-%m-%d").date() if start else end_date - timedelta(days=29)
        )
    except ValueError as exc:
        raise RangeError("日期格式需为 YYYY-MM-DD") from exc
    if start_date > end_date:
        raise RangeError("开始日期不能晚于结束日期")
    if (end_date - start_date).days + 1 > MAX_RANGE_DAYS:
        raise RangeError(f"统计范围最多 {MAX_RANGE_DAYS} 天")
    utc_start = datetime(start_date.year, start_date.month, start_date.day, tzinfo=STATS_TZ).astimezone(
        timezone.utc
    ).replace(tzinfo=None)
    utc_end = (
        datetime(end_date.year, end_date.month, end_date.day, tzinfo=STATS_TZ) + timedelta(days=1)
    ).astimezone(timezone.utc).replace(tzinfo=None)
    return utc_start, utc_end, start_date.isoformat(), end_date.isoformat()


def _day_key(dt: datetime) -> str:
    """naive UTC → UTC+8 日期字符串（按日聚合的 key）。"""
    return (dt + timedelta(hours=8)).date().isoformat()


def _day_series(start_iso: str, end_iso: str) -> list[str]:
    d0 = datetime.strptime(start_iso, "%Y-%m-%d").date()
    d1 = datetime.strptime(end_iso, "%Y-%m-%d").date()
    return [(d0 + timedelta(days=i)).isoformat() for i in range((d1 - d0).days + 1)]


def _blank_days(days: list[str]) -> dict[str, int]:
    return {day: 0 for day in days}


def _activity_sources(start: datetime | None = None, end: datetime | None = None) -> list[Select]:
    """活跃痕迹来源：各业务表（user_id + created_at）+ 使用事件 + 模型调用归属。"""

    def windowed(stmt: Select, ts_col) -> Select:
        if start is not None:
            stmt = stmt.where(ts_col >= start)
        if end is not None:
            stmt = stmt.where(ts_col < end)
        return stmt

    pairs = (
        (UsageEvent.user_id, UsageEvent.created_at),
        (LlmCallRecord.user_id, LlmCallRecord.created_at),
        (InterviewTask.user_id, InterviewTask.created_at),
        (CareerConversation.user_id, CareerConversation.created_at),
        (Resume.user_id, Resume.created_at),
        (JobAnalysis.user_id, JobAnalysis.created_at),
        (ExpressionAnalysis.user_id, ExpressionAnalysis.created_at),
        (ChallengeRun.user_id, ChallengeRun.created_at),
        (KnowledgeDocument.user_id, KnowledgeDocument.created_at),
        (ResumeMatchRecord.user_id, ResumeMatchRecord.created_at),
        (MistakeCard.user_id, MistakeCard.created_at),
        (CareerPathComparison.user_id, CareerPathComparison.created_at),
    )
    return [
        windowed(select(uid.label("user_id"), ts.label("ts")).where(uid.is_not(None)), ts)
        for uid, ts in pairs
    ]


def _active_user_ids(db: Session, start: datetime, end: datetime) -> set[int]:
    union = union_all(*_activity_sources(start, end))
    rows = db.execute(select(union.subquery().c.user_id).distinct()).all()
    return {row[0] for row in rows if row[0] is not None}


def _active_counts_asof(db: Session, ref_date) -> dict[str, int]:
    """以 ref_date（UTC+8 日期）为基准日的 DAU/WAU/MAU。"""

    def day_window(days: int) -> tuple[datetime, datetime]:
        end_local = datetime(ref_date.year, ref_date.month, ref_date.day, tzinfo=STATS_TZ) + timedelta(days=1)
        start_local = end_local - timedelta(days=days)
        return (
            start_local.astimezone(timezone.utc).replace(tzinfo=None),
            end_local.astimezone(timezone.utc).replace(tzinfo=None),
        )

    result = {}
    for key, span in (("dau", 1), ("wau", 7), ("mau", 30)):
        start, end = day_window(span)
        result[key] = len(_active_user_ids(db, start, end))
    return result


def _pencentile(sorted_values: list[int], ratio: float) -> int | None:
    if not sorted_values:
        return None
    idx = min(len(sorted_values) - 1, max(0, round(ratio * (len(sorted_values) - 1))))
    return sorted_values[idx]


def _ai_window_rows(db: Session, start: datetime, end: datetime) -> list[LlmCallRecord]:
    stmt = select(LlmCallRecord).where(
        LlmCallRecord.created_at >= start, LlmCallRecord.created_at < end
    )
    return list(db.scalars(stmt))


def _ai_summary(rows: list[LlmCallRecord]) -> dict:
    total = len(rows)
    success = sum(1 for r in rows if r.status == "success")
    latencies = sorted(r.latency_ms for r in rows if r.status == "success" and r.latency_ms > 0)
    tokens_in = tokens_out = 0
    tokens_known = 0
    for r in rows:
        usage = r.usage if isinstance(r.usage, dict) else None
        if not usage:
            continue
        p = usage.get("prompt_tokens")
        c = usage.get("completion_tokens")
        if isinstance(p, (int, float)) or isinstance(c, (int, float)):
            tokens_known += 1
            tokens_in += int(p or 0)
            tokens_out += int(c or 0)
    error_count = total - success
    return {
        "total": total,
        "success": success,
        "failed": error_count,
        "success_rate": round(success / total, 4) if total else None,
        "avg_latency_ms": round(sum(latencies) / len(latencies)) if latencies else None,
        "p50_ms": _pencentile(latencies, 0.50),
        "p95_ms": _pencentile(latencies, 0.95),
        "tokens_input": tokens_in if tokens_known else None,
        "tokens_output": tokens_out if tokens_known else None,
        "tokens_total": (tokens_in + tokens_out) if tokens_known else None,
        "calls_with_usage": tokens_known,
    }


def _error_category(record: LlmCallRecord) -> str:
    et = (record.error_type or "").lower()
    if "timeout" in et or et in {"http408", "http598"}:
        return "请求超时"
    if et in {"http401", "http403"}:
        return "权限或凭证错误"
    if et == "http429":
        return "调用限额（429）"
    if et.startswith("http"):
        return "模型服务返回错误"
    if et in {"badresponse"}:
        return "响应解析失败"
    if et in {"arknotconfigurederror", "notconfigured"}:
        return "配置缺失"
    if et in {"connectionerror", "connecterror"}:
        return "网络异常"
    if et:
        return "其他未分类错误"
    return "未知错误"


def _mask_message(message: str | None) -> str | None:
    """错误摘要脱敏：截断长度，剔除疑似凭证片段。"""
    if not message:
        return None
    text = message[:300]
    for keyword in ("Bearer ", "api_key", "apikey", "sk-", "Authorization"):
        text = text.replace(keyword, "[已脱敏]")
    return text


def overview(db: Session, start: datetime, end: datetime, start_iso: str, end_iso: str) -> dict:
    ref_date = datetime.strptime(end_iso, "%Y-%m-%d").date()

    total_users = db.scalar(select(func.count(User.id))) or 0
    disabled_users = db.scalar(
        select(func.count(User.id)).where(User.status != "active")
    ) or 0
    new_users = db.scalar(
        select(func.count(User.id)).where(User.created_at >= start, User.created_at < end)
    ) or 0

    active_ids = _active_user_ids(db, start, end)
    dau_wau_mau = _active_counts_asof(db, ref_date)

    page_views = db.scalar(
        select(func.count(UsageEvent.id)).where(
            UsageEvent.event_type == "page_view",
            UsageEvent.created_at >= start,
            UsageEvent.created_at < end,
        )
    ) or 0

    # 模块使用：事件口径（窗口内）
    module_rows = db.execute(
        select(
            UsageEvent.module,
            UsageEvent.event_type,
            UsageEvent.status,
            func.count(UsageEvent.id),
            func.max(UsageEvent.created_at),
            func.count(func.distinct(UsageEvent.user_id)),
        )
        .where(UsageEvent.created_at >= start, UsageEvent.created_at < end)
        .group_by(UsageEvent.module, UsageEvent.event_type, UsageEvent.status)
    ).all()
    modules: dict[str, dict] = {
        key: {
            "module": key,
            "label": module_label(key),
            "page_views": 0,
            "actions": 0,
            "action_errors": 0,
            "users": 0,
            "last_used": None,
        }
        for key in MODULES
    }
    for module, event_type, status, count, last_used, users in module_rows:
        bucket = modules.setdefault(
            module,
            {
                "module": module,
                "label": module_label(module),
                "page_views": 0,
                "actions": 0,
                "action_errors": 0,
                "users": 0,
                "last_used": None,
            },
        )
        bucket["users"] = max(bucket["users"], users or 0)
        if last_used and (bucket["last_used"] is None or last_used > bucket["last_used"]):
            bucket["last_used"] = last_used
        if event_type == "page_view":
            bucket["page_views"] += count
        else:
            bucket["actions"] += count
            if status and status != "success":
                bucket["action_errors"] += count
    module_list = sorted(modules.values(), key=lambda m: (-m["actions"], -m["page_views"], m["module"]))

    ai_rows = _ai_window_rows(db, start, end)
    ai = _ai_summary(ai_rows)

    collection_started = db.scalar(select(func.min(UsageEvent.created_at)))

    return {
        "generated_at": datetime.now(STATS_TZ).isoformat(timespec="seconds"),
        "timezone": STATS_TZ_LABEL,
        "range": {"start": start_iso, "end": end_iso},
        "collection_started_at": collection_started.isoformat(timespec="seconds")
        if collection_started
        else None,
        "users": {
            "total": total_users,
            "disabled": disabled_users,
            "new_in_range": new_users,
            "active_in_range": len(active_ids),
            **dau_wau_mau,
        },
        "pages": {
            "views_in_range": page_views,
            "note": "页面访问自采集上线开始记录，此前无数据" if collection_started else "尚未采集",
        },
        "modules": module_list,
        "ai": ai,
        "definitions": STATS_DEFINITIONS,
    }


def trends(db: Session, start: datetime, end: datetime, start_iso: str, end_iso: str) -> dict:
    days = _day_series(start_iso, end_iso)

    def daily_counts(stmt_rows: list[tuple[str, int]]) -> dict[str, int]:
        result = _blank_days(days)
        for day, count in stmt_rows:
            if day in result:
                result[day] += count
        return result

    new_rows = db.execute(
        select(
            func.strftime("%Y-%m-%d", func.datetime(User.created_at, "+8 hours")).label("day"),
            func.count(User.id),
        )
        .where(User.created_at >= start, User.created_at < end)
        .group_by("day")
    ).all()
    new_users = daily_counts([(r[0], r[1]) for r in new_rows])

    # 活跃按日：union_all 后在 Python 里按日去重（数据量可控，避免复杂 SQL）
    union = union_all(*_activity_sources(start, end))
    sub = union.subquery()
    rows = db.execute(select(sub.c.user_id, sub.c.ts).where(sub.c.user_id.is_not(None))).all()
    active_by_day_sets: dict[str, set[int]] = {day: set() for day in days}
    for user_id, ts in rows:
        key = _day_key(ts)
        if key in active_by_day_sets and user_id is not None:
            active_by_day_sets[key].add(user_id)
    active_users = {day: len(ids) for day, ids in active_by_day_sets.items()}

    page_rows = db.execute(
        select(
            func.strftime("%Y-%m-%d", func.datetime(UsageEvent.created_at, "+8 hours")).label("day"),
            func.count(UsageEvent.id),
        )
        .where(
            UsageEvent.event_type == "page_view",
            UsageEvent.created_at >= start,
            UsageEvent.created_at < end,
        )
        .group_by("day")
    ).all()
    page_views = daily_counts([(r[0], r[1]) for r in page_rows])

    module_day_rows = db.execute(
        select(
            UsageEvent.module,
            func.strftime("%Y-%m-%d", func.datetime(UsageEvent.created_at, "+8 hours")).label("day"),
            func.count(UsageEvent.id),
        )
        .where(
            UsageEvent.event_type == "action",
            UsageEvent.created_at >= start,
            UsageEvent.created_at < end,
        )
        .group_by(UsageEvent.module, "day")
    ).all()
    module_usage: dict[str, dict[str, int]] = {}
    for module, day, count in module_day_rows:
        module_usage.setdefault(module, _blank_days(days))
        if day in module_usage[module]:
            module_usage[module][day] += count

    ai_rows = _ai_window_rows(db, start, end)
    ai_req_by_day: dict[str, int] = _blank_days(days)
    ai_err_by_day: dict[str, int] = _blank_days(days)
    ai_lat_sum: dict[str, int] = _blank_days(days)
    ai_lat_n: dict[str, int] = _blank_days(days)
    tokens_by_day: dict[str, int] = _blank_days(days)
    for r in ai_rows:
        key = _day_key(r.created_at)
        if key not in ai_req_by_day:
            continue
        ai_req_by_day[key] += 1
        if r.status != "success":
            ai_err_by_day[key] += 1
        elif r.latency_ms > 0:
            ai_lat_sum[key] += r.latency_ms
            ai_lat_n[key] += 1
        usage = r.usage if isinstance(r.usage, dict) else None
        if usage:
            total_tokens = usage.get("total_tokens")
            if isinstance(total_tokens, (int, float)):
                tokens_by_day[key] += int(total_tokens)

    ai_success_rate: dict[str, float | None] = {}
    ai_avg_latency: dict[str, int | None] = {}
    for day in days:
        req = ai_req_by_day[day]
        ok = req - ai_err_by_day[day]
        ai_success_rate[day] = round(ok / req, 4) if req else None
        ai_avg_latency[day] = (
            round(ai_lat_sum[day] / ai_lat_n[day]) if ai_lat_n[day] else None
        )

    return {
        "range": {"start": start_iso, "end": end_iso},
        "days": days,
        "series": {
            "new_users": new_users,
            "active_users": active_users,
            "page_views": page_views,
            "module_usage": module_usage,
            "ai_requests": ai_req_by_day,
            "ai_errors": ai_err_by_day,
            "ai_success_rate": ai_success_rate,
            "ai_avg_latency_ms": ai_avg_latency,
            "tokens_total": tokens_by_day,
        },
        "notes": {
            "page_views": "页面访问自采集上线开始记录，早期日期为 0 表示尚未采集",
            "tokens": "仅统计模型服务返回了真实 usage 的调用",
        },
    }


def users_page(
    db: Session,
    *,
    start: datetime,
    end: datetime,
    q: str | None,
    status: str | None,
    registered_start: str | None,
    registered_end: str | None,
    sort: str,
    page: int,
    page_size: int,
) -> dict:
    stmt = select(User)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(User.username.like(like) | User.nickname.like(like))
    if status in {"active", "disabled"}:
        stmt = stmt.where(User.status == status)
    if registered_start:
        try:
            rs = datetime.strptime(registered_start, "%Y-%m-%d")
            rs_utc = rs - timedelta(hours=8)
            stmt = stmt.where(User.created_at >= rs_utc)
        except ValueError as exc:
            raise RangeError("注册起始日期格式需为 YYYY-MM-DD") from exc
    if registered_end:
        try:
            re_date = datetime.strptime(registered_end, "%Y-%m-%d") + timedelta(days=1)
            re_utc = re_date - timedelta(hours=8)
            stmt = stmt.where(User.created_at < re_utc)
        except ValueError as exc:
            raise RangeError("注册结束日期格式需为 YYYY-MM-DD") from exc

    page = max(1, page)
    page_size = min(100, max(5, page_size))

    # 窗口内聚合（子查询，供展示与排序）：使用次数 + 最近操作（含模块）+ AI 调用
    usage_agg = (
        select(
            UsageEvent.user_id.label("user_id"),
            func.count(UsageEvent.id).label("usage_count"),
            func.max(UsageEvent.created_at).label("last_event_at"),
            # SQLite 聚合特有：bare column 与 max() 同用时取 max 行的值
            UsageEvent.module.label("last_module"),
        )
        .where(UsageEvent.created_at >= start, UsageEvent.created_at < end)
        .group_by(UsageEvent.user_id)
        .subquery()
    )
    ai_agg = (
        select(
            LlmCallRecord.user_id.label("user_id"),
            func.count(LlmCallRecord.id).label("ai_calls"),
            func.max(LlmCallRecord.created_at).label("last_ai_at"),
        )
        .where(LlmCallRecord.created_at >= start, LlmCallRecord.created_at < end)
        .group_by(LlmCallRecord.user_id)
        .subquery()
    )

    usage_count_col = func.coalesce(usage_agg.c.usage_count, 0)
    ai_calls_col = func.coalesce(ai_agg.c.ai_calls, 0)
    # 标量 max(a,b)（SQLite 两参数形式）取两者较晚者；各自先 coalesce 兜底 NULL
    last_active_col = func.max(
        func.coalesce(usage_agg.c.last_event_at, ai_agg.c.last_ai_at),
        func.coalesce(ai_agg.c.last_ai_at, usage_agg.c.last_event_at),
    )

    order_map = {
        "created_at": [User.created_at.desc()],
        "last_login": [User.last_login_at.desc().nullslast()],
        "username": [User.username.asc()],
        "usage": [usage_count_col.desc(), User.id.desc()],
        "ai": [ai_calls_col.desc(), User.id.desc()],
        "last_active": [last_active_col.desc().nullslast(), User.id.desc()],
    }
    for order in order_map.get(sort, order_map["created_at"]):
        stmt = stmt.order_by(order)

    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    rows = db.execute(
        select(
            User,
            usage_count_col.label("usage_count_val"),
            usage_agg.c.last_module.label("last_module_val"),
            ai_calls_col.label("ai_calls_val"),
            last_active_col.label("last_active_val"),
        )
        .where(
            User.id.in_(
                select(stmt.order_by(None).subquery().c.id).offset((page - 1) * page_size).limit(page_size)
            )
        )
        .outerjoin(usage_agg, usage_agg.c.user_id == User.id)
        .outerjoin(ai_agg, ai_agg.c.user_id == User.id)
        .order_by(*order_map.get(sort, order_map["created_at"]))
    ).all()

    items = []
    for user, usage_count, last_module, ai_calls, last_ts in rows:
        last_active_at = last_ts or user.last_login_at
        items.append(
            {
                "id": user.id,
                "username": user.username,
                "nickname": user.nickname,
                "status": user.status,
                "role": getattr(user, "role", "user") or "user",
                "created_at": user.created_at.isoformat(timespec="seconds"),
                "last_login_at": user.last_login_at.isoformat(timespec="seconds")
                if user.last_login_at
                else None,
                "last_active_at": last_active_at.isoformat(timespec="seconds")
                if last_active_at
                else None,
                "usage_count": usage_count,
                "ai_calls": ai_calls,
                "last_module": module_label(last_module) if last_module else None,
            }
        )

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size,
        "items": items,
        "range": {"start": start.isoformat(), "end": end.isoformat()},
    }


def user_detail(
    db: Session, *, target: User, start: datetime, end: datetime, start_iso: str, end_iso: str
) -> dict:
    """单用户使用情况：功能使用 + AI 调用 + 按日趋势。不包含任何私人内容。"""
    uid = target.id
    days = _day_series(start_iso, end_iso)

    # 功能使用（事件口径，窗口内）
    event_rows = db.execute(
        select(
            UsageEvent.module,
            UsageEvent.event_type,
            UsageEvent.status,
            func.count(UsageEvent.id),
            func.max(UsageEvent.created_at),
        )
        .where(
            UsageEvent.user_id == uid,
            UsageEvent.created_at >= start,
            UsageEvent.created_at < end,
        )
        .group_by(UsageEvent.module, UsageEvent.event_type, UsageEvent.status)
    ).all()
    modules: dict[str, dict] = {}
    for module, event_type, status, count, last_used in event_rows:
        bucket = modules.setdefault(
            module,
            {
                "module": module,
                "label": module_label(module),
                "page_views": 0,
                "actions": 0,
                "action_errors": 0,
                "last_used": None,
            },
        )
        if last_used and (bucket["last_used"] is None or last_used > bucket["last_used"]):
            bucket["last_used"] = last_used
        if event_type == "page_view":
            bucket["page_views"] += count
        else:
            bucket["actions"] += count
            if status and status != "success":
                bucket["action_errors"] += count

    # 功能历史累计（业务表口径，真实落库记录）
    historical = {
        "面试任务（问澜）": db.scalar(
            select(func.count(InterviewTask.id)).where(InterviewTask.user_id == uid)
        ) or 0,
        "知途会话": db.scalar(
            select(func.count(CareerConversation.id)).where(CareerConversation.user_id == uid)
        ) or 0,
        "简历（履历成章）": db.scalar(
            select(func.count(Resume.id)).where(Resume.user_id == uid)
        ) or 0,
        "岗位解析（知岗）": db.scalar(
            select(func.count(JobAnalysis.id)).where(JobAnalysis.user_id == uid)
        ) or 0,
        "表达分析（协奏）": db.scalar(
            select(func.count(ExpressionAnalysis.id)).where(ExpressionAnalysis.user_id == uid)
        ) or 0,
        "限时挑战（度衡）": db.scalar(
            select(func.count(ChallengeRun.id)).where(ChallengeRun.user_id == uid)
        ) or 0,
        "错题卡片（回澜）": db.scalar(
            select(func.count(MistakeCard.id)).where(MistakeCard.user_id == uid)
        ) or 0,
        "知识文档（知藏）": db.scalar(
            select(func.count(KnowledgeDocument.id)).where(KnowledgeDocument.user_id == uid)
        ) or 0,
        "匹配记录（合契）": db.scalar(
            select(func.count(ResumeMatchRecord.id)).where(ResumeMatchRecord.user_id == uid)
        ) or 0,
        "路径比较（知途）": db.scalar(
            select(func.count(CareerPathComparison.id)).where(CareerPathComparison.user_id == uid)
        ) or 0,
    }

    # AI 调用：窗口内 + 全部
    ai_rows = list(
        db.scalars(
            select(LlmCallRecord).where(
                LlmCallRecord.user_id == uid,
                LlmCallRecord.created_at >= start,
                LlmCallRecord.created_at < end,
            )
        )
    )
    ai_all_rows = list(db.scalars(select(LlmCallRecord).where(LlmCallRecord.user_id == uid)))

    # 按日事件趋势（页面访问 + 操作）
    trend_rows = db.execute(
        select(
            func.strftime("%Y-%m-%d", func.datetime(UsageEvent.created_at, "+8 hours")).label("day"),
            UsageEvent.event_type,
            func.count(UsageEvent.id),
        )
        .where(
            UsageEvent.user_id == uid,
            UsageEvent.created_at >= start,
            UsageEvent.created_at < end,
        )
        .group_by("day", UsageEvent.event_type)
    ).all()
    trend = {
        "page_views": _blank_days(days),
        "actions": _blank_days(days),
    }
    for day, event_type, count in trend_rows:
        if day not in trend["page_views"]:
            continue
        key = "page_views" if event_type == "page_view" else "actions"
        trend[key][day] += count

    last_event = db.scalar(
        select(UsageEvent.created_at)
        .where(UsageEvent.user_id == uid)
        .order_by(UsageEvent.created_at.desc())
        .limit(1)
    )
    last_active_at = max(
        [t for t in (last_event, target.last_login_at) if t is not None], default=None
    )

    return {
        "user": {
            "id": target.id,
            "username": target.username,
            "nickname": target.nickname,
            "status": target.status,
            "role": getattr(target, "role", "user") or "user",
            "created_at": target.created_at.isoformat(timespec="seconds"),
            "last_login_at": target.last_login_at.isoformat(timespec="seconds")
            if target.last_login_at
            else None,
            "last_active_at": last_active_at.isoformat(timespec="seconds")
            if last_active_at
            else None,
        },
        "range": {"start": start_iso, "end": end_iso},
        "modules_in_range": sorted(
            modules.values(),
            key=lambda m: (-(m["actions"] + m["page_views"]), m["module"]),
        ),
        "historical_counts": [
            {"feature": k, "count": v} for k, v in historical.items()
        ],
        "ai_in_range": _ai_summary(ai_rows),
        "ai_all_time": _ai_summary(ai_all_rows),
        "trend": {"days": days, **trend},
    }


def module_stats(
    db: Session, *, start: datetime, end: datetime, start_iso: str, end_iso: str
) -> dict:
    """功能模块统计：页面访问与真实业务操作分开计数。"""
    days = _day_series(start_iso, end_iso)
    rows = db.execute(
        select(
            UsageEvent.module,
            UsageEvent.event_type,
            UsageEvent.status,
            func.count(UsageEvent.id),
            func.count(func.distinct(UsageEvent.user_id)),
            func.max(UsageEvent.created_at),
        )
        .where(UsageEvent.created_at >= start, UsageEvent.created_at < end)
        .group_by(UsageEvent.module, UsageEvent.event_type, UsageEvent.status)
    ).all()

    modules: dict[str, dict] = {}
    for module, event_type, status, count, users, last_used in rows:
        bucket = modules.setdefault(
            module,
            {
                "module": module,
                "label": module_label(module),
                "page_views": 0,
                "actions": 0,
                "action_success": 0,
                "action_errors": 0,
                "users": 0,
                "last_used": None,
            },
        )
        bucket["users"] = max(bucket["users"], users or 0)
        if last_used and (bucket["last_used"] is None or last_used > bucket["last_used"]):
            bucket["last_used"] = last_used.isoformat(timespec="seconds")
        if event_type == "page_view":
            bucket["page_views"] += count
        else:
            bucket["actions"] += count
            if status is None or status == "success":
                bucket["action_success"] += count
            else:
                bucket["action_errors"] += count

    # 每模块按日操作趋势
    day_rows = db.execute(
        select(
            UsageEvent.module,
            func.strftime("%Y-%m-%d", func.datetime(UsageEvent.created_at, "+8 hours")).label("day"),
            func.count(UsageEvent.id),
        )
        .where(
            UsageEvent.event_type == "action",
            UsageEvent.created_at >= start,
            UsageEvent.created_at < end,
        )
        .group_by(UsageEvent.module, "day")
    ).all()
    trends_map: dict[str, dict[str, int]] = {}
    for module, day, count in day_rows:
        trends_map.setdefault(module, _blank_days(days))
        if day in trends_map[module]:
            trends_map[module][day] += count

    items = []
    for key in MODULES:
        item = modules.get(
            key,
            {
                "module": key,
                "label": module_label(key),
                "page_views": 0,
                "actions": 0,
                "action_success": 0,
                "action_errors": 0,
                "users": 0,
                "last_used": None,
            },
        )
        item["trend"] = trends_map.get(key, {d: 0 for d in days})
        items.append(item)
    items.sort(key=lambda m: (-(m["actions"] + m["page_views"]), m["module"]))

    return {
        "range": {"start": start_iso, "end": end_iso},
        "timezone": STATS_TZ_LABEL,
        "days": days,
        "items": items,
        "note": "页面访问（page_view）与真实业务操作（action）分开统计；历史累计请见各业务数据",
    }


def ai_stats(
    db: Session, *, start: datetime, end: datetime, start_iso: str, end_iso: str, limit: int = 20
) -> dict:
    """AI 调用统计：请求量、成功率、耗时分布、错误分类、Token 用量。"""
    rows = _ai_window_rows(db, start, end)
    summary = _ai_summary(rows)

    timeouts = sum(1 for r in rows if _error_category(r) == "请求超时")

    # 按服务
    by_service: dict[str, list[LlmCallRecord]] = {}
    for r in rows:
        by_service.setdefault(r.service, []).append(r)
    service_items = []
    for service, svc_rows in by_service.items():
        s = _ai_summary(svc_rows)
        service_items.append(
            {
                "service": service,
                "module": AI_SERVICE_MODULES.get(service),
                "module_label": module_label(AI_SERVICE_MODULES[service])
                if service in AI_SERVICE_MODULES
                else "未归属模块",
                **s,
            }
        )
    service_items.sort(key=lambda x: -x["total"])

    # 按模型
    by_model: dict[str, dict] = {}
    for r in rows:
        bucket = by_model.setdefault(r.model, {"model": r.model, "total": 0, "tokens_total": 0, "has_usage": False})
        bucket["total"] += 1
        usage = r.usage if isinstance(r.usage, dict) else None
        if usage and isinstance(usage.get("total_tokens"), (int, float)):
            bucket["tokens_total"] += int(usage["total_tokens"])
            bucket["has_usage"] = True
    model_items = sorted(by_model.values(), key=lambda x: -x["total"])

    # 错误分类
    error_buckets: dict[str, int] = {}
    recent_errors = []
    for r in rows:
        if r.status == "success":
            continue
        category = _error_category(r)
        error_buckets[category] = error_buckets.get(category, 0) + 1
        recent_errors.append(
            {
                "id": r.id,
                "created_at": r.created_at.isoformat(timespec="seconds"),
                "service": r.service,
                "module_label": module_label(AI_SERVICE_MODULES[r.service])
                if r.service in AI_SERVICE_MODULES
                else "未归属模块",
                "error_type": r.error_type,
                "category": category,
                "message": _mask_message(r.error_message),
            }
        )
    recent_errors.sort(key=lambda x: x["created_at"], reverse=True)

    return {
        "range": {"start": start_iso, "end": end_iso},
        "timezone": STATS_TZ_LABEL,
        "totals": {**summary, "timeouts": timeouts if summary["total"] else None},
        "by_service": service_items,
        "by_model": model_items,
        "error_categories": [
            {"category": k, "count": v}
            for k, v in sorted(error_buckets.items(), key=lambda x: -x[1])
        ],
        "recent_errors": recent_errors[: max(1, min(50, limit))],
        "notes": {
            "first_output": "首段输出时间（TTFT）尚未采集：当前 latency 为请求总耗时，不伪装成模型推理耗时",
            "cancelled": "客户端取消事件暂无可靠采集来源，不提供估计值",
            "tokens": "Token 用量来自模型服务响应中的真实 usage 字段；未返回用量的调用不计入",
            "cost": "各渠道实际计价方式不同且可能变动，暂不折算费用，避免误导",
        },
    }


def recent_activity(db: Session, *, limit: int = 12) -> dict:
    """近期系统级活动摘要（脱敏：不含聊天正文/简历内容/凭证）。"""
    items: list[dict] = []

    for user in db.scalars(select(User).order_by(User.created_at.desc()).limit(limit)):
        items.append(
            {
                "type": "register",
                "label": f"新用户加入：{user.nickname or user.username}",
                "at": user.created_at.isoformat(timespec="seconds"),
            }
        )

    for event in db.scalars(
        select(UsageEvent)
        .where(UsageEvent.event_type == "action")
        .order_by(UsageEvent.created_at.desc())
        .limit(limit)
    ):
        user = db.get(User, event.user_id) if event.user_id else None
        who = (user.nickname or user.username) if user else "未归属用户"
        items.append(
            {
                "type": "action",
                "label": f"{who} 使用了{module_label(event.module)}",
                "detail": event.name,
                "at": event.created_at.isoformat(timespec="seconds"),
            }
        )

    for r in db.scalars(
        select(LlmCallRecord)
        .where(LlmCallRecord.status != "success")
        .order_by(LlmCallRecord.created_at.desc())
        .limit(limit)
    ):
        items.append(
            {
                "type": "ai_error",
                "label": f"AI 调用失败：{module_label(AI_SERVICE_MODULES.get(r.service, '')) or r.service}",
                "detail": _error_category(r),
                "at": r.created_at.isoformat(timespec="seconds"),
            }
        )

    items.sort(key=lambda x: x["at"], reverse=True)
    return {"items": items[: max(1, min(30, limit))]}


def audit_list(db: Session, *, page: int, page_size: int) -> dict:
    stmt = select(AdminAuditLog).order_by(AdminAuditLog.created_at.desc())
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    page = max(1, page)
    page_size = min(100, max(5, page_size))
    rows = list(db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)))
    items = []
    for log in rows:
        admin = db.get(User, log.admin_user_id)
        items.append(
            {
                "id": log.id,
                "admin": (admin.nickname or admin.username) if admin else f"#{log.admin_user_id}",
                "action": log.action,
                "target_type": log.target_type,
                "target_id": log.target_id,
                "detail": log.detail,
                "created_at": log.created_at.isoformat(timespec="seconds"),
            }
        )
    return {"total": total, "page": page, "page_size": page_size, "items": items}


def _csv_response(rows: list[dict], headers: list[str]) -> str:
    import csv
    import io

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(headers)
    for row in rows:
        writer.writerow([row.get(h, "") for h in headers])
    return buffer.getvalue()


def export_csv(
    db: Session,
    *,
    kind: str,
    start: datetime,
    end: datetime,
    start_iso: str,
    end_iso: str,
) -> tuple[str, str]:
    """导出脱敏统计数据 CSV。返回 (filename, content)。

    用户导出上限 1000 行（按注册时间倒序），避免无界批量导出。
    """
    if kind == "users":
        rows_out: list[dict] = []
        page = 1
        while page <= 10:  # 100/页 × 10 页 = 上限 1000 行
            data = users_page(
                db,
                start=start,
                end=end,
                q=None,
                status=None,
                registered_start=None,
                registered_end=None,
                sort="created_at",
                page=page,
                page_size=100,
            )
            for u in data["items"]:
                rows_out.append(
                    {
                        "用户ID": u["id"],
                        "用户名": u["username"],
                        "昵称": u["nickname"],
                        "状态": u["status"],
                        "注册时间(UTC)": u["created_at"],
                        "最近登录(UTC)": u["last_login_at"] or "",
                        "窗口内使用次数": u["usage_count"],
                        "窗口内AI调用": u["ai_calls"],
                    }
                )
            if page * 100 >= data["total"]:
                break
            page += 1
        headers = ["用户ID", "用户名", "昵称", "状态", "注册时间(UTC)", "最近登录(UTC)", "窗口内使用次数", "窗口内AI调用"]
        return (
            f"aurel-users-{start_iso}_{end_iso}.csv",
            _csv_response(rows_out, headers),
        )
    if kind == "ai":
        data = ai_stats(db, start=start, end=end, start_iso=start_iso, end_iso=end_iso, limit=0)
        rows = [
            {
                "AI服务": s["service"],
                "归属模块": s["module_label"],
                "请求数": s["total"],
                "成功": s["success"],
                "失败": s["failed"],
                "成功率": s["success_rate"] if s["success_rate"] is not None else "",
                "平均耗时(ms)": s["avg_latency_ms"] or "",
                "P95耗时(ms)": s["p95_ms"] or "",
                "Token总量": s["tokens_total"] if s["tokens_total"] is not None else "",
            }
            for s in data["by_service"]
        ]
        return (
            f"aurel-ai-{start_iso}_{end_iso}.csv",
            _csv_response(
                rows,
                ["AI服务", "归属模块", "请求数", "成功", "失败", "成功率", "平均耗时(ms)", "P95耗时(ms)", "Token总量"],
            ),
        )
    if kind == "overview":
        data = overview(db, start=start, end=end, start_iso=start_iso, end_iso=end_iso)
        rows = [
            {"指标": "累计注册用户", "数值": data["users"]["total"]},
            {"指标": "窗口内新增用户", "数值": data["users"]["new_in_range"]},
            {"指标": "窗口内活跃用户", "数值": data["users"]["active_in_range"]},
            {"指标": "DAU", "数值": data["users"]["dau"]},
            {"指标": "WAU", "数值": data["users"]["wau"]},
            {"指标": "MAU", "数值": data["users"]["mau"]},
            {"指标": "窗口内页面访问", "数值": data["pages"]["views_in_range"]},
            {"指标": "窗口内AI请求", "数值": data["ai"]["total"]},
            {"指标": "AI成功率", "数值": data["ai"]["success_rate"] if data["ai"]["success_rate"] is not None else ""},
            {"指标": "AI平均耗时(ms)", "数值": data["ai"]["avg_latency_ms"] or ""},
        ]
        return (
            f"aurel-overview-{start_iso}_{end_iso}.csv",
            _csv_response(rows, ["指标", "数值"]),
        )
    raise RangeError("导出类型仅支持 overview / users / ai")
