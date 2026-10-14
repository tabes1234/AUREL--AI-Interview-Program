"""T3：技能画像 / 技能图谱 / 自适应训练建议。

全部由真实历史面试报告（T1 评分）聚合驱动：
- 四大维度平均分构成画像节点
- 按时间序列的分数走势构成图谱边
- 最薄弱维度驱动训练建议（难度与侧重），建议理由引用真实报告数据
"""

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import InterviewReport, InterviewTask

DIMENSION_ORDER = ["内容深度", "表达清晰", "逻辑结构", "岗位匹配"]

DIFFICULTY_ORDER = {"basic": 0, "intermediate": 1, "advanced": 2}
ORDER_DIFFICULTY = ["basic", "intermediate", "advanced"]

# 维度 -> 练习侧重提示（自适应训练的"侧重"依据）
FOCUS_HINTS = {
    "内容深度": "练习时先给结论，再展开两层依据，每个观点配一个真实案例",
    "表达清晰": "练习时分点作答，控制每点不超过三句话，先骨架后细节",
    "逻辑结构": "练习时使用「背景—行动—结果」或「总—分—总」的框架作答",
    "岗位匹配": "练习时主动把经历与岗位要求对应，说明技能如何迁移到该岗位",
}

RECOMMEND_REASONS = {
    "内容深度": "历史回答在内容深度上得分最低——回答多停留在表面陈述",
    "表达清晰": "历史回答在表达清晰上得分最低——要点组织与语言精炼度不足",
    "逻辑结构": "历史回答在逻辑结构上得分最低——论述缺少清晰框架",
    "岗位匹配": "历史回答在岗位匹配上得分最低——经历与岗位要求的关联不够紧密",
}


@dataclass
class SkillProfile:
    has_data: bool = False
    completed_interviews: int = 0
    average_score: float | None = None
    latest_score: float | None = None
    dimension_averages: dict[str, float] = field(default_factory=dict)
    dimension_trend: dict[str, list[float]] = field(default_factory=dict)
    score_history: list[dict] = field(default_factory=list)  # [{date, score, position}]
    strongest: str | None = None
    weakest: str | None = None
    positions_practiced: list[str] = field(default_factory=list)


def build_skill_profile(db: Session, limit: int = 50, *, user_id: int) -> SkillProfile:
    statement = (
        select(InterviewReport, InterviewTask)
        .join(InterviewTask, InterviewReport.task_id == InterviewTask.id)
        .where(InterviewTask.user_id == user_id)
        .order_by(InterviewReport.created_at.asc(), InterviewReport.id.asc())
        .limit(limit * 2)
    )
    rows = list(db.execute(statement).all())
    profile = SkillProfile()
    if not rows:
        return profile

    reports = [(report, task) for report, task in rows]
    # 最多取最近 limit 场
    reports = reports[-limit:]

    profile.has_data = True
    profile.completed_interviews = len(reports)
    profile.positions_practiced = list(dict.fromkeys(task.position for _, task in reports))

    all_scores = [report.overall_score for report, _ in reports]
    profile.average_score = round(sum(all_scores) / len(all_scores), 1)
    profile.latest_score = all_scores[-1]

    dim_sums: dict[str, float] = {}
    dim_counts: dict[str, int] = {}
    for report, _ in reports:
        for dim in report.dimensions:
            name = dim.get("name", "")
            score = dim.get("score")
            if not name or score is None:
                continue
            dim_sums[name] = dim_sums.get(name, 0.0) + float(score)
            dim_counts[name] = dim_counts.get(name, 0) + 1
            profile.dimension_trend.setdefault(name, []).append(float(score))
    profile.dimension_averages = {
        name: round(dim_sums[name] / dim_counts[name], 1)
        for name in dim_sums
        if dim_counts[name] > 0
    }

    profile.score_history = [
        {
            "date": report.created_at.isoformat(),
            "position": task.position,
            "score": report.overall_score,
        }
        for report, task in reports
    ]

    if profile.dimension_averages:
        ranked = sorted(profile.dimension_averages.items(), key=lambda kv: kv[1])
        profile.weakest = ranked[0][0]
        profile.strongest = ranked[-1][0]
    return profile


def _normalize_trend(trend: list[float], window: int = 3) -> float:
    """近期均值 - 早期均值：正数上升，负数下滑。"""
    if len(trend) < 2:
        return 0.0
    window = min(window, max(1, len(trend) // 2))
    recent = trend[-window:]
    early = trend[:window]
    return sum(recent) / len(recent) - sum(early) / len(early)


def build_training_recommendation(profile: SkillProfile) -> dict:
    """自适应训练建议：薄弱维度决定侧重与难度，理由引用真实历史。"""
    if not profile.has_data:
        return {
            "available": False,
            "message": "完成第一场面试后，这里会基于真实评分给出个性化训练建议",
        }

    weakest = profile.weakest or "内容深度"
    avg_by_dim = profile.dimension_averages
    weakest_score = avg_by_dim.get(weakest, 0.0)

    # 难度调整：综合表现好则升难度，弱则保持/降难度
    if profile.average_score is not None and profile.average_score >= 80:
        suggested_difficulty = "advanced"
        difficulty_reason = f"近期综合均分 {profile.average_score} 已达优秀线，建议挑战高压追问"
    elif profile.average_score is not None and profile.average_score >= 65:
        current = "intermediate"
        suggested_difficulty = current
        difficulty_reason = f"综合均分 {profile.average_score} 处于进阶区间，保持当前难度稳固提升"
    else:
        suggested_difficulty = "basic"
        difficulty_reason = f"综合均分 {profile.average_score} 偏低，先以基础题建立信心与框架"

    # 上升势头明显的维度在建议中说明，鼓励保持
    rising = [
        name
        for name, trend in profile.dimension_trend.items()
        if _normalize_trend(trend) > 1.0
    ]

    reasons = [RECOMMEND_REASONS.get(weakest, f"「{weakest}」是当前最薄弱维度")]
    reasons.append(difficulty_reason)
    if rising:
        reasons.append("「" + "」「".join(rising) + "」呈上升趋势，保持当前练习节奏")

    return {
        "available": True,
        "weakest_dimension": weakest,
        "weakest_score": weakest_score,
        "strongest_dimension": profile.strongest,
        "suggested_difficulty": suggested_difficulty,
        "focus_hint": FOCUS_HINTS.get(weakest, ""),
        "reasons": reasons,
        "based_on": {
            "completed_interviews": profile.completed_interviews,
            "average_score": profile.average_score,
            "latest_score": profile.latest_score,
        },
    }


def build_skill_graph(profile: SkillProfile) -> dict:
    """技能图谱：维度节点（分数/趋势）+ 综合走势边数据，前端渲染。"""
    if not profile.has_data:
        return {"available": False}
    nodes = []
    for name in DIMENSION_ORDER:
        if name not in profile.dimension_averages:
            continue
        trend = profile.dimension_trend.get(name, [])
        nodes.append(
            {
                "name": name,
                "score": profile.dimension_averages[name],
                "trend_delta": round(_normalize_trend(trend), 1),
                "samples": len(trend),
                "is_weakest": name == profile.weakest,
                "is_strongest": name == profile.strongest,
            }
        )
    return {
        "available": True,
        "nodes": nodes,
        "score_history": profile.score_history,
        "average_score": profile.average_score,
        "latest_score": profile.latest_score,
        "positions_practiced": profile.positions_practiced,
    }
