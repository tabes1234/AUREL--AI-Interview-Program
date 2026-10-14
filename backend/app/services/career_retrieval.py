"""知途 RAG：职业知识库的分段、向量表示、混合检索与重排序（第十五阶段）。

数据来源与分段原则：
- 只对「真实资料」做合理分段：知潮真实岗位摘要（全局）、知岗解析结论（本人）、
  知藏上传文档分块（本人）、已确认档案事实（本人）。不把整份 JD 原文或聊天历史塞进索引。
- 每个分段带来源（source_kind + source_id + 可选 source_url）与元数据
  （行业/职业/经验水平/发布与核验时间），检索结果可回溯。

检索原则：
- 关键词检索：BM25（复用 retrieval.BM25Index）；
- 向量检索：本地确定性词面哈希向量（128 维）+ 余弦相似度——方舟 embedding 未开通，
  如实使用词面向量，不冒充语义向量；向量随分段保存，可复算；
- 混合检索：BM25 与向量两路用 RRF（Reciprocal Rank Fusion）融合；
- 重排序：按行业/职业/经验匹配、来源新近度与过期降权（>30 天未核验降权）等规则重排；
- 无可靠依据时明确返回 found=False，绝不编造。
"""

import hashlib
import json
import logging
import math
from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    CareerKnowledgeChunk,
    CareerProfileFact,
    JobAnalysis,
    JobPosition,
    KnowledgeChunk,
    utcnow,
)
from app.services.retrieval import BM25Index, tokenize

logger = logging.getLogger("aurel.career")

VECTOR_DIM = 128
STALE_AFTER_DAYS = 30  # 与知潮口径一致：超过 30 天未核验视为可能过期
CHUNK_MAX_CHARS = 420
RRF_K = 60
BM25_WEIGHT = 1.0
VECTOR_WEIGHT = 0.8

# 全局资料种子：岗位能力模型 / 就业指导参考（事实性、可公开的通用原则，非编造岗位数据）
GLOBAL_GUIDE_SEEDS: list[dict[str, str]] = [
    {
        "title": "面试表达通用方法：STAR 结构",
        "content": (
            "面试中描述项目与实习经历时，可采用 STAR 结构组织回答：S（Situation）交代背景，"
            "T（Task）说明自己的任务与目标，A（Action）重点讲自己采取的具体行动与取舍，"
            "R（Result）给出可核验的结果。结果部分没有数据支撑时，如实说明定性收获，"
            "不要编造百分比或金额。该方法来自通用就业指导资料的结构化表达原则。"
        ),
        "occupation_id": None,
        "industry_id": None,
        "experience_level": "不限",
    },
    {
        "title": "简历写作通用原则：证据优先",
        "content": (
            "简历中每段经历应尽量包含：做了什么、用了什么方法或工具、产生了什么可核验的结果。"
            "避免只写「负责」「参与」等空泛表述；没有数据时不编造数字。"
            "针对不同目标岗位调整重点顺序，把与岗位要求最相关的经历放在前面。"
            "以上为通用写作原则，具体以各高校就业指导中心的公开资料为准。"
        ),
        "occupation_id": None,
        "industry_id": None,
        "experience_level": "不限",
    },
    {
        "title": "职业探索通用建议：小成本验证",
        "content": (
            "在多个职业方向之间犹豫时，常用的验证方式包括：与从业者进行一次信息访谈、"
            "完成一个该方向的小型练习项目、参加一次该方向的限时模拟练习。"
            "这些行动的成本低于直接投递与转行，能帮助收集真实证据后再做决定。"
            "本条为通用方法论，不预测任何具体方向的就业结果。"
        ),
        "occupation_id": None,
        "industry_id": None,
        "experience_level": "不限",
    },
]


def _hash_vector(text: str) -> list[float]:
    """本地确定性词面哈希向量：token 哈希落桶后 L2 归一化（可保存、可复算）。"""
    vector = [0.0] * VECTOR_DIM
    for token in tokenize(text):
        digest = hashlib.md5(token.encode("utf-8")).digest()
        bucket = int.from_bytes(digest[:2], "big") % VECTOR_DIM
        sign = 1.0 if digest[2] % 2 == 0 else -1.0
        vector[bucket] += sign
    norm = math.sqrt(sum(value * value for value in vector))
    if norm > 0:
        vector = [round(value / norm, 5) for value in vector]
    return vector


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    return round(sum(a * b for a, b in zip(left, right)), 5)


def content_fingerprint(text: str) -> str:
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()


def _split_paragraphs(text: str) -> list[str]:
    paragraphs = [part.strip() for part in text.replace("\r\n", "\n").split("\n")]
    return [part for part in paragraphs if part]


def _make_chunk(
    *,
    scope: str,
    source_kind: str,
    source_id: str,
    title: str,
    content: str,
    industry_id: str | None = None,
    occupation_id: str | None = None,
    experience_level: str = "",
    published_at=None,
    last_verified_at=None,
    source_url: str | None = None,
    user_id: int | None = None,
) -> CareerKnowledgeChunk | None:
    content = content.strip()
    if not content:
        return None
    return CareerKnowledgeChunk(
        scope=scope,
        user_id=user_id,
        source_kind=source_kind,
        source_id=source_id,
        title=title[:200],
        industry_id=industry_id,
        occupation_id=occupation_id,
        experience_level=experience_level[:30],
        content=content[:CHUNK_MAX_CHARS],
        content_hash=content_fingerprint(content),
        vector=_hash_vector(title + "\n" + content),
        published_at=published_at,
        last_verified_at=last_verified_at,
        source_url=source_url,
    )


# ---------- 索引构建（只增不重复：以 content_hash + source 判重） ----------


def _existing_hashes(db: Session, scope: str) -> set[str]:
    return set(
        db.scalars(
            select(CareerKnowledgeChunk.content_hash).where(
                CareerKnowledgeChunk.scope == scope
            )
        )
    )


def sync_global_index(db: Session) -> dict:
    """全局索引：知潮真实岗位摘要 + 通用就业指导原则。幂等，可重复调用。"""
    existing = _existing_hashes(db, "global")
    added = 0
    for position in db.scalars(select(JobPosition)).all():
        pieces = [
            (f"{position.title}｜岗位职责摘要", position.responsibilities_summary),
            (f"{position.title}｜必需技能摘要", position.required_skills_summary),
            (f"{position.title}｜加分技能摘要", position.preferred_skills_summary),
            (f"{position.title}｜经验要求", position.experience_summary),
        ]
        for title, body in pieces:
            chunk = _make_chunk(
                scope="global",
                source_kind="job_position",
                source_id=str(position.id),
                title=title,
                content=body or "",
                industry_id=position.industry_id,
                occupation_id=position.occupation_id,
                experience_level=position.level or "不限",
                published_at=position.published_at,
                last_verified_at=position.last_verified_at,
                source_url=position.source_url,
            )
            if chunk is None or chunk.content_hash in existing:
                continue
            db.add(chunk)
            existing.add(chunk.content_hash)
            added += 1
    for seed in GLOBAL_GUIDE_SEEDS:
        chunk = _make_chunk(
            scope="global",
            source_kind="career_guide",
            source_id=content_fingerprint(seed["title"])[:16],
            title=seed["title"],
            content=seed["content"],
            industry_id=seed["industry_id"],
            occupation_id=seed["occupation_id"],
            experience_level=seed["experience_level"],
        )
        if chunk is None or chunk.content_hash in existing:
            continue
        db.add(chunk)
        existing.add(chunk.content_hash)
        added += 1
    db.commit()
    return {"added": added}


def sync_user_index(db: Session, user_id: int) -> dict:
    """本人索引：知岗解析结论、知藏文档分块、已确认档案事实。幂等。"""
    existing = set(
        db.scalars(
            select(CareerKnowledgeChunk.content_hash).where(
                CareerKnowledgeChunk.scope == "user",
                CareerKnowledgeChunk.user_id == user_id,
            )
        )
    )
    added = 0

    for analysis in db.scalars(
        select(JobAnalysis).where(
            JobAnalysis.user_id == user_id, JobAnalysis.status == "ready"
        )
    ).all():
        result = analysis.result or {}
        sections: list[str] = []
        for key, label in (
            ("responsibilities", "岗位职责"),
            ("required_skills", "必需技能"),
            ("preferred_skills", "加分技能"),
            ("experience_requirements", "经验要求"),
        ):
            value = result.get(key)
            if isinstance(value, list) and value:
                sections.append(label + "：" + "；".join(str(item) for item in value[:8]))
        content = "\n".join(sections)
        chunk = _make_chunk(
            scope="user",
            source_kind="job_analysis",
            source_id=str(analysis.id),
            title=f"知岗解析《{analysis.title}》结论",
            content=content,
            user_id=user_id,
        )
        if chunk is not None and chunk.content_hash not in existing:
            db.add(chunk)
            existing.add(chunk.content_hash)
            added += 1

    from app.models import KnowledgeDocument

    doc_chunks = list(
        db.execute(
            select(KnowledgeChunk)
            .join(KnowledgeDocument, KnowledgeChunk.document_id == KnowledgeDocument.id)
            .where(KnowledgeDocument.user_id == user_id)
            .limit(200)
        ).scalars()
    )
    for chunk_row in doc_chunks:
        document = db.get(KnowledgeDocument, chunk_row.document_id)
        if document is None:
            continue
        chunk = _make_chunk(
            scope="user",
            source_kind="knowledge_doc",
            source_id=str(chunk_row.id),
            title=f"知藏文档《{document.title}》片段",
            content=chunk_row.content,
            user_id=user_id,
        )
        if chunk is not None and chunk.content_hash not in existing:
            db.add(chunk)
            existing.add(chunk.content_hash)
            added += 1

    from app.services.career_memory import confirmed_facts

    for fact in confirmed_facts(db, user_id, limit=80):
        chunk = _make_chunk(
            scope="user",
            source_kind="user_profile",
            source_id=str(fact.id),
            title="已确认档案事实",
            content=fact.content,
            user_id=user_id,
        )
        if chunk is not None and chunk.content_hash not in existing:
            db.add(chunk)
            existing.add(chunk.content_hash)
            added += 1

    db.commit()
    return {"added": added}


# ---------- 检索 ----------


def _chunk_is_stale(chunk: CareerKnowledgeChunk) -> bool:
    reference = chunk.last_verified_at or chunk.published_at
    if reference is None:
        return False
    return utcnow() - reference > timedelta(days=STALE_AFTER_DAYS)


def _recency_score(chunk: CareerKnowledgeChunk) -> float:
    """越新越好：30 天内 1.0，线性衰减到 180 天 0.2；无时间不加分不扣分。"""
    reference = chunk.last_verified_at or chunk.published_at
    if reference is None:
        return 0.5
    days = (utcnow() - reference).days
    if days <= STALE_AFTER_DAYS:
        return 1.0
    return max(0.2, 1.0 - (days - STALE_AFTER_DAYS) / 180 * 0.8)


def _rrf_fuse(bm25_hits: list, vector_hits: list, top_k: int) -> dict[int, float]:
    fused: dict[int, float] = {}
    for rank, hit in enumerate(bm25_hits):
        fused[hit.key] = fused.get(hit.key, 0.0) + BM25_WEIGHT / (RRF_K + rank + 1)
    for rank, hit in enumerate(vector_hits):
        fused[hit.key] = fused.get(hit.key, 0.0) + VECTOR_WEIGHT / (RRF_K + rank + 1)
    return dict(sorted(fused.items(), key=lambda kv: kv[1], reverse=True)[:top_k * 2])


def search_knowledge(
    db: Session,
    *,
    user_id: int,
    query: str,
    top_k: int = 5,
    industry_id: str | None = None,
    occupation_id: str | None = None,
    experience_level: str | None = None,
    source_kinds: list[str] | None = None,
) -> dict:
    """混合检索：BM25 + 词面向量 → RRF 融合 → 规则重排序。结果可溯源；无依据时如实说明。"""
    query = (query or "").strip()
    if not query:
        return {"found": False, "results": [], "message": "请输入检索内容"}
    if len(query) > 300:
        query = query[:300]

    statement = (
        select(CareerKnowledgeChunk)
        .where(
            (CareerKnowledgeChunk.scope == "global")
            | (
                (CareerKnowledgeChunk.scope == "user")
                & (CareerKnowledgeChunk.user_id == user_id)
            )
        )
        .limit(2000)
    )
    chunks = list(db.scalars(statement))
    # 元数据过滤（硬过滤：行业/职业/经验/来源类型）
    if industry_id:
        chunks = [c for c in chunks if c.industry_id == industry_id]
    if occupation_id:
        chunks = [c for c in chunks if c.occupation_id == occupation_id]
    if experience_level and experience_level != "不限":
        chunks = [
            c for c in chunks
            if not c.experience_level or c.experience_level == experience_level
            or c.experience_level == "不限"
        ]
    if source_kinds:
        chunks = [c for c in chunks if c.source_kind in set(source_kinds)]
    if not chunks:
        return {
            "found": False,
            "results": [],
            "message": "职业知识库中没有符合筛选条件的资料；未找到可靠依据，不会据此给出建议。",
        }

    # 两路检索
    bm25_index = BM25Index({chunk.id: chunk.title + "\n" + chunk.content for chunk in chunks})
    bm25_hits = bm25_index.search(query, top_k=top_k * 2)
    query_vector = _hash_vector(query)
    vector_scored = [
        (chunk.id, cosine_similarity(query_vector, chunk.vector or []))
        for chunk in chunks
    ]
    vector_scored = [item for item in vector_scored if item[1] > 0]
    vector_scored.sort(key=lambda kv: kv[1], reverse=True)
    from app.services.retrieval import ScoredHit

    vector_hits = [ScoredHit(key=key, score=score) for key, score in vector_scored[:top_k * 2]]

    if not bm25_hits and not vector_hits:
        return {
            "found": False,
            "results": [],
            "message": "没有找到与问题相关的可靠依据；本回答不会基于检索结果展开。",
        }

    fused = _rrf_fuse(bm25_hits, vector_hits, top_k)
    chunk_by_id = {chunk.id: chunk for chunk in chunks}

    # 规则重排序：元数据匹配 + 新近度 + 过期降权
    reranked: list[dict[str, Any]] = []
    for key, fused_score in fused.items():
        chunk = chunk_by_id[key]
        stale = _chunk_is_stale(chunk)
        boost = 0.0
        if occupation_id and chunk.occupation_id == occupation_id:
            boost += 0.15
        if industry_id and chunk.industry_id == industry_id:
            boost += 0.1
        if experience_level and chunk.experience_level == experience_level:
            boost += 0.05
        boost += 0.1 * _recency_score(chunk)
        if stale:
            boost -= 0.2  # 过期资料降权
        reranked.append(
            {
                "chunk_id": chunk.id,
                "title": chunk.title,
                "content": chunk.content,
                "source_kind": chunk.source_kind,
                "source_id": chunk.source_id,
                "source_url": chunk.source_url,
                "scope": chunk.scope,
                "industry_id": chunk.industry_id,
                "occupation_id": chunk.occupation_id,
                "experience_level": chunk.experience_level,
                "published_at": chunk.published_at.isoformat() if chunk.published_at else None,
                "last_verified_at": chunk.last_verified_at.isoformat()
                if chunk.last_verified_at
                else None,
                "stale": stale,
                "stale_note": "该资料超过 30 天未核验，可能已过期" if stale else None,
                "fused_score": round(fused_score, 5),
                "rerank_boost": round(boost, 3),
                "final_score": round(fused_score + max(boost, -0.25), 5),
            }
        )
    reranked.sort(key=lambda item: item["final_score"], reverse=True)
    reranked = reranked[:top_k]
    return {
        "found": True,
        "results": reranked,
        "retrieval_meta": {
            "bm25_weight": BM25_WEIGHT,
            "vector_weight": VECTOR_WEIGHT,
            "vector_kind": "local_hashed_term_vector",
            "vector_dim": VECTOR_DIM,
            "stale_after_days": STALE_AFTER_DAYS,
        },
    }


def evidence_block(db: Session, user_id: int, query: str, top_k: int = 3) -> tuple[str, list[dict]]:
    """供分析/规划使用的检索证据块：返回（可注入的文本块, 来源清单）。
    无可靠依据时返回空块——调用方如实告知「未检索到依据」，不编造。"""
    try:
        outcome = search_knowledge(db, user_id=user_id, query=query, top_k=top_k)
    except Exception:  # noqa: BLE001 — 检索失败不阻塞主流程，但如实降级
        logger.warning("career retrieval failed", exc_info=True)
        return "", []
    if not outcome.get("found"):
        return "", []
    lines = [f"-（{item['title']}）{item['content'][:160]}" for item in outcome["results"]]
    sources = [
        {
            "title": item["title"],
            "source_kind": item["source_kind"],
            "source_id": item["source_id"],
            "source_url": item["source_url"],
            "stale": item["stale"],
        }
        for item in outcome["results"]
    ]
    return "【知识库检索证据（含来源）】\n" + "\n".join(lines), sources


def index_stats(db: Session, user_id: int) -> dict:
    global_count = len(
        list(db.scalars(select(CareerKnowledgeChunk.id).where(CareerKnowledgeChunk.scope == "global")))
    )
    user_count = len(
        list(
            db.scalars(
                select(CareerKnowledgeChunk.id).where(
                    CareerKnowledgeChunk.scope == "user",
                    CareerKnowledgeChunk.user_id == user_id,
                )
            )
        )
    )
    kinds: dict[str, int] = {}
    for kind, count in db.execute(
        select(CareerKnowledgeChunk.source_kind, _count())
        .group_by(CareerKnowledgeChunk.source_kind)
    ):
        kinds[kind] = count
    return {"global_chunks": global_count, "user_chunks": user_count, "by_source_kind": kinds}


def _count():
    from sqlalchemy import func

    return func.count(CareerKnowledgeChunk.id)


def serialize_chunk(chunk: CareerKnowledgeChunk) -> dict:
    return {
        "id": chunk.id,
        "scope": chunk.scope,
        "source_kind": chunk.source_kind,
        "source_id": chunk.source_id,
        "title": chunk.title,
        "content": chunk.content,
        "vector_preview": (chunk.vector or [])[:8],
        "vector_dim": VECTOR_DIM,
    }


def export_stats(db: Session, user_id: int) -> str:
    return json.dumps(index_stats(db, user_id), ensure_ascii=False)
