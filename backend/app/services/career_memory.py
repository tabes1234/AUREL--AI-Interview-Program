"""知途分层记忆：受控上下文组装、会话摘要、档案事实抽取与相关历史召回。

设计原则：
- 不把全部历史塞进每次请求：当前会话取近段窗口，更早内容靠摘要与召回；
- 只有用户确认（或亲述）的事实才进入长期上下文，AI 归纳/推断一律待确认；
- 摘要与召回均可追溯到原始消息，删除的数据立即退出所有检索通道。
"""

import logging
import re

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    CareerConversation,
    CareerMessage,
    CareerProfile,
    CareerProfileFact,
    utcnow,
)
from app.services.ark_client import ArkClient, ArkError
from app.services.retrieval import BM25Index

logger = logging.getLogger("aurel.career")

# 分层记忆参数（受控上下文，避免无限累积）
SUMMARY_TRIGGER_MESSAGES = 24  # 摘要水位线：未摘要消息达到该数量即触发归纳
RECENT_MESSAGE_WINDOW = 12  # 当前会话近段消息窗口
RECALL_TOP_K = 5  # 相关历史召回条数
RECALL_SCAN_LIMIT = 300  # 召回扫描的最近消息上限
FACT_MAX_PER_EXCHANGE = 5

FACT_CATEGORIES = {
    "stage": "当前阶段",
    "major": "专业与教育",
    "skill": "已掌握技能",
    "experience": "经历与项目",
    "industry": "感兴趣的行业",
    "target_role": "目标职业",
    "difficulty": "求职困难",
    "constraint": "地点与方式约束",
    "achievement": "作品与成果",
    "goal": "想提升的能力",
    "other": "其他",
}

# 小鸥人设 v2.0：分层记忆加持，事实/推断分离，不承诺求职结果。
SYSTEM_PROMPT = """你是「观澜 AUREL」的 AI 职业顾问「小鸥」，一只陪伴用户远行的海鸥：
温和、聪明、务实，像一位同行的好友。用户在求职与成长路上向你问路。

回答遵循：
- 用中文，语气自然亲切，不堆砌套话，不居高临下；
- 只基于「已知信息」给建议：绝不编造用户的经历、学历、公司或成果；用户没提到的
  能力既不假设存在、也不判定不存在，需要时坦诚提问；
- 区分事实与推断：引用档案时明确这是用户确认过的信息；你自己的推测要说明
  「我推测 / 可能」，不得把猜测说成用户的真实经历；
- 先直接回应问题，再给 2-3 条可执行的小建议，总长一般不超过 300 字；
- 涉及求职结果保持审慎：不给录用承诺，不预测录取概率或薪资数字；
- 恰当时可建议使用平台功能（问澜面试练习、观己能力快照、知岗岗位解析、
  履历成章简历、合契岗位匹配、知藏知识库、回澜错题本、度衡挑战），但不生硬推销；
- 用户提到重要的新信息（专业、经历、技能、目标、困难、约束）时自然接纳，
  不要反复追问已经给出的信息。"""

FACT_EXTRACT_SYSTEM = """你是职业档案整理员。从对话中提取值得长期记住的职业信息。
只输出 JSON：{"facts": [{"category": "...", "content": "...", "source_type": "...", "quote": "...", "confidence": "..."}]}
规则：
- category 只能取：stage/major/skill/experience/industry/target_role/difficulty/constraint/achievement/goal；
- source_type 取值与要求：
  * user_stated：用户原话明确说出的客观事实，quote 必须是用户原话的连续片段；
  * ai_generalized：基于用户内容归纳的判断（如把经历归纳为能力），quote 给出依据片段；
  * ai_inferred：超出对话内容的推测，confidence 必填（high/mid/low），quote 给出推测依据；
- 绝不编造用户没提过的公司、学历、奖项或成果；没有新信息时返回 {"facts": []}；
- 最多输出 5 条，content 简洁（不超过 60 字）。"""

SUMMARY_SYSTEM = """你是对话摘要员。把对话片段归纳成一份简洁摘要，供后续对话作为记忆背景。
只输出 JSON：{"summary": "摘要正文", "open_questions": ["尚未解决的问题", ...]}。
规则：保留主要问题、目标、结论与未决事项；忠实于原意，不添加对话中不存在的结论；
摘要用中文，不超过 300 字。"""


def get_or_create_profile(db: Session, user_id: int) -> CareerProfile:
    profile = db.scalar(select(CareerProfile).where(CareerProfile.user_id == user_id))
    if profile is None:
        profile = CareerProfile(user_id=user_id)
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile


def confirmed_facts(db: Session, user_id: int, limit: int = 60) -> list[CareerProfileFact]:
    """进入长期上下文的档案事实：用户亲述或已确认。"""
    return list(
        db.scalars(
            select(CareerProfileFact)
            .where(
                CareerProfileFact.user_id == user_id,
                (CareerProfileFact.confirmed.is_(True))
                | (CareerProfileFact.source_type == "user_stated"),
            )
            .order_by(CareerProfileFact.updated_at.desc(), CareerProfileFact.id.desc())
            .limit(limit)
        )
    )


def _facts_block(db: Session, user_id: int) -> str:
    facts = confirmed_facts(db, user_id)
    if not facts:
        return ""
    lines = [
        f"- [{FACT_CATEGORIES.get(fact.category, '其他')}] {fact.content}" for fact in facts
    ]
    return "【已确认的职业档案】\n" + "\n".join(lines)


def recall_related_history(
    db: Session, user_id: int, query: str, exclude_conversation_id: int | None
) -> list[dict]:
    """相关历史召回：BM25 检索本人其他会话的消息、会话摘要与已确认档案。

    只查真实存在的行——已删除的会话/消息/事实天然退出召回。
    """
    rows = list(
        db.execute(
            select(CareerMessage, CareerConversation.title)
            .join(CareerConversation, CareerMessage.conversation_id == CareerConversation.id)
            .where(
                CareerConversation.user_id == user_id,
                CareerConversation.id != exclude_conversation_id,
            )
            .order_by(CareerMessage.id.desc())
            .limit(RECALL_SCAN_LIMIT)
        )
    )
    rows.reverse()
    docs: dict[int, str] = {}
    meta: dict[int, dict] = {}
    for message, title in rows:
        docs[message.id] = message.content
        meta[message.id] = {"kind": "message", "conversation_title": title, "message_id": message.id}
    index = BM25Index(docs)
    hits = index.search(query, top_k=RECALL_TOP_K)
    recalls = []
    for hit in hits:
        info = meta[hit.key]
        content = docs[hit.key]
        recalls.append({**info, "content": content[:200], "score": hit.score})
    return recalls


def _recall_block(recalls: list[dict]) -> str:
    if not recalls:
        return ""
    lines = [
        f"-（会话「{item['conversation_title']}」）{item['content']}" for item in recalls
    ]
    return "【相关历史回忆（来自其他对话）】\n" + "\n".join(lines)


def build_chat_context(
    db: Session, user_id: int, conversation: CareerConversation, current_content: str
) -> tuple[str, str]:
    """组装受控上下文：系统人设 + 档案层 + 召回层 + 当前会话近段 + 新消息。"""
    sections: list[str] = []
    facts_block = _facts_block(db, user_id)
    if facts_block:
        sections.append(facts_block)

    recalls = recall_related_history(db, user_id, current_content, conversation.id)
    recall_block = _recall_block(recalls)
    if recall_block:
        sections.append(recall_block)

    if conversation.summary:
        sections.append(
            "【本会话的早期摘要】\n"
            + conversation.summary
            + f"（覆盖本会话第 1 条到第 {conversation.summarized_until_id} 条消息）"
        )

    recent = list(
        db.scalars(
            select(CareerMessage)
            .where(CareerMessage.conversation_id == conversation.id)
            .order_by(CareerMessage.id.desc())
            .limit(RECENT_MESSAGE_WINDOW)
        )
    )
    recent.reverse()
    if recent:
        transcript = "\n".join(
            f"{'用户' if message.role == 'user' else '小鸥'}：{message.content}"
            for message in recent
        )
        sections.append(f"【本会话的近期对话】\n{transcript}")

    sections.append(f"【用户新消息】\n{current_content}")
    return SYSTEM_PROMPT, "\n\n".join(sections)


def maybe_summarize(db: Session, client: ArkClient, conversation: CareerConversation) -> bool:
    """达到水位线时归纳未摘要的增量消息；失败如实跳过（尽力而为，不阻塞对话）。"""
    pending = list(
        db.scalars(
            select(CareerMessage)
            .where(
                CareerMessage.conversation_id == conversation.id,
                CareerMessage.id > (conversation.summarized_until_id or 0),
            )
            .order_by(CareerMessage.id.asc())
        )
    )
    if len(pending) < SUMMARY_TRIGGER_MESSAGES:
        return False
    transcript = "\n".join(
        f"{'用户' if message.role == 'user' else '小鸥'}：{message.content[:500]}"
        for message in pending
    )
    existing = f"【已有摘要（请合并，不要丢失原有信息）】\n{conversation.summary}\n\n" if conversation.summary else ""
    try:
        data = client.chat_json(
            SUMMARY_SYSTEM,
            f"{existing}【新增对话片段】\n{transcript}",
            temperature=0.2,
            service="career_summary",
        )
    except ArkError as exc:
        logger.warning("career summary skipped: %s", exc)
        return False
    summary = data.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        return False
    conversation.summary = summary.strip()
    conversation.summarized_until_id = pending[-1].id
    db.commit()
    return True


def _normalize(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def _valid_fact_item(
    item: dict, user_content: str
) -> CareerProfileFact | None:
    """校验单条抽取结果；伪造的 user_stated（原文定位不到）降级为 AI 归纳。"""
    if not isinstance(item, dict):
        return None
    content = str(item.get("content") or "").strip()
    if not content:
        return None
    category = str(item.get("category") or "other").strip()
    if category not in FACT_CATEGORIES:
        category = "other"
    source_type = str(item.get("source_type") or "").strip()
    if source_type not in {"user_stated", "ai_generalized", "ai_inferred"}:
        source_type = "ai_generalized"
    quote = str(item.get("quote") or "").strip() or None
    confidence = str(item.get("confidence") or "").strip().lower()
    if confidence not in {"high", "mid", "low"}:
        confidence = None

    if source_type == "user_stated":
        if not quote or _normalize(quote) not in _normalize(user_content):
            # 原文定位不到：不能算用户亲述，降级为待确认的 AI 归纳
            source_type = "ai_generalized"
            confidence = None
    if source_type == "ai_inferred" and confidence is None:
        confidence = "mid"
    confirmed = source_type == "user_stated"
    return CareerProfileFact(
        category=category,
        content=content[:120],
        source_type=source_type,
        confidence=confidence if source_type == "ai_inferred" else None,
        quote=quote,
        confirmed=confirmed,
    )


def _dedupe_facts(db: Session, user_id: int, candidates: list[CareerProfileFact]) -> list[CareerProfileFact]:
    existing = {
        _normalize(fact.content)
        for fact in db.scalars(select(CareerProfileFact).where(CareerProfileFact.user_id == user_id))
    }
    unique: list[CareerProfileFact] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = _normalize(candidate.content)
        if not key or key in existing or key in seen:
            continue
        seen.add(key)
        unique.append(candidate)
    return unique[:FACT_MAX_PER_EXCHANGE]


def _extract_facts(
    db: Session,
    client: ArkClient,
    user_id: int,
    source_message_id: int | None,
    transcript: str,
    user_content: str,
) -> list[CareerProfileFact]:
    data = client.chat_json(
        FACT_EXTRACT_SYSTEM, transcript, temperature=0.2, service="career_fact_extract"
    )
    raw_items = data.get("facts")
    if not isinstance(raw_items, list):
        return []
    candidates = [
        fact
        for fact in (_valid_fact_item(item, user_content) for item in raw_items[:8])
        if fact is not None
    ]
    candidates = _dedupe_facts(db, user_id, candidates)
    if not candidates:
        return []
    profile = get_or_create_profile(db, user_id)
    for candidate in candidates:
        candidate.user_id = user_id
        candidate.profile_id = profile.id
        candidate.source_message_id = source_message_id
    db.add_all(candidates)
    db.commit()
    return candidates


def extract_facts_from_exchange(
    db: Session,
    client: ArkClient,
    user_id: int,
    user_message: CareerMessage,
    assistant_content: str,
) -> list[CareerProfileFact]:
    """一轮问答后抽取候选档案事实（user_stated 自动确认，其余待确认）。"""
    transcript = (
        f"用户：{user_message.content}\n小鸥：{assistant_content[:800]}"
    )
    return _extract_facts(db, client, user_id, user_message.id, transcript, user_message.content)


def organize_profile_from_history(
    db: Session,
    client: ArkClient,
    user_id: int,
    conversation: CareerConversation | None = None,
    message_limit: int = 60,
) -> list[CareerProfileFact]:
    """AI 整理历史对话，产出待确认的档案候选（全部不自动确认）。"""
    statement = (
        select(CareerMessage, CareerConversation.title)
        .join(CareerConversation, CareerMessage.conversation_id == CareerConversation.id)
        .where(CareerConversation.user_id == user_id)
    )
    if conversation is not None:
        statement = statement.where(CareerConversation.id == conversation.id)
    rows = list(
        db.execute(statement.order_by(CareerMessage.id.desc()).limit(message_limit))
    )
    rows.reverse()
    if not rows:
        return []
    transcript = "\n".join(
        f"（会话「{title}」）{'用户' if message.role == 'user' else '小鸥'}：{message.content[:300]}"
        for message, title in rows
    )
    return _extract_facts(db, client, user_id, None, transcript, "")


def profile_counts(db: Session, user_id: int) -> dict:
    confirmed = db.scalar(
        select(func.count(CareerProfileFact.id)).where(
            CareerProfileFact.user_id == user_id,
            (CareerProfileFact.confirmed.is_(True))
            | (CareerProfileFact.source_type == "user_stated"),
        )
    )
    total = db.scalar(
        select(func.count(CareerProfileFact.id)).where(CareerProfileFact.user_id == user_id)
    )
    return {"confirmed_count": int(confirmed or 0), "pending_count": int(total or 0) - int(confirmed or 0)}
