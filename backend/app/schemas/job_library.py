"""知潮 API Schema：岗位目录、导入、收藏、来源核验与模块联动。"""

from datetime import datetime

from pydantic import BaseModel, Field


class JobPositionOut(BaseModel):
    """岗位目录/详情公开字段：原文全文不公开（display_permission=summary_only）。"""

    id: int
    company: str
    company_url: str | None
    title: str
    industry_id: str | None
    industry_name: str | None
    occupation_id: str | None
    occupation_name: str | None
    location: str
    level: str
    published_at: datetime | None  # 来源未提供时为 null（前端显示 published_note）
    published_note: str
    source_updated_at: datetime | None
    source_url: str | None
    source_type: str
    display_permission: str
    responsibilities_summary: str
    required_skills_summary: str
    preferred_skills_summary: str
    experience_summary: str
    hiring_status: str
    link_status: str
    last_verified_at: datetime | None
    verified_note: str | None
    stale_hint: bool  # 超过核验周期或链接失效 → 「可能已过期」
    is_favorited: bool = False
    imported_by: int | None = None
    created_at: datetime


class JobPositionChangeOut(BaseModel):
    id: int
    change_type: str
    note: str
    created_at: datetime


class JobPositionDetail(JobPositionOut):
    """岗位详情：附最近变化记录（历史可回溯）。"""

    changes: list[JobPositionChangeOut] = []


class JobPositionImportRequest(BaseModel):
    """用户导入岗位：必须提供来源链接，或选择手动录入（无链接，标记 manual）。"""

    company: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=120)
    location: str = Field(default="", max_length=200)
    level: str = Field(default="", max_length=40)
    industry_id: str | None = Field(default=None, max_length=60)
    occupation_id: str | None = Field(default=None, max_length=80)
    source_url: str | None = Field(default=None, max_length=500)
    responsibilities_summary: str = Field(default="", max_length=4000)
    required_skills_summary: str = Field(default="", max_length=4000)
    preferred_skills_summary: str = Field(default="", max_length=2000)
    experience_summary: str = Field(default="", max_length=300)
    jd_full_text: str | None = Field(default=None, max_length=20000)
    hiring_status: str = Field(default="unconfirmed", pattern="^(unconfirmed|open|closed)$")
    display_permission: str = Field(default="summary_only", pattern="^(summary_only|full_text)$")


class JobPositionImportResponse(BaseModel):
    position: JobPositionOut
    is_duplicate: bool


class JobPositionListResponse(BaseModel):
    items: list[JobPositionOut]
    total: int
    limit: int
    offset: int


class JobAnalyzeFromPositionRequest(BaseModel):
    """从库内岗位发起知岗解析。"""

    force_new: bool = False  # 默认复用当前用户已有的最新解析


class JobMatchFromPositionRequest(BaseModel):
    """从库内岗位发起合契匹配。"""

    resume_id: int
