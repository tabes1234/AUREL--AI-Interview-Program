"""行业与职业目录 API：供前端问澜选择器读取。"""

from fastapi import APIRouter, Query

from app.services import catalog as catalog_service

router = APIRouter(prefix="/api/v1/catalog", tags=["catalog"])


@router.get("/industries")
def list_industries() -> dict:
    """全部行业（含「其他行业」），按目录顺序返回。"""
    return {"items": catalog_service.list_industries()}


@router.get("/occupations")
def list_occupations(
    industry_id: str | None = Query(default=None, max_length=60),
    q: str | None = Query(default=None, max_length=60),
) -> dict:
    """职业检索：必须按行业过滤；q 模糊匹配名称与别名。"""
    if industry_id:
        if catalog_service.get_industry(industry_id) is None:
            return {"items": []}
        items = catalog_service.list_occupations(industry_id=industry_id, q=q)
    else:
        items = catalog_service.list_occupations(q=q)
    return {"items": items}
