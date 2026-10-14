"""知途能力图谱：可追溯的技能/经历/方向/岗位/证据节点与真实关系（第十五阶段）。

核心原则：
- 关系不由模型随意生成：每条边都来自真实事件（完成问澜面试、知岗解析、
  简历经历、档案事实确认）或用户手动建立，且带来源；
- 节点四态严格区分：verified（已证实）/ user_stated（用户自述）/
  ai_inferred（AI 推断，必须带 confidence）/ pending（尚待验证）；
- AI 只能以 ai_inferred 状态「提议」节点，且必须给出材料中的依据片段，
  由用户确认后才升级为 user_stated；
- 新增项目/实习经历或完成一场问澜面试后，相关能力记录自动更新。
"""

import logging
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    CareerProfileFact,
    CareerSkillEdge,
    CareerSkillNode,
    InterviewReport,
    InterviewTask,
    JobAnalysis,
    utcnow,
)

logger = logging.getLogger("aurel.career")

ENTITY_TYPES = {
    "skill",
    "required_skill",
    "experience",
    "direction",
    "target_position",
    "evidence",
    "improvement_task",
}
NODE_STATUSES = {"verified", "user_stated", "ai_inferred", "pending"}
EDGE_RELATIONS = {"proves", "requires", "targets", "practice_for", "improves", "related_to"}
VERIFIED_DIMENSION_SCORE = 75  # 观己维度分达到该值，视为「已证实」
MAX_NODES = 400


def _normalize(name: str) -> str:
    return re.sub(r"\s+", "", name or "").lower()


def find_node(db: Session, user_id: int, entity_type: str, name: str) -> CareerSkillNode | None:
    normalized = _normalize(name)
    if not normalized:
        return None
    for node in db.scalars(
        select(CareerSkillNode).where(
            CareerSkillNode.user_id == user_id, CareerSkillNode.entity_type == entity_type
        )
    ):
        if _normalize(node.name) == normalized:
            return node
    return None


def _ensure_node(
    db: Session,
    *,
    user_id: int,
    entity_type: str,
    name: str,
    status: str,
    source_kind: str,
    source_ref: dict,
    quote: str | None = None,
    confidence: str | None = None,
    note: str | None = None,
) -> tuple[CareerSkillNode, bool]:
    """幂等创建节点：已存在则不降级状态（verified > user_stated > ai_inferred/pending）。"""
    existing = find_node(db, user_id, entity_type, name)
    name = name.strip()[:120]
    if existing is not None:
        return existing, False
    node = CareerSkillNode(
        user_id=user_id,
        entity_type=entity_type if entity_type in ENTITY_TYPES else "skill",
        name=name,
        status=status if status in NODE_STATUSES else "pending",
        confidence=confidence,
        source_kind=source_kind[:30],
        source_ref=source_ref or {},
        quote=quote,
        note=note,
    )
    db.add(node)
    db.flush()
    return node, True


def _ensure_edge(
    db: Session,
    *,
    user_id: int,
    from_node: CareerSkillNode,
    to_node: CareerSkillNode,
    relation: str,
    origin: str = "auto",
    source_kind: str = "",
) -> None:
    if from_node.id == to_node.id:
        return
    existing = db.scalar(
        select(CareerSkillEdge).where(
            CareerSkillEdge.user_id == user_id,
            CareerSkillEdge.from_node_id == from_node.id,
            CareerSkillEdge.to_node_id == to_node.id,
            CareerSkillEdge.relation == relation,
        )
    )
    if existing is not None:
        return
    db.add(
        CareerSkillEdge(
            user_id=user_id,
            from_node_id=from_node.id,
            to_node_id=to_node.id,
            relation=relation if relation in EDGE_RELATIONS else "related_to",
            origin=origin,
            source_kind=source_kind[:30],
        )
    )


# ---------- 更新触发：真实事件 → 图谱 ----------


def update_after_interview(db: Session, user_id: int, report: InterviewReport) -> dict:
    """完成一场问澜面试（报告生成）后调用：
    - 每个评分维度成为/更新技能节点：维度均分 ≥ 75 → verified，否则 pending；
    - 报告本身成为 evidence 节点（引用报告摘要），边 evidence --proves--> 技能；
    - 薄弱维度生成 improvement_task 节点，边技能 --practice_for--> 提升任务。
    幂等：同一报告重复触发不会产生重复节点/边。
    """
    task = db.get(InterviewTask, report.task_id)
    position = task.position if task else "未知岗位"
    created = 0
    source_ref = {
        "report_id": report.id,
        "task_id": report.task_id,
        "position": position,
        "overall_score": report.overall_score,
    }
    evidence, evidence_new = _ensure_node(
        db,
        user_id=user_id,
        entity_type="evidence",
        name=f"问澜报告#{report.id}（{position}）",
        status="verified",
        source_kind="interview_report",
        source_ref=source_ref,
        quote=(report.summary or "")[:200],
    )
    created += int(evidence_new)

    dim_scores: dict[str, float] = {}
    for dim in report.dimensions or []:
        name = str(dim.get("name") or "").strip()
        score = dim.get("score")
        if not name or score is None:
            continue
        dim_scores[name] = float(score)

    for name, score in dim_scores.items():
        node, is_new = _ensure_node(
            db,
            user_id=user_id,
            entity_type="skill",
            name=name,
            status="verified" if score >= VERIFIED_DIMENSION_SCORE else "pending",
            source_kind="interview_report",
            source_ref=source_ref,
            quote=f"「{name}」在 {position} 面试中得分 {score}",
        )
        created += int(is_new)
        if score < VERIFIED_DIMENSION_SCORE and node.status == "verified":
            node.status = "pending"  # 有新证据显示未达标，降回待验证
        _ensure_edge(
            db, user_id=user_id, from_node=evidence, to_node=node,
            relation="proves", source_kind="interview_report",
        )
        if score < VERIFIED_DIMENSION_SCORE:
            improvement, is_new = _ensure_node(
                db,
                user_id=user_id,
                entity_type="improvement_task",
                name=f"提升「{name}」（基于问澜报告#{report.id}）",
                status="pending",
                source_kind="interview_report",
                source_ref=source_ref,
                quote=f"「{name}」得分 {score}，低于 {VERIFIED_DIMENSION_SCORE} 验证线",
            )
            created += int(is_new)
            _ensure_edge(
                db, user_id=user_id, from_node=node, to_node=improvement,
                relation="practice_for", source_kind="interview_report",
            )
    db.commit()
    return {"created_nodes": created}


def update_after_resume(db: Session, user_id: int, resume) -> dict:
    """简历保存/解析后调用：经历板块 → experience 节点（user_stated）；
    技能清单 → skill 节点（user_stated）；边 experience --proves--> skill（用户自述证据）。
    只使用简历中用户自己填写的内容，不做任何虚构。
    """
    created = 0
    content = resume.content if isinstance(resume.content, dict) else {}
    source_ref = {"resume_id": resume.id, "resume_title": resume.title}

    for index, section in enumerate(("projects", "experiences", "internships", "works")):
        items = content.get(section)
        if not isinstance(items, list):
            continue
        for item_index, item in enumerate(items[:10]):
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or item.get("name") or item.get("company") or "").strip()
            if not title:
                continue
            node, is_new = _ensure_node(
                db,
                user_id=user_id,
                entity_type="experience",
                name=title[:120],
                status="user_stated",
                source_kind="resume",
                source_ref={**source_ref, "section": section, "index": item_index},
                quote=str(item.get("description") or item.get("summary") or "")[:200] or None,
            )
            created += int(is_new)

            skills = item.get("skills") or item.get("tags")
            if isinstance(skills, list):
                for skill_name in skills[:6]:
                    skill_text = str(skill_name).strip()
                    if not skill_text:
                        continue
                    skill_node, skill_new = _ensure_node(
                        db,
                        user_id=user_id,
                        entity_type="skill",
                        name=skill_text[:120],
                        status="user_stated",
                        source_kind="resume",
                        source_ref={**source_ref, "section": section},
                    )
                    created += int(skill_new)
                    _ensure_edge(
                        db, user_id=user_id, from_node=node, to_node=skill_node,
                        relation="proves", source_kind="resume",
                    )

    skills_block = content.get("skills")
    if isinstance(skills_block, list):
        for skill_name in skills_block[:20]:
            skill_text = str(skill_name).strip()
            if not skill_text:
                continue
            _, is_new = _ensure_node(
                db,
                user_id=user_id,
                entity_type="skill",
                name=skill_text[:120],
                status="user_stated",
                source_kind="resume",
                source_ref=source_ref,
            )
            created += int(is_new)
    db.commit()
    return {"created_nodes": created}


def update_after_job_analysis(db: Session, user_id: int, analysis: JobAnalysis) -> dict:
    """知岗解析完成后调用：目标岗位节点 + 岗位要求技能节点（pending）+ requires 边。
    岗位要求来自解析结论中的真实字段，不是模型在图谱里随意编造的关系。"""
    created = 0
    source_ref = {"job_analysis_id": analysis.id, "title": analysis.title}
    position, is_new = _ensure_node(
        db,
        user_id=user_id,
        entity_type="target_position",
        name=analysis.title[:120],
        status="user_stated",
        source_kind="job_analysis",
        source_ref=source_ref,
    )
    created += int(is_new)
    result = analysis.result or {}
    required = result.get("required_skills")
    if isinstance(required, list):
        for skill_name in required[:10]:
            skill_text = str(skill_name).strip()
            if not skill_text:
                continue
            skill_node, skill_new = _ensure_node(
                db,
                user_id=user_id,
                entity_type="required_skill",
                name=skill_text[:120],
                status="pending",
                source_kind="job_analysis",
                source_ref=source_ref,
                note="岗位要求技能：是否具备尚待本人材料验证",
            )
            created += int(skill_new)
            _ensure_edge(
                db, user_id=user_id, from_node=position, to_node=skill_node,
                relation="requires", source_kind="job_analysis",
            )
    db.commit()
    return {"created_nodes": created}


def sync_profile_skill_facts(db: Session, user_id: int) -> dict:
    """已确认档案中 category=skill / achievement 的事实 → user_stated 技能节点。幂等。"""
    created = 0
    facts = list(
        db.scalars(
            select(CareerProfileFact).where(
                CareerProfileFact.user_id == user_id,
                (CareerProfileFact.confirmed.is_(True))
                | (CareerProfileFact.source_type == "user_stated"),
            )
        )
    )
    for fact in facts:
        if fact.category not in {"skill", "achievement"}:
            continue
        _, is_new = _ensure_node(
            db,
            user_id=user_id,
            entity_type="skill",
            name=fact.content[:120],
            status="user_stated",
            source_kind="profile_fact",
            source_ref={"fact_id": fact.id},
            quote=fact.quote,
        )
        created += int(is_new)
    db.commit()
    return {"created_nodes": created}


GRAPH_SUGGEST_SYSTEM = """你是能力图谱整理员。根据用户已确认的档案事实与简历材料，提议值得记录的能力节点。
只输出 JSON：{"nodes": [{"entity_type": "skill", "name": "...", "confidence": "high|mid|low", "quote": "材料中的依据片段", "reason": "推断理由"}]}
规则：
- entity_type 只能是 skill 或 experience；
- quote 必须来自给定材料原文（连续片段），找不到依据就不要输出该节点；
- 只提议材料能支撑的节点，绝不编造用户没提过的公司、技能或成果；
- 最多 6 条。"""


def suggest_from_profile(db: Session, client, user_id: int) -> list[dict]:
    """AI 提议能力节点：全部以 ai_inferred + 待确认状态入库，绝不自动转正。
    依据片段必须能在材料中定位，定位不到的丢弃。"""
    from app.services.career_analyst import _profile_block, _resume_block
    from app.services.career_memory import _normalize as _norm

    materials = "\n\n".join(block for block in (_profile_block(db, user_id), _resume_block(db, user_id)) if block)
    if not materials.strip():
        return []
    data = client.chat_json(
        GRAPH_SUGGEST_SYSTEM, materials, temperature=0.2, service="career_graph_extract"
    )
    raw = data.get("nodes") if isinstance(data.get("nodes"), list) else []
    created = []
    normalized_materials = _norm(materials)
    for item in raw[:6]:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        quote = str(item.get("quote") or "").strip()
        if not name or not quote or _norm(quote) not in normalized_materials:
            continue  # 依据定位不到：直接丢弃，不入库
        confidence = str(item.get("confidence") or "mid").lower()
        if confidence not in {"high", "mid", "low"}:
            confidence = "mid"
        node, is_new = _ensure_node(
            db,
            user_id=user_id,
            entity_type="skill" if item.get("entity_type") != "experience" else "experience",
            name=name[:120],
            status="ai_inferred",
            source_kind="ai_suggest",
            source_ref={"service": "career_graph_extract", "prompt_version": "v1.0"},
            quote=quote[:300],
            confidence=confidence,
            note=str(item.get("reason") or "")[:300] or None,
        )
        created.append(node)
    db.commit()
    return created


# ---------- 查询与用户修正 ----------


def get_graph(db: Session, user_id: int) -> dict:
    nodes = list(
        db.scalars(
            select(CareerSkillNode)
            .where(CareerSkillNode.user_id == user_id)
            .order_by(CareerSkillNode.updated_at.desc(), CareerSkillNode.id.desc())
            .limit(MAX_NODES)
        )
    )
    edges = list(
        db.scalars(
            select(CareerSkillEdge)
            .where(CareerSkillEdge.user_id == user_id)
            .order_by(CareerSkillEdge.id.asc())
            .limit(MAX_NODES * 3)
        )
    )
    node_ids = {node.id for node in nodes}
    by_id = {node.id: node for node in nodes}
    node_payload = [
        {
            "id": node.id,
            "entity_type": node.entity_type,
            "name": node.name,
            "status": node.status,
            "confidence": node.confidence,
            "source_kind": node.source_kind,
            "source_ref": node.source_ref or {},
            "quote": node.quote,
            "note": node.note,
            "updated_at": node.updated_at.isoformat(),
        }
        for node in nodes
    ]
    edge_payload = [
        {
            "id": edge.id,
            "from_node_id": edge.from_node_id,
            "to_node_id": edge.to_node_id,
            "from_name": by_id[edge.from_node_id].name if edge.from_node_id in by_id else "",
            "to_name": by_id[edge.to_node_id].name if edge.to_node_id in by_id else "",
            "relation": edge.relation,
            "origin": edge.origin,
            "source_kind": edge.source_kind,
        }
        for edge in edges
        if edge.from_node_id in node_ids and edge.to_node_id in node_ids
    ]
    counts: dict[str, int] = {}
    for node in nodes:
        counts[node.status] = counts.get(node.status, 0) + 1
    return {"nodes": node_payload, "edges": edge_payload, "status_counts": counts}


def update_node_status(db: Session, user_id: int, node_id: int, status: str, note: str | None) -> CareerSkillNode:
    """用户修正节点状态：确认 AI 推断 → user_stated；标记待验证 → pending。
    verified 状态只能由真实练习事件产生，用户不能手工把节点标为已证实。"""
    node = db.get(CareerSkillNode, node_id)
    if node is None or node.user_id != user_id:
        raise LookupError("节点不存在")
    if status not in NODE_STATUSES:
        raise ValueError("未知的状态")
    if status == "verified":
        raise ValueError("「已证实」状态只能来自真实练习结果（问澜报告等），不能手工标记")
    if node.status == "verified" and status in {"ai_inferred", "pending"}:
        raise ValueError("已证实的节点不能降级为推断或待验证；如有异议可添加备注")
    node.status = status
    node.confidence = node.confidence if status == "ai_inferred" else None
    if note is not None:
        node.note = note[:300]
    node.updated_at = utcnow()
    db.commit()
    db.refresh(node)
    return node


def delete_node(db: Session, user_id: int, node_id: int) -> None:
    node = db.get(CareerSkillNode, node_id)
    if node is None or node.user_id != user_id:
        raise LookupError("节点不存在")
    for edge in db.scalars(
        select(CareerSkillEdge).where(
            (CareerSkillEdge.from_node_id == node_id) | (CareerSkillEdge.to_node_id == node_id)
        )
    ):
        db.delete(edge)
    db.delete(node)
    db.commit()


def add_user_edge(
    db: Session, user_id: int, from_node_id: int, to_node_id: int, relation: str
) -> CareerSkillEdge:
    """用户手动建立关系（origin=user），仍然写入来源便于追溯。"""
    from_node = db.get(CareerSkillNode, from_node_id)
    to_node = db.get(CareerSkillNode, to_node_id)
    if from_node is None or from_node.user_id != user_id or to_node is None or to_node.user_id != user_id:
        raise LookupError("节点不存在")
    if relation not in EDGE_RELATIONS:
        raise ValueError("未知的关系类型")
    _ensure_edge(db, user_id=user_id, from_node=from_node, to_node=to_node, relation=relation, origin="user", source_kind="user_manual")
    db.commit()
    edge = db.scalar(
        select(CareerSkillEdge).where(
            CareerSkillEdge.user_id == user_id,
            CareerSkillEdge.from_node_id == from_node_id,
            CareerSkillEdge.to_node_id == to_node_id,
            CareerSkillEdge.relation == relation,
        )
    )
    return edge
