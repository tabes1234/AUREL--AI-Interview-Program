"""知岗测试：JD 校验、结构化解析、证据核验、历史版本、权限隔离、问澜/合契联动。

模型调用全部使用 FakeArkClient 预设响应，不发起真实网络请求。
"""

import io

import pytest
from fastapi.testclient import TestClient

from app.services import auth_service
from tests.conftest import (
    FakeArkClient,
    NotConfiguredArkClient,
    app,
    make_user,
    login_user,
    question_generation_response,
    use_fake_client,
)

SAMPLE_JD = (
    "岗位职责：负责公司核心 SaaS 产品的 Web 前端开发，参与组件库建设与性能优化。\n"
    "任职要求：本科及以上学历，3 年以上前端开发经验，精通 React 与 TypeScript，"
    "熟悉 Webpack 构建优化。有 Node.js 服务端经验者优先。熟悉 SQL 者优先。\n"
    "工作地点：杭州。我们提供有竞争力的薪酬。"
)


def _valid_analysis_payload() -> dict:
    return {
        "position_name": "前端开发工程师",
        "industry": "互联网",
        "responsibilities": [
            {"text": "负责核心 SaaS 产品的 Web 前端开发", "evidence": "负责公司核心 SaaS 产品的 Web 前端开发"},
            {"text": "组件库建设", "evidence": "参与组件库建设与性能优化"},
        ],
        "required_skills": [
            {"text": "React", "evidence": "精通 React 与 TypeScript"},
            {"text": "TypeScript", "evidence": "精通 React 与 TypeScript"},
        ],
        "preferred_skills": [{"text": "Node.js", "evidence": "有 Node.js 服务端经验者优先"}],
        "experience_requirement": {"text": "3 年以上前端开发经验", "evidence": "3 年以上前端开发经验"},
        "education_requirement": {"text": "本科及以上学历", "evidence": "本科及以上学历"},
        "tools": [{"text": "Webpack", "evidence": "熟悉 Webpack 构建优化"}],
        "capability_dimensions": ["前端工程化", "性能优化", "组件设计"],
        "interview_directions": ["React 原理", "构建优化实践", "组件库设计"],
        "keywords": ["React", "TypeScript", "Webpack", "SaaS", "组件库"],
    }


def _client_with_token(token: str) -> TestClient:
    client = TestClient(app)
    client.cookies.set(auth_service.SESSION_COOKIE_NAME, token)
    return client


def _analyze(client: TestClient, jd_text: str = SAMPLE_JD) -> dict:
    response = client.post("/api/v1/jobs/analyze", json={"jd_text": jd_text})
    assert response.status_code == 201, response.text
    return response.json()


# ---------- 输入校验 ----------


def test_analyze_rejects_too_short_jd(api_client):
    use_fake_client([])
    response = api_client.post("/api/v1/jobs/analyze", json={"jd_text": "太短了"})
    assert response.status_code == 422
    assert "至少" in response.json()["detail"]


def test_analyze_rejects_overlong_jd(api_client):
    use_fake_client([])
    response = api_client.post("/api/v1/jobs/analyze", json={"jd_text": "岗" * 20001})
    assert response.status_code == 422


def test_analyze_requires_login(anon_client):
    response = anon_client.post("/api/v1/jobs/analyze", json={"jd_text": SAMPLE_JD})
    assert response.status_code == 401


# ---------- 结构化解析与证据核验 ----------


def test_analyze_returns_structured_result(api_client):
    fake = use_fake_client([_valid_analysis_payload()])
    data = _analyze(api_client)

    assert data["title"] == "前端开发工程师"
    assert data["version_no"] == 1
    assert data["status"] == "ready"
    assert data["model_name"] == "fake-model-test"
    result = data["result"]
    assert result["position_name"] == "前端开发工程师"
    assert len(result["responsibilities"]) == 2
    # 服务端应保留 evidence 并对可定位证据标记非推断
    assert result["required_skills"][0]["is_inferred"] is False
    assert fake.calls, "应真实调用模型"
    system_prompt, user_prompt = fake.calls[0]
    assert "原文" in system_prompt  # 系统提示要求严格基于 JD 原文
    assert "React" in user_prompt  # JD 原文已随提示发送


def test_unverifiable_evidence_marked_as_inferred(api_client):
    """证据无法在 JD 原文定位时，必须降级为模型推断而不是冒充原文结论。"""
    payload = _valid_analysis_payload()
    payload["required_skills"][0]["evidence"] = "JD 里根本没有这句话"
    payload["education_requirement"]["evidence"] = None  # 未提供证据 → 推断
    use_fake_client([payload])
    data = _analyze(api_client)

    result = data["result"]
    assert result["required_skills"][0]["is_inferred"] is True
    assert result["required_skills"][1]["is_inferred"] is False
    assert result["education_requirement"]["is_inferred"] is True
    assert result["experience_requirement"]["is_inferred"] is False


def test_analyze_retries_on_invalid_structure_then_succeeds(api_client):
    """首次输出缺字段 → 服务端要求重试；第二次合法 → 成功。"""
    use_fake_client([{"position_name": "只有半个结果"}, _valid_analysis_payload()])
    data = _analyze(api_client)
    assert data["status"] == "ready"


def test_analyze_fails_honestly_after_max_attempts(api_client):
    """模型连续输出无效结构：返回真实 502，不伪造成功。"""
    use_fake_client([{"bad": 1}, {"bad": 2}, {"bad": 3}])
    response = api_client.post("/api/v1/jobs/analyze", json={"jd_text": SAMPLE_JD})
    assert response.status_code == 502
    assert "结构化校验" in response.json()["detail"]


def test_analyze_not_configured_returns_503(api_client, monkeypatch):
    import app.routers.interviews as interviews_router

    monkeypatch.setitem(
        app.dependency_overrides, interviews_router.get_ark_client, lambda: NotConfiguredArkClient()
    )
    response = api_client.post("/api/v1/jobs/analyze", json={"jd_text": SAMPLE_JD})
    assert response.status_code == 503
    assert "ARK_API_KEY" in response.json()["detail"]


# ---------- 历史与版本 ----------


def test_reanalyzing_same_jd_increments_version(api_client):
    use_fake_client([_valid_analysis_payload(), _valid_analysis_payload()])
    first = _analyze(api_client)
    second = _analyze(api_client)
    assert first["version_no"] == 1
    assert second["version_no"] == 2

    listed = api_client.get("/api/v1/jobs/analyses").json()
    assert [item["id"] for item in listed] == [second["id"], first["id"]]
    assert all(item["jd_preview"] for item in listed)


def test_analysis_detail_and_delete(api_client):
    use_fake_client([_valid_analysis_payload()])
    data = _analyze(api_client)
    detail = api_client.get(f"/api/v1/jobs/analyses/{data['id']}").json()
    assert detail["jd_text"] == SAMPLE_JD
    assert detail["result"]["position_name"] == "前端开发工程师"

    assert api_client.delete(f"/api/v1/jobs/analyses/{data['id']}").status_code == 204
    assert api_client.get(f"/api/v1/jobs/analyses/{data['id']}").status_code == 404


def test_analysis_permission_isolation(api_client, db_session):
    use_fake_client([_valid_analysis_payload()])
    data = _analyze(api_client)

    other = make_user(db_session, username="jobs-other", nickname="乙用户")
    other_client = _client_with_token(login_user(db_session, other))
    assert other_client.get(f"/api/v1/jobs/analyses/{data['id']}").status_code == 404
    assert other_client.delete(f"/api/v1/jobs/analyses/{data['id']}").status_code == 404
    assert data["id"] not in [i["id"] for i in other_client.get("/api/v1/jobs/analyses").json()]


# ---------- 文件上传 ----------


def test_upload_jd_text_file(api_client):
    response = api_client.post(
        "/api/v1/jobs/upload",
        files={"file": ("jd.txt", SAMPLE_JD.encode("utf-8"), "text/plain")},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["filename"] == "jd.txt"
    assert "React" in body["text"]


def test_upload_jd_docx_file(api_client):
    import docx as docx_lib

    document = docx_lib.Document()
    document.add_paragraph(SAMPLE_JD)
    buffer = io.BytesIO()
    document.save(buffer)
    response = api_client.post(
        "/api/v1/jobs/upload",
        files={"file": ("jd.docx", buffer.getvalue(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    assert response.status_code == 201
    assert "精通 React" in response.json()["text"]


def test_upload_jd_pdf_file(api_client):
    """PDF 上传走 pypdf 纯文本提取（reportlab 生成测试样本）。"""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    c.drawString(72, 720, SAMPLE_JD[:100])
    c.save()
    pdf_bytes = buffer.getvalue()

    response = api_client.post(
        "/api/v1/jobs/upload", files={"file": ("jd.pdf", pdf_bytes, "application/pdf")}
    )
    assert response.status_code == 201, response.text
    assert "React" in response.json()["text"]


def test_upload_rejects_unsupported_type(api_client):
    response = api_client.post(
        "/api/v1/jobs/upload",
        files={"file": ("jd.exe", b"MZ" + b"\x00" * 100, "application/octet-stream")},
    )
    assert response.status_code == 422


def test_upload_rejects_empty_and_oversize(api_client):
    empty = api_client.post(
        "/api/v1/jobs/upload", files={"file": ("jd.txt", b"", "text/plain")}
    )
    assert empty.status_code == 422

    oversize = api_client.post(
        "/api/v1/jobs/upload",
        files={"file": ("jd.txt", b"a" * (5 * 1024 * 1024 + 1), "text/plain")},
    )
    assert oversize.status_code == 413


def test_upload_requires_login(anon_client):
    response = anon_client.post(
        "/api/v1/jobs/upload", files={"file": ("jd.txt", SAMPLE_JD.encode(), "text/plain")}
    )
    assert response.status_code == 401


# ---------- 知岗 × 问澜联动 ----------


def test_create_interview_task_from_analysis(api_client):
    """联动必须复用现有问澜生成流程：结构化职责/技能进入出题依据。"""
    use_fake_client([_valid_analysis_payload(), question_generation_response(5)])
    analysis = _analyze(api_client)

    response = api_client.post(
        f"/api/v1/jobs/analyses/{analysis['id']}/interview-task",
        json={"question_count": 5, "difficulty": "advanced"},
    )
    assert response.status_code == 201, response.text
    task = response.json()
    assert task["position"] == "前端开发工程师"
    assert task["status"] == "ready"
    assert len(task["questions"]) == 5
    description = task["description"]
    assert "核心工作职责" in description and "React" in description
    assert "经验阶段" in description


def test_interview_task_allows_position_override(api_client):
    """用户修改岗位信息后重新生成：position 覆盖生效。"""
    use_fake_client([_valid_analysis_payload(), question_generation_response(3)])
    analysis = _analyze(api_client)
    response = api_client.post(
        f"/api/v1/jobs/analyses/{analysis['id']}/interview-task",
        json={"position": "高级前端开发工程师", "question_count": 3},
    )
    assert response.status_code == 201
    assert response.json()["position"] == "高级前端开发工程师"


def test_interview_task_permission_and_state(api_client, db_session):
    use_fake_client([_valid_analysis_payload()])
    analysis = _analyze(api_client)

    other = make_user(db_session, username="jobs-other2", nickname="丙用户")
    other_client = _client_with_token(login_user(db_session, other))
    assert (
        other_client.post(
            f"/api/v1/jobs/analyses/{analysis['id']}/interview-task", json={}
        ).status_code
        == 404
    )


# ---------- 知岗 × 履历成章/合契联动 ----------


def _create_resume(api_client: TestClient, *, with_sql: bool = False) -> dict:
    content = {
        "basics": {"name": "林澜", "summary": "三年 React 前端开发经验"},
        "work": [
            {
                "name": "云帆科技",
                "role": "前端工程师",
                "start": "2022-07",
                "end": "至今",
                "highlights": ["使用 React 与 TypeScript 重构管理后台，加载时间显著下降"],
            }
        ],
        "skills": [{"name": "React", "level": "精通", "detail": "Hooks 与状态管理"}],
    }
    if with_sql:
        content["skills"].append({"name": "SQL", "level": "熟悉", "detail": "复杂查询优化"})
    response = api_client.post(
        "/api/v1/resumes", json={"title": "林澜的前端简历", "template_id": "tech", "content": content}
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_match_analysis_with_resume(api_client):
    use_fake_client([_valid_analysis_payload(), {"suggestions": ["补充 Webpack 构建优化的量化结果"]}])
    analysis = _analyze(api_client)
    resume = _create_resume(api_client)

    response = api_client.post(
        f"/api/v1/jobs/analyses/{analysis['id']}/match", json={"resume_id": resume["id"]}
    )
    assert response.status_code == 201, response.text
    match = response.json()

    skill_names = [m["skill"] for m in match["matched_skills"]]
    assert "React" in skill_names and "TypeScript" in skill_names
    react = next(m for m in match["matched_skills"] if m["skill"] == "React")
    assert react["evidence"] and "React" in react["evidence"]  # 简历侧证据
    assert react["job_evidence"]  # JD 侧证据
    assert react["supporting_experiences"] and "工作经历" in react["supporting_experiences"][0]

    missing_names = [m["skill"] for m in match["missing_skills"]]
    assert "Webpack" in missing_names
    webpack = next(m for m in match["missing_skills"] if m["skill"] == "Webpack")
    assert webpack["suggestion"] and webpack["job_evidence"]

    assert 0 <= match["match_score"] <= 100
    assert "不代表获得工作的概率" in match["score_note"]
    assert match["suggestions"] == ["补充 Webpack 构建优化的量化结果"]


def test_match_llm_failure_degrades_gracefully(api_client):
    """建议模型失败时降级为纯统计结果并如实标注 llm_error。"""
    use_fake_client([_valid_analysis_payload()])

    class _FailClient(FakeArkClient):
        def chat_json(self, system, user, *, temperature=0.3, service="unattributed"):
            from app.services.ark_client import ArkError

            if service == "matching_suggestions":
                raise ArkError("AI 模型服务返回错误（HTTP 500）")
            return super().chat_json(system, user, temperature=temperature, service=service)

    fake = _FailClient([_valid_analysis_payload()])
    import app.routers.interviews as interviews_router

    app.dependency_overrides[interviews_router.get_ark_client] = lambda: fake

    analysis = _analyze(api_client)
    resume = _create_resume(api_client)
    response = api_client.post(
        f"/api/v1/jobs/analyses/{analysis['id']}/match", json={"resume_id": resume["id"]}
    )
    assert response.status_code == 201
    body = response.json()
    assert body["suggestions"] == []
    assert body["llm_error"] and "HTTP 500" in body["llm_error"]
    assert body["matched_skills"], "统计匹配不应依赖 LLM"


def test_match_requires_existing_resume(api_client):
    use_fake_client([_valid_analysis_payload()])
    analysis = _analyze(api_client)
    response = api_client.post(
        f"/api/v1/jobs/analyses/{analysis['id']}/match", json={"resume_id": 99999}
    )
    assert response.status_code == 404
