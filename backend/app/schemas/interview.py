"""面试流程的 Pydantic 请求/响应模型。"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

Difficulty = Literal["basic", "intermediate", "advanced"]
InterviewLanguage = Literal["zh", "en"]

DIFFICULTIES: list[str] = ["basic", "intermediate", "advanced"]
LANGUAGES: list[str] = ["zh", "en"]

# ---------- 问澜：行业职业目录与结构化题集 ----------

ExperienceLevel = Literal[
    "student", "fresh_graduate", "junior", "mid", "senior", "expert", "management"
]
InterviewType = Literal[
    "screening", "technical", "behavioral", "case", "leadership", "comprehensive"
]
FocusArea = Literal[
    "knowledge", "project", "practice", "analysis", "communication",
    "behavior", "scenario", "case_analysis", "comprehensive",
]
QuestionCategory = Literal[
    "knowledge", "project", "practice", "analysis", "communication",
    "behavior", "scenario", "case_analysis",
]

ALLOWED_QUESTION_COUNTS = (5, 8, 10, 15)
JOB_DESCRIPTION_MAX = 2000


class QuestionSetGenerateRequest(BaseModel):
    """问澜题集生成请求：行业 + 职业（可自定义）+ 更多设置。"""

    industry_id: str = Field(min_length=2, max_length=60)
    occupation_id: str = Field(min_length=2, max_length=60)
    custom_occupation: str | None = Field(default=None, max_length=60)
    experience_level: ExperienceLevel = "fresh_graduate"
    interview_type: InterviewType = "comprehensive"
    focus_areas: list[FocusArea] = Field(default_factory=lambda: ["comprehensive"])
    difficulty: Difficulty = "intermediate"
    language: InterviewLanguage = "zh"
    question_count: int = 10
    # 岗位描述仅作为参考数据注入提示词（有长度限制与防注入包裹），不是指令
    job_description: str = Field(default="", max_length=JOB_DESCRIPTION_MAX)
    knowledge_document_id: int | None = None

    @field_validator("focus_areas")
    @classmethod
    def _dedupe_focus(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(value))[:9]

    @field_validator("question_count")
    @classmethod
    def _allowed_count(cls, value: int) -> int:
        if value not in ALLOWED_QUESTION_COUNTS:
            raise ValueError(f"题目数量仅支持 {'、'.join(str(c) for c in ALLOWED_QUESTION_COUNTS)} 道")
        return value


class InterviewCreateRequest(BaseModel):
    position: str = Field(min_length=2, max_length=120)
    description: str = Field(default="", max_length=1000)
    difficulty: Difficulty
    language: InterviewLanguage
    question_count: int = Field(ge=3, le=8)
    # T2 RAG：可选指定知识库文档，出题时检索该文档相关内容作为依据
    knowledge_document_id: int | None = None


class AnswerCreateRequest(BaseModel):
    question_id: int
    content: str = Field(min_length=1, max_length=4000)


class QuestionOut(BaseModel):
    id: int
    order_index: int
    type: Literal["main", "follow_up"]
    parent_question_id: int | None
    content: str
    answer: str | None = None
    # 问澜结构化题元数据（旧任务为 null）
    category: str | None = None  # 题型：knowledge/project/practice/analysis/...
    dimension: str | None = None  # 能力维度
    goal: str | None = None  # 考查目标
    rubric: list[str] | None = None  # 评分要点
    suggested_follow_up: str | None = None  # 可选追问

    model_config = {"from_attributes": True}


class TaskSummary(BaseModel):
    id: int
    position: str
    difficulty: Difficulty
    language: InterviewLanguage
    question_count: int
    status: str
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime
    overall_score: float | None = None
    # 问澜目录上下文（旧任务为 null）
    industry_id: str | None = None
    occupation_id: str | None = None
    experience_level: str | None = None
    interview_type: str | None = None


class TaskDetail(TaskSummary):
    description: str
    questions: list[QuestionOut]
    current_question_id: int | None = None


class AnswerResponse(BaseModel):
    """提交回答后的响应：告知下一步是追问、下一题还是全部完成。"""

    task_status: str
    answered_question_id: int
    next_question: QuestionOut | None = None
    all_answered: bool
    report_id: int | None = None


class FinishResponse(BaseModel):
    task_id: int
    status: str
    report_id: int | None = None


class ScoreDimension(BaseModel):
    name: str
    score: float = Field(ge=0, le=10)
    evidence: str
    rationale: str


class ImprovementItem(BaseModel):
    title: str
    detail: str


class ReportOut(BaseModel):
    id: int
    task_id: int
    overall_score: float
    summary: str
    dimensions: list[ScoreDimension]
    strengths: list[str]
    improvements: list[ImprovementItem]
    model_name: str
    created_at: datetime
    # 附带任务信息便于报告页展示
    position: str
    difficulty: Difficulty
    language: InterviewLanguage


class AiStatusResponse(BaseModel):
    configured: bool
    model: str | None = None
    base_url: str
    message: str
