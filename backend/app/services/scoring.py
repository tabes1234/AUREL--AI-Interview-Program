"""T1 可解释评分引擎：分项评分 + 回答原文证据 + 评分理由 + 改进建议。

总分由后端根据维度分计算平均值，不直接采信模型给出的算术结果。
"""

from pydantic import BaseModel, Field, ValidationError

from app.services.ark_client import ArkClient, ArkError

DIMENSIONS = ["内容深度", "表达清晰", "逻辑结构", "岗位匹配"]


class ScoreDimension(BaseModel):
    name: str
    score: float = Field(ge=0, le=10)
    evidence: str = Field(min_length=1)
    rationale: str = Field(min_length=1)


class ImprovementItem(BaseModel):
    title: str = Field(min_length=1)
    detail: str = Field(min_length=1)


class ScoringResult(BaseModel):
    summary: str = Field(min_length=1)
    dimensions: list[ScoreDimension] = Field(min_length=1)
    strengths: list[str] = Field(min_length=1)
    improvements: list[ImprovementItem] = Field(min_length=1)
    overall_score: float = Field(ge=0, le=10)


def build_qa_lines(qa_pairs: list[dict]) -> str:
    lines = []
    for index, pair in enumerate(qa_pairs, start=1):
        lines.append(f"问题 {index}：{pair['question']}")
        lines.append(f"回答 {index}：{pair['answer']}")
        if pair.get("follow_up"):
            lines.append(f"追问：{pair['follow_up']}")
            lines.append(f"追问回答：{pair['follow_up_answer']}")
    return "\n".join(lines)


def score_interview(
    client: ArkClient,
    *,
    position: str,
    difficulty: str,
    language: str,
    qa_pairs: list[dict],
    occupation_context: str | None = None,
) -> ScoringResult:
    system = (
        "你是一位严格、可解释的面试评估专家。你的评分必须完全基于候选人回答的原文："
        "每个维度都要给出 evidence（候选人回答中的原文片段）和 rationale（为什么是这个分数）。"
        "禁止编造候选人没有说过的内容。评分客观克制，不刻意拔高。"
    )
    occupation_part = (
        f"职业背景（评定「岗位匹配」维度时结合以下信息判断）：{occupation_context}\n"
        if occupation_context
        else ""
    )
    user = (
        f"目标岗位：{position}\n"
        f"{occupation_part}"
        f"难度：{difficulty}\n"
        f"面试语言：{'中文' if language == 'zh' else 'English'}\n\n"
        f"面试记录：\n{build_qa_lines(qa_pairs)}\n\n"
        f"请按以下固定维度评分（0-10 分，支持一位小数）：{('、'.join(DIMENSIONS))}\n"
        "输出 JSON：\n"
        "{\n"
        '  "summary": "整体评价（2-4 句）",\n'
        '  "dimensions": [{"name": "维度名", "score": 7.5, '
        '"evidence": "回答原文片段", "rationale": "评分理由"}],\n'
        '  "strengths": ["亮点1", "亮点2"],\n'
        '  "improvements": [{"title": "改进方向", "detail": "具体可执行的建议"}]\n'
        "}\n"
        "要求：dimensions 必须包含全部四个维度；strengths 与 improvements 各 2-4 条。"
    )

    data = client.chat_json(system, user, service="scoring")

    try:
        dimensions_raw = data["dimensions"]
        strengths_raw = data["strengths"]
        improvements_raw = data["improvements"]
        summary = str(data["summary"]).strip()
    except KeyError as exc:
        raise ArkError(f"AI 评分结果缺少字段：{exc.args[0]}") from exc

    if not isinstance(dimensions_raw, list) or not isinstance(strengths_raw, list) \
            or not isinstance(improvements_raw, list) or not summary:
        raise ArkError("AI 评分结果结构无效")

    try:
        dimensions = [ScoreDimension(**item) for item in dimensions_raw]
        improvements = [ImprovementItem(**item) for item in improvements_raw]
    except (ValidationError, TypeError) as exc:
        raise ArkError(f"AI 评分结果字段无效：{_brief(str(exc))}") from exc

    strengths = [str(s).strip() for s in strengths_raw if str(s).strip()]
    if not strengths or not improvements:
        raise ArkError("AI 评分结果的亮点或改进建议为空")

    missing = [name for name in DIMENSIONS if name not in {d.name for d in dimensions}]
    if missing:
        raise ArkError(f"AI 评分缺少维度：{'、'.join(missing)}")

    # T1 可解释原则：总分 = 维度平均，由后端计算
    overall = round(sum(d.score for d in dimensions) / len(dimensions), 1)

    return ScoringResult(
        summary=summary,
        dimensions=dimensions,
        strengths=strengths,
        improvements=improvements,
        overall_score=overall,
    )


def _brief(text: str, limit: int = 160) -> str:
    compact = " ".join(text.split())
    return compact[:limit] + ("…" if len(compact) > limit else "")
