"""知途：多职业路径比较（第十五阶段）。

- 至少比较两个职业方向；每个方向分析：用户已有经历的关联度、目标岗位技能要求
  （优先引用知潮真实岗位与知岗解析，带来源）、需要补充的证据与实践、用户主动
  说明的兴趣与限制、可能的学习/切换成本、下一步验证行动；
- 结果强制分为四类：用户已提供的事实 / 有来源的岗位要求 / AI 推断的可能性 /
  建议进一步确认的问题；
- 绝不编造薪酬、就业概率或职业前景数字；没有可靠数据时如实说明；
- 比较结果可保存、可查看、可删除（按用户隔离）。
"""

import json
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CareerPathComparison, JobPosition, utcnow
from app.services.ark_client import ArkError
from app.services.career_analyst import _profile_block, _resume_block, _skill_profile_block
from app.services.career_retrieval import evidence_block

logger = logging.getLogger("aurel.career")

PATH_COMPARE_SYSTEM = """你是职业路径比较分析员。对用户给出的两个及以上职业方向做对比分析。
只输出 JSON：{"directions": [{"name": "方向名",
  "relevance": "与用户已有经历的关联度说明（引用材料）",
  "skill_requirements": [{"requirement": "技能要求", "source": "来源说明（来自材料中的哪个岗位或解析）"}],
  "evidence_gaps": ["需要补充的证据与实践"],
  "interests_constraints": ["用户主动说明的兴趣与限制（没有则留空数组）"],
  "learning_cost": "学习与切换成本说明（只基于材料，不编造数据）",
  "verification_actions": ["下一步用于验证方向的实际行动"]
}],
"comparison": {"common": ["各方向共同要求"], "diverge": ["关键差异"], "recommendation": "基于材料的探索顺序建议（不是结论）"},
"note": "提醒"}
硬性规则：
- skill_requirements 的 source 必须指向材料中真实出现的岗位（知潮岗位/知岗解析）；材料中没有的岗位要求标记来源为「通用经验，待核实」；
- interests_constraints 只能来自用户材料原文，不得替用户编造兴趣；
- 绝不输出薪酬数字、就业概率、录用概率或行业前景预测；没有可靠数据就明确说「材料中没有可靠数据」；
- 结论区分事实与推断；推断写明「AI 推断」；
- 每个方向 skill_requirements 2-4 条、verification_actions 2-4 条。"""

DISCLAIMER = (
    "本比较基于现有材料与检索到的岗位资料，仅用于探索参考，不构成对任何方向就业结果、"
    "录用概率或薪酬水平的预测；请结合进一步验证后再做决定。"
)

MAX_DIRECTIONS = 4


def _job_library_block(db: Session, directions: list[str]) -> tuple[str, list[dict]]:
    """从知潮真实岗位库中检索与方向相关的岗位要求（全局资料，带来源）。"""
    lines: list[str] = []
    sources: list[dict] = []
    seen_positions: set[int] = set()
    for direction in directions[:MAX_DIRECTIONS]:
        try:
            outcome = _search_positions(db, direction)
        except Exception:  # noqa: BLE001
            logger.warning("job library search failed", exc_info=True)
            continue
        for item in outcome:
            position_id = item["position_id"]
            if position_id in seen_positions:
                continue
            seen_positions.add(position_id)
            lines.append(
                f"- 岗位《{item['title']}》（{item['company']}）：必需技能摘要：{item['required'][:150]}；"
                f"经验要求：{item['experience'][:80] or '未明确说明'}"
            )
            sources.append(
                {
                    "position_id": position_id,
                    "title": item["title"],
                    "company": item["company"],
                    "source_url": item["source_url"],
                    "hiring_status": item["hiring_status"],
                }
            )
            if len(sources) >= 8:
                break
        if len(sources) >= 8:
            break
    if not lines:
        return "【知潮岗位库】未检索到相关真实岗位", []
    return "【知潮岗位库 · 真实岗位要求（有来源）】\n" + "\n".join(lines), sources


def _search_positions(db: Session, direction: str) -> list[dict]:
    from app.services.retrieval import BM25Index

    positions = list(db.scalars(select(JobPosition).limit(300)))
    if not positions:
        return []
    docs = {
        position.id: f"{position.title} {position.company} "
        f"{position.required_skills_summary} {position.responsibilities_summary}"
        for position in positions
    }
    hits = BM25Index(docs).search(direction, top_k=3)
    by_id = {position.id: position for position in positions}
    results = []
    for hit in hits:
        position = by_id[hit.key]
        results.append(
            {
                "position_id": position.id,
                "title": position.title,
                "company": position.company,
                "required": position.required_skills_summary or "",
                "experience": position.experience_summary or "",
                "source_url": position.source_url,
                "hiring_status": position.hiring_status,
            }
        )
    return results


def compare_paths(
    db: Session,
    client,
    user_id: int,
    *,
    directions: list[str],
    note: str = "",
) -> CareerPathComparison:
    """真实执行多路径比较并保存。AI 调用失败时抛出 ArkError，不伪造结果。"""
    clean_directions: list[str] = []
    for direction in directions:
        text = str(direction or "").strip()[:60]
        if text and text not in clean_directions:
            clean_directions.append(text)
    if len(clean_directions) < 2:
        raise ValueError("至少需要两个职业方向才能比较")

    # 联动知藏 RAG：为每个方向检索知识证据（含来源，可追溯）
    knowledge_lines: list[str] = []
    knowledge_sources: list[dict] = []
    for direction in clean_directions:
        block, sources = evidence_block(db, user_id, f"{direction} 岗位要求 能力", top_k=2)
        if block:
            knowledge_lines.append(f"◆ 方向「{direction}」\n{block}")
            for source in sources:
                source = {**source, "for_direction": direction}
                if source not in knowledge_sources:
                    knowledge_sources.append(source)

    library_block, library_sources = _job_library_block(db, clean_directions)

    user_payload = "\n\n".join(
        block
        for block in (
            _profile_block(db, user_id),
            _resume_block(db, user_id),
            _skill_profile_block(db, user_id),
            f"【用户指定的比较方向】{'、'.join(clean_directions)}",
            f"【用户补充说明】{note[:300]}" if note else "",
            library_block,
            "\n\n".join(knowledge_lines) if knowledge_lines else "",
        )
        if block
    )
    data = client.chat_json(
        PATH_COMPARE_SYSTEM, user_payload, temperature=0.3, service="career_path_compare"
    )

    raw_directions = data.get("directions") if isinstance(data.get("directions"), list) else []
    parsed_directions: list[dict] = []
    for item in raw_directions[:MAX_DIRECTIONS]:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()[:60]
        if not name:
            continue
        requirements = []
        for req in item.get("skill_requirements", [])[:4] if isinstance(item.get("skill_requirements"), list) else []:
            if not isinstance(req, dict):
                continue
            requirement = str(req.get("requirement") or "").strip()[:150]
            if not requirement:
                continue
            requirements.append(
                {
                    "requirement": requirement,
                    "source": str(req.get("source") or "通用经验，待核实").strip()[:120],
                }
            )
        parsed_directions.append(
            {
                "name": name,
                "relevance": str(item.get("relevance") or "").strip()[:600],
                "skill_requirements": requirements,
                "evidence_gaps": _string_list(item.get("evidence_gaps"), 5),
                "interests_constraints": _string_list(item.get("interests_constraints"), 5),
                "learning_cost": str(item.get("learning_cost") or "").strip()[:400],
                "verification_actions": _string_list(item.get("verification_actions"), 5),
                "source": "ai_analysis",
            }
        )
    if len(parsed_directions) < 2:
        raise ValueError("AI 未能生成有效的多方向比较，请稍后重试或补充更多信息")

    raw_comparison = data.get("comparison") if isinstance(data.get("comparison"), dict) else {}
    comparison = {
        "common": _string_list(raw_comparison.get("common"), 6),
        "diverge": _string_list(raw_comparison.get("diverge"), 6),
        "recommendation": str(raw_comparison.get("recommendation") or "").strip()[:600],
    }

    record = CareerPathComparison(
        user_id=user_id,
        title=" vs ".join(clean_directions[:2]) + (" 等" if len(clean_directions) > 2 else ""),
        note=note[:500],
        directions=parsed_directions,
        comparison=comparison,
        data_basis={
            "generated_at": utcnow().isoformat(),
            "knowledge_sources": knowledge_sources[:12],
            "job_sources": library_sources[:8],
            "disclaimer": DISCLAIMER,
        },
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def list_comparisons(db: Session, user_id: int, limit: int = 30) -> list[CareerPathComparison]:
    return list(
        db.scalars(
            select(CareerPathComparison)
            .where(CareerPathComparison.user_id == user_id)
            .order_by(CareerPathComparison.created_at.desc(), CareerPathComparison.id.desc())
            .limit(limit)
        )
    )


def get_comparison(db: Session, user_id: int, comparison_id: int) -> CareerPathComparison | None:
    record = db.get(CareerPathComparison, comparison_id)
    if record is None or record.user_id != user_id:
        return None
    return record


def serialize(record: CareerPathComparison) -> dict:
    return {
        "id": record.id,
        "title": record.title,
        "note": record.note,
        "directions": record.directions,
        "comparison": record.comparison,
        "data_basis": record.data_basis,
        "created_at": record.created_at.isoformat(),
    }


def _string_list(value: object, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    items = []
    for item in value[:limit]:
        text = str(item).strip()
        if text:
            items.append(text[:200])
    return items


def safe_json(record: dict) -> str:
    return json.dumps(record, ensure_ascii=False)
