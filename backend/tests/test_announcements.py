"""澜讯公告接口：真实阶段记录，无编造内容。"""

from datetime import date as date_type

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_announcements_shape_and_content():
    resp = client.get("/api/v1/announcements")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) >= 5
    for item in items:
        assert item["id"] and item["type"] and item["title"] and item["summary"]
        assert isinstance(item["items"], list) and item["items"]
        if item["date"] is not None:
            # 有日期必须是合法 YYYY-MM-DD，无日期如实为 null，绝不编造
            date_type.fromisoformat(item["date"])


def test_announcements_sorted_dated_first():
    items = client.get("/api/v1/announcements").json()["items"]
    dated = [i["date"] for i in items if i["date"]]
    assert dated == sorted(dated, reverse=True)
    assert all(i["date"] is None for i in items[len(dated):])


def test_announcements_early_history_retired():
    """前期开发过程公告已按内容策略下线：仅保留近期核心公告，历史条目不得复活。"""
    items = client.get("/api/v1/announcements").json()["items"]
    retired_ids = {
        "release-v0.3.0",
        "milestone-phase-1",
        "milestone-phase-2",
        "milestone-phase-3",
        "milestone-phase-4",
        "milestone-phase-6",
        "milestone-phase-9",
        "milestone-phase-10",
        "milestone-phase-12",
        "milestone-brand-refresh",
        "fix-phase-2-followup",
    }
    ids = {i["id"] for i in items}
    assert not ids & retired_ids
    # 保留的普通公告必须都带日期（近期记录，无日期条目只允许是置顶档案）
    normal = [i for i in items if not i.get("pinned")]
    assert len(normal) == 5
    assert all(i["date"] for i in normal)


def test_tech_archive_pinned_first_and_single():
    items = client.get("/api/v1/announcements").json()["items"]
    pinned = [i for i in items if i.get("pinned")]
    assert len(pinned) == 1
    assert items[0]["id"] == "project-tech-archive"
    assert items[0]["importance"] == "重要"
    assert "置顶公告" in items[0]["tags"]
    # 置顶公告必须带更新时间，且早于它的普通公告不会被排到前面
    assert items[0]["updated_at"] == "2026-10-14"


def test_tech_archive_detail_sections():
    resp = client.get("/api/v1/announcements/project-tech-archive")
    assert resp.status_code == 200
    data = resp.json()
    assert data["announcement"]["id"] == "project-tech-archive"
    sections = data["sections"]
    assert [s["id"] for s in sections] == [
        "overview",
        "frontend",
        "backend",
        "database",
        "ai",
        "security",
        "modules",
        "design",
        "quality",
        "deployment",
        "progress",
        "changelog",
    ]
    # 表格章节必须表头与行数齐全
    modules = next(s for s in sections if s["id"] == "modules")
    assert modules["table_head"] and len(modules["table_rows"]) >= 15
    # 不得出现敏感取值：密钥类字段只允许出现变量名形态
    text = str(data)
    assert "sk-" not in text and "ARK_API_KEY=" not in text
