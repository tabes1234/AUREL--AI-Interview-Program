"""知岗 API Schema：JD 解析请求/响应、问澜联动、简历匹配。"""

from datetime import datetime

from pydantic import BaseModel, Field


class JdAnalyzeRequest(BaseModel):
    """粘贴 JD 文本解析请求；source_job_id 表示该 JD 来自知潮资料库条目。"""

    jd_text: str = Field(min_length=1, max_length=20000)
    source_job_id: int | None = None


class JdUploadResponse(BaseModel):
    """JD 文件上传解析结果（仅提取文本，不调用模型）。"""

    filename: str
    text: str
    char_count: int


class JobAnalysisSummary(BaseModel):
    """分析历史列表项。"""

    id: int
    title: str
    version_no: int
    status: str
    created_at: datetime
    jd_preview: str  # 输入文本摘要（前 120 字）
    source_job_id: int | None = None  # 来自知潮资料库的岗位 ID（可空）


class JobAnalysisDetail(JobAnalysisSummary):
    """分析详情：完整原文 + 结构化结果 + 证据/推断标记。"""

    jd_text: str
    result: dict | None
    model_name: str | None
    error_message: str | None
    user_edited: bool = False  # 解析结果是否被用户人工修改过


class JobAnalysisUpdateRequest(BaseModel):
    """用户修改知岗解析结果：整体替换结构化结果，服务端重新做证据核验。"""

    title: str | None = Field(default=None, min_length=1, max_length=120)
    result: dict


class InterviewFromJobRequest(BaseModel):
    """依据知岗分析生成面试题：允许用户修改岗位信息后再生成。"""

    position: str | None = Field(default=None, max_length=120)
    difficulty: str = Field(default="intermediate", pattern="^(basic|intermediate|advanced)$")
    language: str = Field(default="zh", pattern="^(zh|en)$")
    question_count: int = Field(default=5, ge=3, le=10)


class JobResumeMatchRequest(BaseModel):
    """知岗分析结果与指定简历的结构化匹配。"""

    resume_id: int


class JobResumeMatchResponse(BaseModel):
    """匹配结果：每项结论均带理由与证据；score 仅为系统内部文本匹配指标。"""

    job_analysis_id: int
    resume_id: int
    resume_title: str
    matched_skills: list[dict]  # [{skill, evidence, job_evidence, supporting_experiences}]
    missing_skills: list[dict]  # [{skill, job_evidence, suggestion}]
    uncertain_items: list[dict]  # [{skill, reason}]
    suggestions: list[str]
    match_score: float
    score_note: str
    model_name: str | None
    llm_error: str | None
