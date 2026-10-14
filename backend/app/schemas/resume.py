"""履历成章 API Schema：结构化简历内容、模板、版本与导出。

所有结构化字段都有长度上限：导出与展示基于同一结构，防止超长文本破坏版式。
"""

from datetime import datetime

from pydantic import BaseModel, Field


# ---------- 结构化简历内容 ----------


class ResumeBasics(BaseModel):
    """基本资料。"""

    name: str = Field(default="", max_length=40)
    phone: str = Field(default="", max_length=30)
    email: str = Field(default="", max_length=120)
    location: str = Field(default="", max_length=60)
    links: str = Field(default="", max_length=200)  # 主页 / 作品集 / 仓库链接
    summary: str = Field(default="", max_length=600)  # 个人概述


class EducationEntry(BaseModel):
    """教育经历。"""

    school: str = Field(default="", max_length=80)
    degree: str = Field(default="", max_length=40)
    major: str = Field(default="", max_length=60)
    start: str = Field(default="", max_length=20)
    end: str = Field(default="", max_length=20)
    details: str = Field(default="", max_length=400)


class ExperienceEntry(BaseModel):
    """实习 / 工作经历与项目经历共用的条目结构。"""

    name: str = Field(default="", max_length=80)  # 公司或项目名
    role: str = Field(default="", max_length=60)
    start: str = Field(default="", max_length=20)
    end: str = Field(default="", max_length=20)
    link: str = Field(default="", max_length=200)
    highlights: list[str] = Field(default_factory=list, max_length=8)


class SkillEntry(BaseModel):
    """技能与工具。"""

    name: str = Field(default="", max_length=40)
    level: str = Field(default="", max_length=20)
    detail: str = Field(default="", max_length=120)


class CertificateEntry(BaseModel):
    """证书与语言能力。"""

    name: str = Field(default="", max_length=80)
    issuer: str = Field(default="", max_length=80)
    date: str = Field(default="", max_length=20)


class AwardEntry(BaseModel):
    """奖项或其他真实经历。"""

    name: str = Field(default="", max_length=80)
    issuer: str = Field(default="", max_length=80)
    date: str = Field(default="", max_length=20)
    detail: str = Field(default="", max_length=300)


class ResumeContent(BaseModel):
    """简历全量结构化内容（保存与版本快照共用）。"""

    basics: ResumeBasics = Field(default_factory=ResumeBasics)
    education: list[EducationEntry] = Field(default_factory=list, max_length=10)
    work: list[ExperienceEntry] = Field(default_factory=list, max_length=15)
    projects: list[ExperienceEntry] = Field(default_factory=list, max_length=15)
    skills: list[SkillEntry] = Field(default_factory=list, max_length=30)
    certificates: list[CertificateEntry] = Field(default_factory=list, max_length=20)
    awards: list[AwardEntry] = Field(default_factory=list, max_length=20)

    def model_post_init(self, __context) -> None:  # noqa: D105
        # highlights 单条长度限制（列表长度已由 max_length 约束）
        for entry in (*self.work, *self.projects):
            entry.highlights = [h.strip()[:300] for h in entry.highlights if isinstance(h, str)]


# ---------- 模板 / 版本 / 请求 ----------


class ResumeTemplateOut(BaseModel):
    id: str
    name: str
    description: str
    section_order: list[str]
    accent: str  # 主题色（十六进制）


class ResumeCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    template_id: str = Field(default="clean", max_length=40)
    content: ResumeContent = Field(default_factory=ResumeContent)


class ResumeSaveRequest(BaseModel):
    title: str | None = Field(default=None, max_length=120)
    template_id: str | None = Field(default=None, max_length=40)
    content: ResumeContent
    note: str = Field(default="", max_length=200)  # 版本备注


class ResumeSummary(BaseModel):
    id: int
    title: str
    template_id: str
    current_version_no: int
    created_at: datetime
    updated_at: datetime


class ResumeDetail(ResumeSummary):
    content: dict
    versions: list["ResumeVersionSummary"] = Field(default_factory=list)


class ResumeVersionSummary(BaseModel):
    version_no: int
    title: str
    template_id: str
    note: str
    created_at: datetime


class ResumeVersionDetail(ResumeVersionSummary):
    content: dict


class ResumePolishRequest(BaseModel):
    """AI 表达优化请求：仅对用户已有文本改写表达，不保存、不捏造。"""

    section: str = Field(pattern="^(summary|work|projects|awards)$")
    text: str = Field(min_length=5, max_length=2000)


class ResumePolishResponse(BaseModel):
    polished: str
    notes: str
    model_name: str | None


class TemplateSourceOut(BaseModel):
    """模板设计参考来源：官方指导资料 + 查阅时间（真实可追溯）。"""

    name: str
    url: str
    purpose: str
    consulted_on: str  # 查阅日期（YYYY-MM-DD）


class ResumeOptimizeForJobRequest(BaseModel):
    """面向真实岗位的简历优化诊断请求：给出知岗分析 ID 或直接粘贴 JD。"""

    job_analysis_id: int | None = None
    jd_text: str | None = Field(default=None, max_length=20000)
    position: str = Field(default="", max_length=120)


class ResumeOptimizeForJobResponse(BaseModel):
    keyword_gaps: list[dict]  # [{skill, job_evidence}] — 统计层计算，真实可复算
    weak_points: list[dict]  # [{text, reason, question}] — 引用逐字来自简历原文
    restructure_advice: str  # STAR/CAR 结构建议（只讲方法，不代写事实）
    position: str
    model_name: str | None


class ResumeParseResponse(BaseModel):
    """拖拽解析简历的结果。

    text 为安全提取的纯文本（确定性，恒返回）；
    title / position / content 为 AI 忠实转录的结构化结果，
    AI 不可用或未通过校验时为空并如实附 parse_error，绝不伪造。
    """

    filename: str
    text: str
    title: str | None = None
    position: str | None = None
    content: dict | None = None
    parse_error: str | None = None


ResumeDetail.model_rebuild()
