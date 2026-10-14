"""履历成章测试：简历真实保存、版本快照、模板渲染、AI 润色防捏造、PDF/DOCX 导出与权限隔离。

模型调用全部使用 FakeArkClient 预设响应，不发起真实网络请求；
导出测试对生成文件做真实字节级校验（PDF 魔数 / DOCX zip 内容）。
"""

import io
import zipfile

import pytest
from fastapi.testclient import TestClient

from app.services import auth_service
from tests.conftest import app, make_user, login_user, use_fake_client

RESUMES = "/api/v1/resumes"


def _client_with_token(token: str) -> TestClient:
    client = TestClient(app)
    client.cookies.set(auth_service.SESSION_COOKIE_NAME, token)
    return client


def _sample_content(*, company: str = "云帆科技", extra_skill: str | None = None) -> dict:
    content = {
        "basics": {
            "name": "林澜",
            "phone": "13800000000",
            "email": "linlan@qq.com",
            "location": "杭州",
            "summary": "三年 React 前端开发经验，熟悉组件库建设。",
        },
        "education": [
            {"school": "观澜大学", "degree": "本科", "major": "软件工程", "start": "2018-09", "end": "2022-06"}
        ],
        "work": [
            {
                "name": company,
                "role": "前端工程师",
                "start": "2022-07",
                "end": "至今",
                "highlights": ["使用 React 与 TypeScript 重构管理后台"],
            }
        ],
        "projects": [],
        "skills": [{"name": "React", "level": "精通", "detail": "Hooks 与状态管理"}],
        "certificates": [{"name": "CET-6", "issuer": "教育部", "date": "2020-12"}],
        "awards": [],
    }
    if extra_skill:
        content["skills"].append({"name": extra_skill, "level": "熟悉", "detail": ""})
    return content


def _create_resume(api_client: TestClient, *, template_id: str = "tech", **kwargs) -> dict:
    response = api_client.post(
        RESUMES,
        json={"title": "林澜的前端简历", "template_id": template_id, "content": _sample_content(**kwargs)},
    )
    assert response.status_code == 201, response.text
    return response.json()


# ---------- 模板目录 ----------


def test_templates_endpoint_lists_seven_layouts(api_client):
    response = api_client.get(f"{RESUMES}/templates")
    assert response.status_code == 200
    templates = response.json()
    assert len(templates) == 7

    by_id = {t["id"]: t for t in templates}
    assert set(by_id) == {"clean", "campus", "tech", "product", "design", "research", "finance"}
    # 模板差异必须是真实版式差异：分节顺序与主题色，而非仅换颜色
    assert by_id["campus"]["section_order"][0] == "education"  # 应届生教育前置
    assert by_id["tech"]["section_order"][1] == "skills"  # 技术型技能置顶
    assert by_id["research"]["section_order"][0] == "education"
    accents = {t["accent"] for t in templates}
    assert accents <= {"#4D83D6", "#315FAD"}  # 观澜蓝白体系，无霓虹色


# ---------- 创建 / 保存 / 读取 ----------


def test_create_and_read_resume_persists_content(api_client):
    data = _create_resume(api_client)
    assert data["title"] == "林澜的前端简历"
    assert data["template_id"] == "tech"
    assert data["current_version_no"] == 1
    assert data["content"]["basics"]["name"] == "林澜"
    assert data["content"]["work"][0]["name"] == "云帆科技"
    assert data["versions"][0]["note"] == "初始版本"

    fetched = api_client.get(f"{RESUMES}/{data['id']}").json()
    assert fetched["content"] == data["content"]


def test_save_creates_version_snapshot(api_client):
    data = _create_resume(api_client)
    updated = api_client.put(
        f"{RESUMES}/{data['id']}",
        json={"content": _sample_content(extra_skill="Node.js"), "note": "补充服务端技能"},
    )
    assert updated.status_code == 200, updated.text
    body = updated.json()
    assert body["current_version_no"] == 2
    assert body["content"]["skills"][1]["name"] == "Node.js"

    versions = api_client.get(f"{RESUMES}/{data['id']}/versions").json()
    assert [v["version_no"] for v in versions] == [2, 1]
    assert versions[1]["note"] == "初始版本"

    # v1 快照内容不可变：仍是两技能之前的旧内容
    v1 = api_client.get(f"{RESUMES}/{data['id']}/versions/1").json()
    assert v1["content"]["skills"] == body["content"]["skills"][:1]


def test_restore_version_rolls_back_and_appends_snapshot(api_client):
    data = _create_resume(api_client)
    api_client.put(f"{RESUMES}/{data['id']}", json={"content": _sample_content(company="沧海网络"), "note": "换公司"})
    restored = api_client.post(f"{RESUMES}/{data['id']}/versions/1/restore")
    assert restored.status_code == 200
    body = restored.json()
    assert body["current_version_no"] == 3  # 恢复也生成新快照，历史不可变
    assert body["content"]["work"][0]["name"] == "云帆科技"
    assert body["versions"][0]["note"] == "恢复自 v1"
    assert [v["version_no"] for v in body["versions"]] == [3, 2, 1]


def test_duplicate_version_copies_snapshot(api_client):
    data = _create_resume(api_client)
    duplicated = api_client.post(f"{RESUMES}/{data['id']}/versions/1/duplicate")
    assert duplicated.status_code == 200
    body = duplicated.json()
    assert body["version_no"] == 2
    assert body["note"] == "复制自 v1"
    assert body["content"]["work"][0]["name"] == "云帆科技"


# ---------- 模板切换与输入校验 ----------


def test_template_switch_persists(api_client):
    data = _create_resume(api_client, template_id="tech")
    switched = api_client.put(
        f"{RESUMES}/{data['id']}",
        json={"template_id": "campus", "content": data["content"], "note": "切换应届模板"},
    )
    assert switched.status_code == 200
    assert switched.json()["template_id"] == "campus"
    assert api_client.get(f"{RESUMES}/{data['id']}").json()["template_id"] == "campus"


def test_create_rejects_unknown_template(api_client):
    response = api_client.post(
        RESUMES, json={"title": "简历", "template_id": "neon-cyber", "content": _sample_content()}
    )
    assert response.status_code == 422
    assert "模板不存在" in response.json()["detail"]


def test_create_rejects_overlimit_entries(api_client):
    content = _sample_content()
    content["work"][0]["highlights"] = [f"要点{i}" for i in range(9)]  # 上限 8 条
    response = api_client.post(RESUMES, json={"title": "简历", "content": content})
    assert response.status_code == 422


def test_list_and_delete_resume(api_client):
    data = _create_resume(api_client)
    listed = api_client.get(RESUMES).json()
    assert [r["id"] for r in listed] == [data["id"]]

    assert api_client.delete(f"{RESUMES}/{data['id']}").status_code == 204
    assert api_client.get(RESUMES).json() == []
    assert api_client.get(f"{RESUMES}/{data['id']}").status_code == 404


# ---------- 权限隔离 ----------


def test_resume_permission_isolation(api_client, db_session):
    data = _create_resume(api_client)

    other = make_user(db_session, username="resume-other", nickname="乙用户")
    other_client = _client_with_token(login_user(db_session, other))
    assert other_client.get(f"{RESUMES}/{data['id']}").status_code == 404
    assert other_client.put(f"{RESUMES}/{data['id']}", json={"content": _sample_content()}).status_code == 404
    assert other_client.delete(f"{RESUMES}/{data['id']}").status_code == 404
    assert other_client.get(f"{RESUMES}/{data['id']}/export").status_code == 404
    assert other_client.get(RESUMES).json() == []


def test_resume_endpoints_require_login(anon_client):
    assert anon_client.get(RESUMES).status_code == 401
    assert anon_client.get(f"{RESUMES}/templates").status_code == 401
    assert anon_client.post(RESUMES, json={"title": "x", "content": {}}).status_code == 401


# ---------- AI 润色：只给建议、不自动保存、不捏造 ----------


ORIGINAL_TEXT = "负责数据后台重构，与 5 人团队协作，按期完成上线。"


def test_polish_returns_suggestion_without_touching_resume(api_client):
    fake = use_fake_client(
        [
            {"polished": "主导数据后台重构：与 5 人团队协作推进，按期完成上线交付。", "notes": "调整语序，突出主导性。"}
        ]
    )
    data = _create_resume(api_client)
    response = api_client.post(
        f"{RESUMES}/{data['id']}/polish", json={"section": "work", "text": ORIGINAL_TEXT}
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert "5" in body["polished"]
    assert body["notes"]
    assert body["model_name"] == "fake-model-test"
    assert fake.calls and "简历段落" in fake.calls[0][1]

    # 建议≠落库：简历内容必须保持原样，等待用户确认
    after = api_client.get(f"{RESUMES}/{data['id']}").json()
    assert after["current_version_no"] == 1
    assert after["content"] == data["content"]


def test_polish_retries_when_fabricating_numbers_then_succeeds(api_client):
    """模型试图编造"提升 80%"这类原文没有的数字时必须重试。"""
    use_fake_client(
        [
            {"polished": "主导重构，性能提升 80%，与 5 人团队协作。", "notes": ""},
            {"polished": "主导数据后台重构，与 5 人团队协作完成上线。", "notes": "已去除推测指标。"},
        ]
    )
    data = _create_resume(api_client)
    response = api_client.post(
        f"{RESUMES}/{data['id']}/polish", json={"section": "work", "text": ORIGINAL_TEXT}
    )
    assert response.status_code == 200
    assert "80" not in response.json()["polished"]


def test_polish_fails_honestly_after_repeated_fabrication(api_client):
    use_fake_client(
        [
            {"polished": "提升 80% 效率，管理 5 人团队。", "notes": ""},
            {"polished": "提升 30% 效率，管理 5 人团队。", "notes": ""},
            {"polished": "提升 2 倍效率，管理 5 人团队。", "notes": ""},
        ]
    )
    data = _create_resume(api_client)
    response = api_client.post(
        f"{RESUMES}/{data['id']}/polish", json={"section": "work", "text": ORIGINAL_TEXT}
    )
    assert response.status_code == 502
    assert "防捏造校验" in response.json()["detail"]


def test_polish_rejects_invalid_section(api_client):
    use_fake_client([])
    data = _create_resume(api_client)
    response = api_client.post(
        f"{RESUMES}/{data['id']}/polish", json={"section": "skills", "text": ORIGINAL_TEXT}
    )
    assert response.status_code == 422


def test_polish_not_configured_returns_503(api_client, monkeypatch):
    import app.routers.interviews as interviews_router
    from tests.conftest import NotConfiguredArkClient

    monkeypatch.setitem(
        app.dependency_overrides, interviews_router.get_ark_client, lambda: NotConfiguredArkClient()
    )
    data = _create_resume(api_client)
    response = api_client.post(
        f"{RESUMES}/{data['id']}/polish", json={"section": "work", "text": ORIGINAL_TEXT}
    )
    assert response.status_code == 503
    assert "ARK_API_KEY" in response.json()["detail"]


# ---------- 拖拽解析（忠实转录，绝不编造） ----------

RESUME_FILE_TEXT = (
    "林澜，电话 13800000000，邮箱 linlan@qq.com，现居杭州。\n"
    "三年 React 前端开发经验，熟悉组件库建设。\n"
    "教育：观澜大学 软件工程 本科，2018-09 至 2022-06。\n"
    "工作：云帆科技 前端工程师，2022-07 至今；使用 React 与 TypeScript 重构管理后台。\n"
    "技能：React（精通），Hooks 与状态管理。\n"
    "证书：CET-6，教育部，2020-12。"
)

PARSE_AI_OK = {
    "title": "林澜 · 前端工程师",
    "position": "前端工程师",
    "content": _sample_content(),
}


def _parse_file(client: TestClient, *, filename: str = "我的简历.txt",
                content: bytes | None = None, jd_text: str = ""):
    data = content if content is not None else RESUME_FILE_TEXT.encode("utf-8")
    kwargs = {"data": {"jd_text": jd_text}} if jd_text else {}
    return client.post(
        f"{RESUMES}/parse",
        files={"file": (filename, data, "text/plain")},
        **kwargs,
    )


def test_parse_requires_login(anon_client):
    response = _parse_file(anon_client)
    assert response.status_code == 401


def test_parse_txt_returns_text_and_ai_structure(api_client):
    use_fake_client([PARSE_AI_OK])
    response = _parse_file(api_client, jd_text="招聘前端工程师，要求 React 经验")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["filename"] == "我的简历.txt"
    assert "React" in body["text"] and "CET-6" in body["text"]
    assert body["title"] == "林澜 · 前端工程师"
    assert body["position"] == "前端工程师"
    assert body["content"]["basics"]["name"] == "林澜"
    assert body["content"]["work"][0]["name"] == "云帆科技"
    assert body["parse_error"] is None


def test_parse_rejects_unsupported_type(api_client):
    use_fake_client([])
    response = _parse_file(
        api_client, filename="payload.exe", content=b"MZ\x90\x00binary"
    )
    assert response.status_code == 422


def test_parse_rejects_empty_text(api_client):
    use_fake_client([])
    response = _parse_file(api_client, filename="blank.txt", content="   \n".encode("utf-8"))
    assert response.status_code == 422


def test_parse_retries_and_rejects_fabricated_numbers(api_client):
    """结构化结果出现原文没有的数字 → 服务端拒绝并重试；重试成功则正常返回。"""
    fabricated = {
        "title": "林澜 · 前端工程师",
        "position": "前端工程师",
        "content": _sample_content(),
    }
    fabricated["content"]["work"][0]["highlights"] = ["性能提升 300%，重构 12 个模块"]
    use_fake_client([fabricated, PARSE_AI_OK])
    response = _parse_file(api_client)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["parse_error"] is None
    assert body["content"]["work"][0]["highlights"] == [
        "使用 React 与 TypeScript 重构管理后台"
    ]


def test_parse_degrades_honestly_after_repeated_failures(api_client):
    fabricated = {
        "title": "林澜 · 前端工程师",
        "position": "前端工程师",
        "content": _sample_content(),
    }
    fabricated["content"]["work"][0]["highlights"] = ["性能提升 300%"]
    use_fake_client([fabricated, fabricated, fabricated])
    response = _parse_file(api_client)
    assert response.status_code == 200
    body = response.json()
    assert body["text"].startswith("林澜")  # 文本提取照常返回
    assert body["content"] is None
    assert body["title"] is None
    assert body["position"] is None
    assert "AI 解析失败" in body["parse_error"]


def test_parse_degrades_honestly_without_ai_configured(api_client, monkeypatch):
    import app.routers.interviews as interviews_router
    from tests.conftest import NotConfiguredArkClient

    monkeypatch.setitem(
        app.dependency_overrides, interviews_router.get_ark_client, lambda: NotConfiguredArkClient()
    )
    response = _parse_file(api_client)
    assert response.status_code == 200
    body = response.json()
    assert body["content"] is None
    assert "ARK_API_KEY" in body["parse_error"]


# ---------- 导出：真实文件生成 ----------


def test_export_pdf_real_file(api_client):
    data = _create_resume(api_client)
    response = api_client.get(f"{RESUMES}/{data['id']}/export", params={"format": "pdf"})
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/pdf"
    assert "attachment" in response.headers["content-disposition"]
    payload = response.content
    assert payload[:5] == b"%PDF-"  # 真实 PDF 魔数
    assert len(payload) > 1000  # 含中文字体与完整版式，绝非空文件


def test_export_docx_real_file(api_client):
    data = _create_resume(api_client)
    response = api_client.get(f"{RESUMES}/{data['id']}/export", params={"format": "docx"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    payload = response.content
    assert payload[:2] == b"PK"  # OOXML zip 魔数

    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        document_xml = archive.read("word/document.xml").decode("utf-8")
    assert "林澜" in document_xml  # 中文名正常写入
    assert "云帆科技" in document_xml
    assert "观澜大学" in document_xml


def test_export_docx_matches_requested_version(api_client):
    """导出历史版本时内容必须与该版本快照一致，而非当前内容。"""
    data = _create_resume(api_client)
    api_client.put(
        f"{RESUMES}/{data['id']}", json={"content": _sample_content(company="沧海网络"), "note": "换公司"}
    )

    response = api_client.get(
        f"{RESUMES}/{data['id']}/export", params={"format": "docx", "version_no": 1}
    )
    assert response.status_code == 200
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        document_xml = archive.read("word/document.xml").decode("utf-8")
    assert "云帆科技" in document_xml
    assert "沧海网络" not in document_xml


def test_export_with_design_template_and_missing_fields(api_client):
    """分栏模板 + 缺失字段：导出不得崩溃，姓名缺失用占位提示而非编造。"""
    response = api_client.post(
        RESUMES,
        json={
            "title": "空白设计简历",
            "template_id": "design",
            "content": {"basics": {"name": ""}, "projects": [{"name": "作品集网站", "highlights": ["视觉改版"]}]},
        },
    )
    assert response.status_code == 201
    resume_id = response.json()["id"]

    pdf = api_client.get(f"{RESUMES}/{resume_id}/export", params={"format": "pdf"})
    assert pdf.status_code == 200
    assert pdf.content[:5] == b"%PDF-"


def test_export_rejects_unknown_format(api_client):
    data = _create_resume(api_client)
    response = api_client.get(f"{RESUMES}/{data['id']}/export", params={"format": "html"})
    assert response.status_code == 422
    assert "pdf 或 docx" in response.json()["detail"]


def test_export_unknown_version_404(api_client):
    data = _create_resume(api_client)
    response = api_client.get(
        f"{RESUMES}/{data['id']}/export", params={"format": "pdf", "version_no": 42}
    )
    assert response.status_code == 404
