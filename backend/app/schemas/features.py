"""T2 知识库 / T3 技能图谱 / T9 简历匹配的 Pydantic 模型。"""

from datetime import datetime

from pydantic import BaseModel, Field


# ---------- T2 知识库 ----------

class EvidenceOut(BaseModel):
    """检索证据：真实分块原文 + 来源文档 + BM25 分数（可追溯）。"""

    document_id: int
    document_title: str
    chunk_id: int
    chunk_index: int
    content: str
    score: float


class KnowledgeChunkOut(BaseModel):
    id: int
    chunk_index: int
    content: str
    char_count: int

    model_config = {"from_attributes": True}


class KnowledgeDocumentOut(BaseModel):
    id: int
    title: str
    filename: str
    char_count: int
    status: str
    error_message: str | None = None
    created_at: datetime
    chunk_count: int = 0

    model_config = {"from_attributes": True}


class KnowledgeDocumentDetail(KnowledgeDocumentOut):
    content_text: str
    chunks: list[KnowledgeChunkOut]


class KnowledgeSearchResponse(BaseModel):
    query: str
    evidence: list[EvidenceOut]


# ---------- T3 技能图谱 / 自适应训练 ----------

class SkillProfileResponse(BaseModel):
    has_data: bool
    completed_interviews: int = 0
    average_score: float | None = None
    latest_score: float | None = None
    dimension_averages: dict[str, float] = Field(default_factory=dict)
    positions_practiced: list[str] = Field(default_factory=list)


class TrainingRecommendationResponse(BaseModel):
    available: bool
    message: str | None = None
    weakest_dimension: str | None = None
    weakest_score: float | None = None
    strongest_dimension: str | None = None
    suggested_difficulty: str | None = None
    focus_hint: str | None = None
    reasons: list[str] = Field(default_factory=list)
    based_on: dict = Field(default_factory=dict)


class SkillGraphResponse(BaseModel):
    available: bool
    nodes: list[dict] = Field(default_factory=list)
    score_history: list[dict] = Field(default_factory=list)
    average_score: float | None = None
    latest_score: float | None = None
    positions_practiced: list[str] = Field(default_factory=list)


# ---------- T9 简历匹配 ----------

class ResumeMatchRequest(BaseModel):
    position: str = Field(min_length=2, max_length=120)
    job_description: str = Field(default="", max_length=4000)
    resume_text: str = Field(min_length=30, max_length=20000)


class MatchedSkillOut(BaseModel):
    skill: str
    evidence: str | None = None
    job_evidence: str | None = None


class ResumeMatchResultOut(BaseModel):
    match_score: float
    matched_skills: list[MatchedSkillOut]
    missing_skills: list[str]
    suggestions: list[str]
    llm_error: str | None = None


class ResumeMatchRecordOut(BaseModel):
    id: int
    position: str
    match_score: float
    created_at: datetime

    model_config = {"from_attributes": True}


class ResumeMatchDetail(ResumeMatchRecordOut):
    job_description: str
    resume_text: str
    result: ResumeMatchResultOut
    model_name: str | None = None


class ResumeMatchResponse(BaseModel):
    id: int
    match_score: float
    matched_skills: list[MatchedSkillOut]
    missing_skills: list[str]
    suggestions: list[str]
    llm_error: str | None = None
    model_name: str | None = None
