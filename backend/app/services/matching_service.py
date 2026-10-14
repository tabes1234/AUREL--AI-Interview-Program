"""T9：简历与岗位语义匹配。

匹配依据全部真实可解释：
- 统计层：技能词典命中（简历原文证据 + 岗位要求原文证据）、BM25 相似度总分
- 增强层：LLM 生成改进建议（真实调用）；失败时降级为纯统计结果并如实标注
"""

import re
from dataclasses import dataclass

from app.services.ark_client import ArkClient, ArkError
from app.services.retrieval import BM25Index

# 常见技能词典（中英别名归一）
SKILL_ALIASES: dict[str, list[str]] = {
    "JavaScript": ["javascript", "js"],
    "TypeScript": ["typescript", "ts"],
    "React": ["react"],
    "Vue": ["vue", "vuejs"],
    "Node.js": ["node", "nodejs", "node.js"],
    "Python": ["python"],
    "Java": ["java"],
    "Go": ["golang", "go"],
    "SQL": ["sql"],
    "MySQL": ["mysql"],
    "PostgreSQL": ["postgresql", "postgres"],
    "Redis": ["redis"],
    "MongoDB": ["mongodb"],
    "Docker": ["docker"],
    "Kubernetes": ["kubernetes", "k8s"],
    "Git": ["git"],
    "Linux": ["linux"],
    "Webpack": ["webpack"],
    "FastAPI": ["fastapi"],
    "Django": ["django"],
    "Flask": ["flask"],
    "Spring": ["spring", "springboot"],
    "机器学习": ["机器学习", "machinelearning"],
    "深度学习": ["深度学习", "deeplearning"],
    "数据分析": ["数据分析", "dataanalysis"],
    "产品设计": ["产品设计", "产品规划"],
    "项目管理": ["项目管理", "projectmanagement", "pmp"],
    "沟通协作": ["沟通", "协作", "跨部门"],
}

# 技能在岗位描述中出现的典型表述（用于抽取岗位侧证据）
_JOB_SPLIT_RE = re.compile(r"[。；;！!？?\n，,]")


@dataclass
class MatchResult:
    match_score: float
    matched_skills: list[dict]
    missing_skills: list[str]
    suggestions: list[str]
    llm_error: str | None
    model_name: str | None


def _find_sentence(text: str, token: str, limit: int = 80) -> str | None:
    """在原文中找到包含 token 的句子作为证据。"""
    lowered = text.lower()
    pos = lowered.find(token)
    if pos == -1:
        return None
    start = max(0, text.rfind("\n", 0, pos) + 1)
    end = text.find("\n", pos)
    if end == -1:
        end = len(text)
    sentence = text[start:end].strip()
    return sentence[:limit] + ("…" if len(sentence) > limit else "")


def _text_contains(text: str, alias: str) -> bool:
    """英文别名按词边界匹配（Java 不误命中 JavaScript、js 不误命中 node.js），中文按子串。"""
    if re.fullmatch(r"[a-z0-9.+#]+", alias):
        return re.search(rf"(?<![a-z0-9.]){re.escape(alias)}(?![a-z0-9])", text) is not None
    return alias in text


def extract_matched_skills(resume_text: str, job_description: str) -> tuple[list[dict], list[str]]:
    """按技能词典匹配：返回（命中技能含双侧证据, 缺失技能）。"""
    resume_lower = resume_text.lower()
    job_lower = job_description.lower() if job_description else ""
    matched: list[dict] = []
    missing: list[str] = []
    for skill, aliases in SKILL_ALIASES.items():
        hit_alias = next((a for a in aliases if _text_contains(resume_lower, a)), None)
        job_alias = next((a for a in aliases if job_lower and _text_contains(job_lower, a)), None)
        if hit_alias and job_alias:
            evidence = _find_sentence(resume_text, hit_alias)
            job_evidence = _find_sentence(job_description, job_alias) if job_description else None
            matched.append(
                {"skill": skill, "evidence": evidence, "job_evidence": job_evidence}
            )
        elif hit_alias and not job_alias:
            # 简历有但岗位未提：不算缺失，也不算强匹配，略过
            continue
        elif job_alias and not hit_alias:
            missing.append(skill)
    matched.sort(key=lambda m: m["skill"])
    return matched, missing


def compute_match_score(
    resume_text: str, job_description: str, matched_count: int, missing_count: int
) -> float:
    """综合分 = 覆盖率主导 + BM25 语义相关性微调（0-100）。"""
    total = matched_count + missing_count
    coverage = matched_count / total if total else 0.0
    relevance = 0.0
    if job_description.strip():
        index = BM25Index({0: resume_text})
        hits = index.search(job_description, top_k=1)
        if hits:
            # 归一化：BM25 分数无上界，映射到 0-1（经验分母）
            relevance = min(hits[0].score / 40.0, 1.0)
    score = coverage * 80 + relevance * 20
    return round(min(score, 100.0), 1)


def generate_suggestions(
    client: ArkClient,
    *,
    position: str,
    matched_skills: list[str],
    missing_skills: list[str],
    match_score: float,
) -> list[str]:
    """LLM 生成针对性提升建议（真实调用）。"""
    system = "你是资深职业顾问。只输出 JSON，不输出任何解释。"
    user = (
        f"目标岗位：{position}\n"
        f"匹配得分：{match_score}/100\n"
        f"已具备技能：{'、'.join(matched_skills) if matched_skills else '（无明确命中）'}\n"
        f"岗位要求但简历缺失的技能：{'、'.join(missing_skills) if missing_skills else '（无）'}\n"
        f"生成 3 条具体可执行的改进建议，每条不超过 60 字。\n"
        f'输出：{{"suggestions": ["建议1", "建议2", "建议3"]}}'
    )
    data = client.chat_json(system, user, service="matching_suggestions")
    suggestions = data.get("suggestions")
    if not isinstance(suggestions, list):
        raise ArkError("AI 模型未返回有效的建议列表")
    cleaned = [s.strip() for s in suggestions if isinstance(s, str) and s.strip()]
    if not cleaned:
        raise ArkError("AI 模型未返回有效建议")
    return cleaned[:3]


def match_resume(
    db_or_none,
    client: ArkClient | None,
    *,
    position: str,
    job_description: str,
    resume_text: str,
) -> MatchResult:
    """完整匹配流程：统计层必算，LLM 层尽力而为（失败降级并如实标注）。"""
    matched, missing = extract_matched_skills(resume_text, job_description)
    score = compute_match_score(resume_text, job_description, len(matched), len(missing))

    suggestions: list[str] = []
    llm_error: str | None = None
    model_name: str | None = None
    if client is not None:
        try:
            suggestions = generate_suggestions(
                client,
                position=position,
                matched_skills=[m["skill"] for m in matched],
                missing_skills=missing,
                match_score=score,
            )
            model_name = client.model
        except ArkError as exc:
            llm_error = str(exc)

    return MatchResult(
        match_score=score,
        matched_skills=matched,
        missing_skills=missing,
        suggestions=suggestions,
        llm_error=llm_error,
        model_name=model_name,
    )
