"""使用数据上报：登录用户在工作区页面的访问事件。

- 仅接受白名单模块标识，避免任意字符串写入；
- 30 秒内同一用户同一页面去重，刷新/重渲染不重复计数；
- 未登录请求由中间件统一 401，不采集匿名访问。
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import current_user_id
from app.services.usage_tracking import MODULES, record_page_view

router = APIRouter(prefix="/api/v1/usage", tags=["usage"])


class PageViewRequest(BaseModel):
    module: str
    name: str = "page_view"

    @field_validator("module")
    @classmethod
    def _check_module(cls, value: str) -> str:
        if value not in MODULES:
            raise ValueError("未知的模块标识")
        return value

    @field_validator("name")
    @classmethod
    def _check_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not 1 <= len(cleaned) <= 60:
            raise ValueError("事件名长度需在 1-60 字符之间")
        return cleaned


@router.post("/page-view")
def page_view(
    body: PageViewRequest,
    db: Session = Depends(get_db),
    user_id: int = Depends(current_user_id),
):
    recorded = record_page_view(db, user_id=user_id, module=body.module, name=body.name)
    db.commit()
    if not recorded:
        return {"recorded": False, "reason": "deduped"}
    return {"recorded": True}


@router.get("/modules")
def usage_modules(_user_id: int = Depends(current_user_id)):
    """模块白名单（供前端上报时校验/展示）。"""
    return {"modules": [{"key": k, "label": v} for k, v in MODULES.items()]}
