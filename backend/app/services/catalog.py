"""行业与职业目录服务：从 JSON Seed 加载，提供检索、组合校验与自定义职业支持。

- 目录数据（24 个行业 + 160+ 职业）来自 app/data/catalog.json，可扩展。
- 特殊值：industry_id="other" 表示"其他行业"；occupation_id="custom" 表示自定义职业。
- 前后端双重校验：本模块是服务端唯一可信的目录校验入口。
"""

import json
from functools import lru_cache
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "catalog.json"

INDUSTRY_OTHER_ID = "other"
INDUSTRY_OTHER_NAME = "其他行业"
OCCUPATION_CUSTOM_ID = "custom"
OCCUPATION_CUSTOM_NAME = "自定义职业"

CUSTOM_OCCUPATION_MIN = 2
CUSTOM_OCCUPATION_MAX = 60


@lru_cache(maxsize=1)
def _load() -> tuple[dict[str, dict], list[dict]]:
    raw = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    industries = {item["id"]: item for item in raw["industries"]}
    occupations: list[dict] = raw["occupations"]
    return industries, occupations


def occupation_count(industry_id: str) -> int:
    _, occupations = _load()
    return sum(1 for o in occupations if o["industry_id"] == industry_id)


def list_industries() -> list[dict]:
    industries, _ = _load()
    items = [
        {"id": item["id"], "name": item["name"], "occupation_count": occupation_count(item["id"])}
        for item in industries.values()
    ]
    items.append({"id": INDUSTRY_OTHER_ID, "name": INDUSTRY_OTHER_NAME, "occupation_count": 0})
    return items


def list_occupations(industry_id: str | None = None, q: str | None = None) -> list[dict]:
    """按行业与关键词检索职业；关键词匹配名称与别名（不区分大小写）。"""
    _, occupations = _load()
    query = (q or "").strip().lower()
    result: list[dict] = []
    for item in occupations:
        if industry_id and item["industry_id"] != industry_id:
            continue
        if query:
            haystack = " ".join([item["name"], *item.get("aliases", [])]).lower()
            if query not in haystack:
                continue
        result.append(item)
    return result


def get_industry(industry_id: str) -> dict | None:
    industries, _ = _load()
    if industry_id == INDUSTRY_OTHER_ID:
        return {"id": INDUSTRY_OTHER_ID, "name": INDUSTRY_OTHER_NAME}
    return industries.get(industry_id)


def get_occupation(occupation_id: str) -> dict | None:
    _, occupations = _load()
    return next((o for o in occupations if o["id"] == occupation_id), None)


class CatalogError(ValueError):
    """行业/职业组合不合法（面向用户可读的 message）。"""


def resolve_occupation(
    industry_id: str, occupation_id: str, custom_occupation: str | None
) -> tuple[str, str, dict | None]:
    """校验行业与职业组合，返回 (职业显示名, 行业名, 职业目录条目 | None)。

    - 其他行业：只允许自定义职业。
    - 自定义职业：需要提供 custom_occupation 文本（2-60 字符）。
    - 目录职业：必须属于所选行业，否则视为非法组合。
    """
    industry = get_industry(industry_id)
    if industry is None:
        raise CatalogError("所选行业不在目录中，请重新选择")

    custom_name = (custom_occupation or "").strip()
    if occupation_id == OCCUPATION_CUSTOM_ID or industry_id == INDUSTRY_OTHER_ID:
        if not custom_name:
            raise CatalogError(
                "该行业或组合没有目录职业可选，请填写自定义职业名称"
                if industry_id == INDUSTRY_OTHER_ID
                else "请填写自定义职业名称"
            )
        if not (CUSTOM_OCCUPATION_MIN <= len(custom_name) <= CUSTOM_OCCUPATION_MAX):
            raise CatalogError(
                f"自定义职业名称需在 {CUSTOM_OCCUPATION_MIN}-{CUSTOM_OCCUPATION_MAX} 个字符之间"
            )
        return custom_name, industry["name"], None

    occupation = get_occupation(occupation_id)
    if occupation is None:
        raise CatalogError("所选职业不在目录中，请重新选择")
    if occupation["industry_id"] != industry_id:
        raise CatalogError(
            f"职业「{occupation['name']}」不属于行业「{industry['name']}」，请重新选择"
        )
    return occupation["name"], industry["name"], occupation


def occupation_context(occupation: dict | None, occupation_name: str, focus_areas: list[str]) -> str:
    """组装传给评分等下游模块的职业上下文文本。"""
    if occupation is None:
        return occupation_name
    parts = [
        f"行业：{get_industry(occupation['industry_id'])['name'] if get_industry(occupation['industry_id']) else ''}",
        f"职业：{occupation_name}",
        f"核心技能：{'、'.join(occupation['core_skills'])}",
        f"能力维度：{'、'.join(occupation['dimensions'])}",
    ]
    if focus_areas:
        from app.services.question_generator import FOCUS_LABELS

        labels = [FOCUS_LABELS.get(f, f) for f in focus_areas]
        parts.append(f"题目侧重：{'、'.join(labels)}")
    return "；".join(p for p in parts if p)
