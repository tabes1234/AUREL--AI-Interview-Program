"""知岗 × 履历成章：结构化岗位与简历的可解释匹配（复用合契统计匹配层）。

匹配结论全部带理由与证据：
- matched_skills：词典命中 + 简历原文证据 + JD 原文证据 + 支撑该技能的具体经历条目；
- missing_skills：JD 明确要求但简历未体现，附原文证据与补充方向；
- uncertain_items：无法给出可靠证据的项，如实标注原因；
- match_score 仅为系统内部文本匹配指标（覆盖率 + BM25 相关性），不代表获得工作的概率。
"""

from app.schemas.resume import ResumeContent
from app.services import matching_service
from app.services.jd_analysis import NOT_STATED


def _entry_label(kind: str, name: str, role: str) -> str:
    base = name or role or "未命名条目"
    return f"{kind}：{base}" + (f"（{role}）" if role and name and role != name else "")


def flatten_resume_text(content: ResumeContent) -> tuple[str, list[dict]]:
    """把结构化简历展平为全文文本，同时返回可定位的经历条目（用于支撑证据）。"""
    parts: list[str] = []
    basics = content.basics
    if basics.summary:
        parts.append(basics.summary)
    if basics.links:
        parts.append(basics.links)

    experiences: list[dict] = []
    for entry in content.work:
        line = " ".join([entry.name, entry.role, *entry.highlights]).strip()
        if line:
            parts.append(line)
            experiences.append(
                {"kind": "工作经历", "label": _entry_label("工作经历", entry.name, entry.role), "text": line}
            )
    for entry in content.projects:
        line = " ".join([entry.name, entry.role, *entry.highlights]).strip()
        if line:
            parts.append(line)
            experiences.append(
                {"kind": "项目经历", "label": _entry_label("项目经历", entry.name, entry.role), "text": line}
            )
    for entry in content.education:
        line = " ".join([entry.school, entry.degree, entry.major, entry.details]).strip()
        if line:
            parts.append(line)
    for entry in content.skills:
        line = " ".join([entry.name, entry.level, entry.detail]).strip()
        if line:
            parts.append(line)
    for entry in content.certificates:
        line = " ".join([entry.name, entry.issuer]).strip()
        if line:
            parts.append(line)
    for entry in content.awards:
        line = " ".join([entry.name, entry.issuer, entry.detail]).strip()
        if line:
            parts.append(line)
    return "\n".join(parts), experiences


def flatten_jd_text(jd_text: str, analysis_result: dict) -> str:
    """JD 原文 + 结构化结论合并为岗位侧匹配文本。"""
    parts = [jd_text]
    for key in ("responsibilities", "required_skills", "preferred_skills", "tools"):
        for item in analysis_result.get(key, []):
            if isinstance(item, dict) and item.get("text") and item["text"] != NOT_STATED:
                parts.append(str(item["text"]))
    return "\n".join(parts)


def _supporting_experiences(skill: str, aliases: list[str], experiences: list[dict]) -> list[str]:
    """找到简历中实际支撑该技能结论的经历条目（按别名在条目文本中定位）。"""
    supporting: list[str] = []
    for experience in experiences:
        haystack = experience["text"].lower()
        if any(alias in haystack for alias in (*aliases, skill.lower())):
            supporting.append(experience["label"])
    return supporting


def _structured_skill_texts(analysis_result: dict) -> list[str]:
    """JD 结构化结论中的技能集合（必需 + 加分 + 工具），词典之外的技能同样参与匹配。"""
    skills: list[str] = []
    seen: set[str] = set()
    for key in ("required_skills", "preferred_skills", "tools"):
        for item in analysis_result.get(key, []):
            if isinstance(item, dict):
                text = str(item.get("text", "")).strip()
                if text and text != NOT_STATED and text.lower() not in seen:
                    skills.append(text)
                    seen.add(text.lower())
    return skills


def match_analysis_with_resume(
    client,
    *,
    jd_text: str,
    analysis_result: dict,
    resume_content: ResumeContent,
) -> dict:
    """统计匹配必算；LLM 建议尽力而为（失败降级并如实标注 llm_error）。"""
    resume_flat, experiences = flatten_resume_text(resume_content)
    jd_flat = flatten_jd_text(jd_text, analysis_result)

    matched, missing = matching_service.extract_matched_skills(resume_flat, jd_flat)

    # 结构化技能补全：合契词典之外的技能（如 Webpack）也必须参与匹配与缺失判断
    covered = {m["skill"].lower() for m in matched} | {m.lower() for m in missing}
    resume_lower = resume_flat.lower()
    for skill in _structured_skill_texts(analysis_result):
        if skill.lower() in covered:
            continue
        if matching_service._text_contains(resume_lower, skill.lower()):
            matched.append(
                {
                    "skill": skill,
                    "evidence": matching_service._find_sentence(resume_flat, skill.lower()),
                    "job_evidence": matching_service._find_sentence(jd_flat, skill.lower()),
                }
            )
        else:
            missing.append(skill)
        covered.add(skill.lower())
    matched.sort(key=lambda m: m["skill"].lower())

    score = matching_service.compute_match_score(
        resume_flat, jd_flat, len(matched), len(missing)
    )

    # 支撑经历与不确定项
    for item in matched:
        aliases = matching_service.SKILL_ALIASES.get(item["skill"], [item["skill"].lower()])
        item["supporting_experiences"] = _supporting_experiences(item["skill"], aliases, experiences)
    uncertain: list[dict] = []
    for item in matched:
        if not item.get("evidence"):
            uncertain.append(
                {"skill": item["skill"], "reason": "简历与岗位要求词面匹配，但未能在简历中定位到具体描述句"}
            )
    missing_detailed: list[dict] = []
    for skill in missing:
        aliases = matching_service.SKILL_ALIASES.get(skill, [skill.lower()])
        job_evidence = matching_service._find_sentence(jd_flat, aliases[0]) if aliases else None
        missing_detailed.append(
            {
                "skill": skill,
                "job_evidence": job_evidence,
                "suggestion": f"JD 明确要求 {skill}，但简历尚未体现：可在相关经历中补充真实使用证据，"
                "或如实标注为学习中。",
            }
        )

    # LLM 建议（真实调用，失败降级）
    suggestions: list[str] = []
    llm_error: str | None = None
    model_name: str | None = None
    if client is not None:
        position = str(analysis_result.get("position_name", "目标岗位"))
        try:
            suggestions = matching_service.generate_suggestions(
                client,
                position=position,
                matched_skills=[m["skill"] for m in matched],
                missing_skills=missing,
                match_score=score,
            )
            model_name = client.model
        except matching_service.ArkError as exc:
            llm_error = str(exc)

    return {
        "matched_skills": matched,
        "missing_skills": missing_detailed,
        "uncertain_items": uncertain,
        "suggestions": suggestions,
        "match_score": score,
        "score_note": "该分数是系统内部的文本匹配指标（技能覆盖率与语义相关性加权），"
        "仅反映简历文本与岗位描述的重合程度，不代表获得工作的概率。",
        "model_name": model_name,
        "llm_error": llm_error,
    }
