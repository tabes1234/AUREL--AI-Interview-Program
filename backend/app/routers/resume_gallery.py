"""拾贝：官方简历写作指南与模板结构库（只读公开数据）。

数据真实性原则：
- 每条模板规范都来自高校就业指导中心、政府就业服务平台或知名招聘平台官方页面，
  人工核对后录入 backend/app/data/resume_gallery.json；绝不编造来源。
- 只收录模板结构与写法规范，不收录任何真实个人简历内容。
- 每条附来源链接、来源标题与查阅日期；模板库为只读静态数据，无用户生成内容。
"""

import json
from pathlib import Path
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/v1/resume-gallery", tags=["resume-gallery"])

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "resume_gallery.json"


class ResumeTemplate(BaseModel):
    id: str
    name: str
    industry: str
    audience: str
    structure: list[str]
    tips: list[str]
    source_url: str
    source_title: str
    accessed_at: str


class ResumeGalleryResponse(BaseModel):
    verified_on: str
    templates: list[ResumeTemplate]

    model_config = {"json_schema_extra": {
        "example": {
            "verified_on": "2026-10-15",
            "templates": [],
        }
    }}


@router.get("", response_model=ResumeGalleryResponse)
def list_resume_templates() -> ResumeGalleryResponse:
    """拾贝模板库：按行业分类的官方简历结构规范，只读公开数据。"""
    raw = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    return ResumeGalleryResponse(
        verified_on=raw.get("verified_on", ""),
        templates=[ResumeTemplate(**item) for item in raw["templates"]],
    )
