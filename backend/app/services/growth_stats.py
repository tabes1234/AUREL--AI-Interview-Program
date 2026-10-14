"""成长轨迹统计：年度热力图 + 连续打卡（streak）。

数据来源（全部为真实用户行为，不做任何模拟补点）：
- interview_tasks.created_at（问澜训练）
- challenge_runs.created_at（度衡挑战）
- expression_analyses.created_at（听澜表达分析）
- mistake_cards.last_reviewed_at（回澜复习）
"""

from collections import defaultdict
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    ChallengeRun,
    ExpressionAnalysis,
    InterviewReport,
    InterviewTask,
    MistakeCard,
    utcnow,
)

_KIND_LABELS = {
    "interview": "问澜",
    "challenge": "度衡",
    "expression": "听澜",
    "mistake": "回澜",
}


def growth_heatmap(db: Session, user_id: int, year: int) -> dict:
    """返回指定年份的逐日活动与连续打卡统计。"""
    day_counts: dict[date, int] = defaultdict(int)
    day_kinds: dict[date, set[str]] = defaultdict(set)

    def _record(dt: datetime | None, kind: str) -> None:
        if dt is None or dt.year != year:
            return
        day = dt.date()
        day_counts[day] += 1
        day_kinds[day].add(kind)

    task_rows = db.execute(
        select(InterviewTask.created_at).where(
            InterviewTask.user_id == user_id, InterviewTask.status == "completed"
        )
    ).all()
    for (created_at,) in task_rows:
        _record(created_at, "interview")

    challenge_rows = db.execute(
        select(ChallengeRun.created_at).where(
            ChallengeRun.user_id == user_id, ChallengeRun.status == "completed"
        )
    ).all()
    for (created_at,) in challenge_rows:
        _record(created_at, "challenge")

    expression_rows = db.execute(
        select(ExpressionAnalysis.created_at).where(
            ExpressionAnalysis.user_id == user_id
        )
    ).all()
    for (created_at,) in expression_rows:
        _record(created_at, "expression")

    mistake_rows = db.execute(
        select(MistakeCard.last_reviewed_at).where(
            MistakeCard.user_id == user_id, MistakeCard.review_count > 0
        )
    ).all()
    for (reviewed_at,) in mistake_rows:
        _record(reviewed_at, "mistake")

    days = sorted(
        (
            {"date": day.isoformat(), "count": day_counts[day], "kinds": sorted(day_kinds[day])}
            for day in set(day_counts) | set(day_kinds)
        ),
        key=lambda item: item["date"],
    )

    active = {date.fromisoformat(item["date"]) for item in days}
    current, longest = _streaks(active, year)

    return {"year": year, "days": days, "streak": {"current": current, "longest": longest}}


def _streaks(active: set[date], year: int) -> tuple[int, int]:
    """当前连续天数（截至今天/年末，取小者）与该年最长连续天数。"""
    longest = 0
    run = 0
    cursor = date(year, 1, 1)
    end = date(year, 12, 31)
    while cursor <= end:
        if cursor in active:
            run += 1
            longest = max(longest, run)
        else:
            run = 0
        cursor += timedelta(days=1)

    today = utcnow().date()
    current = 0
    cursor = min(today, end)
    while cursor >= date(year, 1, 1) and cursor in active:
        current += 1
        cursor -= timedelta(days=1)
    return current, longest


# ---------- 澜记周报：近 7 日真实活动聚合（ai_note 由路由层按需填充） ----------


def weekly_report(db: Session, user_id: int) -> dict:
    """聚合最近 7 天（含今日）的真实行为：逐日活动、分类合计、周内面试均分。"""
    today = utcnow().date()
    start = today - timedelta(days=6)
    start_dt = datetime(start.year, start.month, start.day)

    day_counts: dict[date, int] = defaultdict(int)
    day_kinds: dict[date, set[str]] = defaultdict(set)
    totals: dict[str, int] = defaultdict(int)

    def _record(dt: datetime | None, kind: str) -> None:
        if dt is None:
            return
        day = dt.date()
        if not (start <= day <= today):
            return
        day_counts[day] += 1
        day_kinds[day].add(kind)
        totals[kind] += 1

    task_rows = db.execute(
        select(InterviewTask.created_at, InterviewReport.overall_score)
        .outerjoin(InterviewReport, InterviewReport.task_id == InterviewTask.id)
        .where(
            InterviewTask.user_id == user_id,
            InterviewTask.status == "completed",
            InterviewTask.created_at >= start_dt,
        )
    ).all()
    week_scores = []
    for created_at, overall_score in task_rows:
        _record(created_at, "interview")
        if overall_score is not None:
            week_scores.append(float(overall_score))

    for created_at, in db.execute(
        select(ChallengeRun.created_at).where(
            ChallengeRun.user_id == user_id,
            ChallengeRun.status == "completed",
            ChallengeRun.created_at >= start_dt,
        )
    ):
        _record(created_at, "challenge")

    for created_at, in db.execute(
        select(ExpressionAnalysis.created_at).where(
            ExpressionAnalysis.user_id == user_id,
            ExpressionAnalysis.created_at >= start_dt,
        )
    ):
        _record(created_at, "expression")

    for reviewed_at, in db.execute(
        select(MistakeCard.last_reviewed_at).where(
            MistakeCard.user_id == user_id,
            MistakeCard.review_count > 0,
            MistakeCard.last_reviewed_at >= start_dt,
        )
    ):
        _record(reviewed_at, "mistake")

    days = []
    for offset in range(7):
        day = start + timedelta(days=offset)
        days.append(
            {
                "date": day.isoformat(),
                "count": day_counts.get(day, 0),
                "kinds": sorted(day_kinds.get(day, set())),
            }
        )

    # 连续天数基于全年活动：复用热力图口径，避免 7 日窗口截断
    current_streak, _ = _streaks(_year_active_days(db, user_id, today.year), today.year)

    return {
        "week_start": start.isoformat(),
        "week_end": today.isoformat(),
        "days": days,
        "totals": dict(totals),
        "interviews_completed": totals.get("interview", 0),
        "average_score": (
            round(sum(week_scores) / len(week_scores), 1) if week_scores else None
        ),
        "active_days": len(day_counts),
        "streak_current": current_streak,
        "ai_note": None,
    }


def _year_active_days(db: Session, user_id: int, year: int) -> set[date]:
    """该年有真实活动的日期集合（与 growth_heatmap 同口径）。"""
    heatmap = growth_heatmap(db, user_id, year)
    return {date.fromisoformat(item["date"]) for item in heatmap["days"] if item["count"] > 0}
