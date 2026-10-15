"""拾贝（官方简历模板指南库）公开只读端点：字段完整、来源可溯、无个人简历内容。"""

from datetime import date as date_type

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_resume_gallery_public_and_shape():
    """公开端点无需登录即可访问，结构完整。"""
    resp = client.get("/api/v1/resume-gallery")
    assert resp.status_code == 200
    data = resp.json()
    # 全局查阅日期必须是合法日期
    date_type.fromisoformat(data["verified_on"])
    templates = data["templates"]
    assert len(templates) >= 15


def test_resume_gallery_template_fields_complete():
    templates = client.get("/api/v1/resume-gallery").json()["templates"]
    ids = {t["id"] for t in templates}
    assert len(ids) == len(templates), "模板 id 不得重复"
    for t in templates:
        assert t["name"] and t["industry"] and t["audience"]
        assert isinstance(t["structure"], list) and len(t["structure"]) >= 3
        assert isinstance(t["tips"], list) and t["tips"]
        # 来源可溯：URL 为 http(s) 官方链接、来源标题与查阅日期齐全
        assert t["source_url"].startswith(("http://", "https://"))
        assert t["source_title"]
        date_type.fromisoformat(t["accessed_at"])


def test_resume_gallery_no_personal_resume_content():
    """只收录写作规范：不得包含姓名/电话等个人简历字段取值，防止夹带真实简历信息。"""
    import re

    text = str(client.get("/api/v1/resume-gallery").json())
    assert not re.search(r"1[3-9]\d{9}", text), "不得出现手机号形态的内容"


def test_resume_gallery_official_sources():
    """来源必须为高校就业网、国家就业服务平台或招聘平台官方指南，不得编造或使用论坛链接。"""
    templates = client.get("/api/v1/resume-gallery").json()["templates"]
    allowed_hosts = (
        ".edu.cn",
        "24365.ncss.cn",
        "24365.smartedu.cn",
        "51job.com",
        "yinhangzhaopin.com",
    )
    for t in templates:
        assert any(h in t["source_url"] for h in allowed_hosts), t["source_url"]
